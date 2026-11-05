// Communities: the list (anyone can look), a community's page — what it is about, its rules, members and season
// rating — and joining (the rules accepted; by request, or with the code of an invite link) or leaving. Creating
// and running a community stays on the website.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../links.dart';
import '../main.dart';
import '../report.dart';
import '../theme.dart';
import '../widgets.dart';
import 'profile.dart';
import 'ratings.dart';

void openCommunities(BuildContext context) =>
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CommunitiesScreen()));

void openCommunity(BuildContext context, String slug) =>
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => CommunityScreen(slug: slug)));

class CommunityEmblem extends StatelessWidget {
  const CommunityEmblem({super.key, required this.icon, required this.hue, this.size = 44});

  final String? icon;
  final num hue;
  final double size;

  @override
  Widget build(BuildContext context) {
    final c = V.hue(hue, s: .75, l: .55);
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * .3),
        gradient: LinearGradient(colors: [c, V.hue(hue + 40, s: .75, l: .45)]),
        boxShadow: [BoxShadow(color: c.withValues(alpha: .35), blurRadius: 16, spreadRadius: -6)],
      ),
      child: Icon(vIcon(icon), color: Colors.white, size: size * .52),
    );
  }
}

String accessName(BuildContext context, String? access) =>
    (((SessionScope.read(context).catalog['social'] as Json?)?['access'] as Json?)?[access] as Json?)?['name']
        as String? ??
    '';

class CommunitiesScreen extends StatelessWidget {
  const CommunitiesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final mine = {for (final c in ((s.me?['communities'] as List?) ?? const []).cast<Json>()) c['slug']};
    return Scaffold(
      appBar: AppBar(title: const Text('Сообщества')),
      body: Loader<Json>(
        load: () => s.api.get('/communities'),
        builder: (context, data, reload) {
          final list = ((data['communities'] as List?) ?? const []).cast<Json>().toList()
            ..sort((a, b) => (mine.contains(b['slug']) ? 1 : 0) - (mine.contains(a['slug']) ? 1 : 0));
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              Text(
                'Клубы судей со своими правилами и своим рейтингом: судите дела вместе и сравнивайте вердикты.',
                style: V.body(13.5, color: V.muted),
              ),
              const SizedBox(height: 14),
              if (list.isEmpty)
                Panel(
                  child: Text('Сообществ пока нет — создайте первое на сайте.', style: V.body(14, color: V.muted)),
                ),
              for (final c in list)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Panel(
                    accent: mine.contains(c['slug']) ? V.violet : null,
                    onTap: () => openCommunity(context, c['slug'] as String),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CommunityEmblem(icon: c['icon'] as String?, hue: c['hue'] as num? ?? 190),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(c['name'] as String, style: V.body(15.5, weight: FontWeight.w800)),
                              if ((c['description'] as String? ?? '').isNotEmpty)
                                Text(
                                  c['description'] as String,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: V.body(13, color: V.muted),
                                ),
                              const SizedBox(height: 6),
                              Wrap(
                                spacing: 6,
                                runSpacing: 6,
                                children: [
                                  Pill(
                                    '${c['members']} ${plural(c['members'] as num? ?? 0, 'участник', 'участника', 'участников')}',
                                    icon: Icons.group,
                                  ),
                                  Pill(accessName(context, c['access'] as String?), color: V.muted),
                                  if (mine.contains(c['slug']))
                                    const Pill('вы в нём', icon: Icons.check, color: V.violet),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              const SizedBox(height: 10),
              GhostButton(
                'Создать сообщество на сайте',
                icon: Icons.open_in_new,
                onPressed: () => openSite(context, '/communities'),
              ),
            ],
          );
        },
      ),
    );
  }
}

class CommunityScreen extends StatefulWidget {
  const CommunityScreen({super.key, required this.slug});

  final String slug;

  @override
  State<CommunityScreen> createState() => _CommunityScreenState();
}

class _CommunityScreenState extends State<CommunityScreen> {
  Key _loader = UniqueKey();
  bool _busy = false;

  void _reload() {
    setState(() => _loader = UniqueKey());
    SessionScope.read(context).refreshMe();
  }

  /// The rules first (when there are any), and the invite code for an invite-only community.
  Future<void> _join(Json c) async {
    final rules = (c['rules'] as String? ?? '').trim();
    final invite = c['access'] == 'invite';
    String code = '';
    if (rules.isNotEmpty || invite) {
      final res = await showDialog<String>(
        context: context,
        builder: (_) => _JoinDialog(rules: rules, invite: invite),
      );
      if (res == null || !mounted) return;
      code = res;
    }
    setState(() => _busy = true);
    try {
      final out = await SessionScope.read(context).api
          .post('/communities/${widget.slug}/join', {'accept_rules': true, if (code.isNotEmpty) 'code': code});
      if (!mounted) return;
      snack(context, switch (out['result']) {
        'joined' => 'Вы в сообществе «${c['name']}».',
        'requested' => 'Заявка отправлена: её рассмотрит основатель или модератор.',
        'pending' => 'Заявка уже ждёт решения.',
        _ => 'Вы уже в сообществе.',
      });
      _reload();
    } on ApiException catch (e) {
      if (mounted) {
        snack(
          context,
          e.body?['result'] == 'need_code' ? 'Код не подошёл: возьмите его из ссылки-приглашения.' : e.message,
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _leave(Json c, {required bool request}) async {
    if (!request) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (d) => AlertDialog(
          backgroundColor: V.panel2,
          title: Text('Выйти из «${c['name']}»?'),
          content: const Text('Вернуться можно в любой момент — если сообщество открытое, без заявки.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Остаться')),
            FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Выйти')),
          ],
        ),
      );
      if (ok != true || !mounted) return;
    }
    setState(() => _busy = true);
    try {
      await SessionScope.read(context).api.post('/communities/${widget.slug}/leave');
      if (mounted) {
        snack(context, request ? 'Заявка отозвана.' : 'Вы вышли из сообщества.');
        _reload();
      }
    } on ApiException catch (e) {
      if (mounted) snack(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _membership(Json c, Json? me) {
    final s = SessionScope.of(context);
    final roles = ((s.catalog['social'] as Json?)?['roles'] as Json?) ?? const {};
    if (!s.signedIn) return Text('Войдите, чтобы вступить.', style: V.body(13.5, color: V.muted));
    if (me == null) {
      return GradientButton(
        c['access'] == 'request' ? 'Подать заявку' : 'Вступить',
        icon: Icons.group_add,
        busy: _busy,
        onPressed: () => _join(c),
      );
    }
    if (me['status'] != 'active') {
      return Row(
        children: [
          const Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: Pill('Заявка ждёт решения', icon: Icons.hourglass_empty, color: V.amber),
            ),
          ),
          TextButton(onPressed: _busy ? null : () => _leave(c, request: true), child: const Text('Отозвать')),
        ],
      );
    }
    final role = '${roles[me['role']] ?? me['role']}';
    if (me['role'] == 'owner') {
      return Align(
        alignment: Alignment.centerLeft,
        child: Pill('Вы ${role.toLowerCase()}', icon: Icons.star, color: V.violet),
      );
    }
    return Row(
      children: [
        Expanded(
          child: Align(
            alignment: Alignment.centerLeft,
            child: Pill('Вы в сообществе · ${role.toLowerCase()}', icon: Icons.check, color: V.violet),
          ),
        ),
        TextButton(onPressed: _busy ? null : () => _leave(c, request: false), child: const Text('Выйти')),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final roles = ((s.catalog['social'] as Json?)?['roles'] as Json?) ?? const {};
    final access = ((s.catalog['social'] as Json?)?['access'] as Json?) ?? const {};
    return Scaffold(
      appBar: AppBar(
        title: const Text('Сообщество'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) => v == 'site'
                ? openSite(context, '/c/${widget.slug}')
                : report(context, target: 'community', slug: widget.slug, what: 'Сообщество'),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'site', child: Text('Открыть на сайте')),
              PopupMenuItem(value: 'report', child: Text('Пожаловаться')),
            ],
          ),
        ],
      ),
      body: Loader<Json>(
        key: _loader,
        load: () => s.api.get('/communities/${widget.slug}'),
        builder: (context, data, reload) {
          final c = data['community'] as Json;
          final me = data['me'] as Json?;
          final rating = ((data['rating'] as List?) ?? const []).cast<Json>();
          final people = ((c['people'] as List?) ?? const []).cast<Json>();
          final a = access[c['access']] as Json?;
          final owner = c['owner'] as Json?;
          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              Row(
                children: [
                  CommunityEmblem(icon: c['icon'] as String?, hue: c['hue'] as num? ?? 190, size: 60),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(c['name'] as String, style: V.display(19)),
                        const SizedBox(height: 2),
                        Text(
                          '${c['members']} ${plural(c['members'] as num? ?? 0, 'участник', 'участника', 'участников')}'
                          '${owner != null ? ' · основатель: ${owner['display_name']}' : ''}',
                          style: V.body(13, color: V.muted),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if ((c['description'] as String? ?? '').isNotEmpty) ...[
                const SizedBox(height: 14),
                Text(c['description'] as String, style: V.body(15)),
              ],
              if (a != null) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    Icon(vIcon(a['icon'] as String?), size: 16, color: V.muted),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text('${a['name']}. ${a['desc']}', style: V.body(12.5, color: V.muted)),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 14),
              _membership(c, me),
              if ((c['rules'] as String? ?? '').trim().isNotEmpty) ...[
                const SectionTitle('Правила', icon: Icons.gavel),
                Panel(child: Text((c['rules'] as String).trim(), style: V.body(14))),
              ],
              SectionTitle(
                'Рейтинг сезона',
                icon: Icons.emoji_events,
                trailing: Text('${rating.length}', style: V.mono(12)),
              ),
              if (rating.isEmpty)
                Text('Пока никто из участников не судил в этом сезоне.', style: V.body(13.5, color: V.muted)),
              for (final r in rating) RatingRow(row: r, me: s.user?['login']),
              const SectionTitle('Участники', icon: Icons.group),
              for (final p in people)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  onTap: () => openProfile(context, p['login'] as String),
                  leading: Avatar(p['display_name'] as String, size: 36),
                  title: Text(p['display_name'] as String, style: V.body(14.5, weight: FontWeight.w700)),
                  subtitle: Text('@${p['login']}', style: V.body(12, color: V.muted)),
                  trailing: p['role'] == 'member'
                      ? null
                      : Pill('${roles[p['role']] ?? p['role']}', color: p['role'] == 'owner' ? V.amber : V.violet),
                ),
            ],
          );
        },
      ),
    );
  }
}

/// Accepting the rules, and the code for an invite-only community (the whole invite link can be pasted too).
class _JoinDialog extends StatefulWidget {
  const _JoinDialog({required this.rules, required this.invite});

  final String rules;
  final bool invite;

  @override
  State<_JoinDialog> createState() => _JoinDialogState();
}

class _JoinDialogState extends State<_JoinDialog> {
  bool _accepted = false;
  final _code = TextEditingController();

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  String get _codeValue {
    final v = _code.text.trim();
    return Uri.tryParse(v)?.queryParameters['code'] ?? v;
  }

  @override
  Widget build(BuildContext context) {
    final ready = (widget.rules.isEmpty || _accepted) && (!widget.invite || _codeValue.isNotEmpty);
    return AlertDialog(
      backgroundColor: V.panel2,
      title: Text(widget.rules.isNotEmpty ? 'Правила сообщества' : 'Код приглашения'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (widget.rules.isNotEmpty) ...[
              Text(widget.rules, style: V.body(14)),
              const SizedBox(height: 8),
              CheckboxListTile(
                value: _accepted,
                onChanged: (v) => setState(() => _accepted = v == true),
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
                title: const Text('Принимаю правила'),
              ),
            ],
            if (widget.invite)
              TextField(
                controller: _code,
                onChanged: (_) => setState(() {}),
                decoration: const InputDecoration(
                  labelText: 'Код или ссылка-приглашение',
                  helperText: 'В это сообщество входят по приглашению.',
                ),
              ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
        FilledButton(onPressed: ready ? () => Navigator.pop(context, _codeValue) : null, child: const Text('Вступить')),
      ],
    );
  }
}
