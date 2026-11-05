// Another judge's public profile — as much as its owner shows everyone — and the friendship button.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../links.dart';
import '../main.dart';
import '../report.dart';
import '../theme.dart';
import '../widgets.dart';
import 'communities.dart';

void openProfile(BuildContext context, String login) =>
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ProfileScreen(login: login)));

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key, required this.login});

  final String login;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

/// self | friends | incoming | outgoing | none | guest
class _Data {
  _Data(this.user, this.relation);

  final Json user;
  final String relation;
}

class _ProfileScreenState extends State<ProfileScreen> {
  Key _loader = UniqueKey();
  bool _busy = false;

  Future<_Data> _load() async {
    final s = SessionScope.read(context);
    final user = (await s.api.get('/users/${widget.login}'))['user'] as Json;
    if (!s.signedIn) return _Data(user, 'guest');
    if (s.user!['login'] == widget.login) return _Data(user, 'self');
    final f = await s.api.get('/friends');
    bool has(String key) => ((f[key] as List?) ?? const []).any((x) => (x as Json)['login'] == widget.login);
    return _Data(
      user,
      has('friends') ? 'friends' : (has('incoming') ? 'incoming' : (has('outgoing') ? 'outgoing' : 'none')),
    );
  }

  Future<void> _act(String action) async {
    final api = SessionScope.read(context).api;
    setState(() => _busy = true);
    try {
      final out = action == 'add'
          ? await api.post('/friends', {'login': widget.login})
          : await api.post('/friends/${widget.login}/$action');
      if (mounted) {
        final msg = {
          'add': out['result'] == 'accepted' ? 'Теперь вы друзья.' : 'Заявка отправлена.',
          'accept': 'Теперь вы друзья.',
          'cancel': 'Заявка отозвана.',
          'remove': 'Больше не друзья.',
        }[action]!;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
        setState(() => _loader = UniqueKey());
      }
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _friendButton(String relation) => switch (relation) {
    'self' => const Pill('Это вы', icon: Icons.person, color: V.cyan),
    'guest' => Text('Войдите, чтобы добавить судью в друзья.', style: V.body(13, color: V.muted)),
    'friends' => GhostButton(
      'В друзьях — убрать',
      icon: Icons.person_remove_alt_1,
      onPressed: _busy ? null : () => _act('remove'),
    ),
    'incoming' => GradientButton(
      'Принять заявку в друзья',
      icon: Icons.person_add,
      busy: _busy,
      onPressed: () => _act('accept'),
    ),
    'outgoing' => GhostButton(
      'Заявка отправлена — отозвать',
      icon: Icons.undo,
      onPressed: _busy ? null : () => _act('cancel'),
    ),
    _ => GradientButton('Добавить в друзья', icon: Icons.person_add_alt_1, busy: _busy, onPressed: () => _act('add')),
  };

  @override
  Widget build(BuildContext context) {
    final achievementsDict = SessionScope.of(context).catalog['achievements'] as Json? ?? {};
    return Scaffold(
      appBar: AppBar(
        title: Text('@${widget.login}'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (v) => v == 'site'
                ? openSite(context, '/u/${widget.login}')
                : report(context, target: 'user', login: widget.login, what: 'Судья @${widget.login}'),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'site', child: Text('Открыть на сайте')),
              PopupMenuItem(value: 'report', child: Text('Пожаловаться')),
            ],
          ),
        ],
      ),
      body: Loader<_Data>(
        key: _loader,
        load: _load,
        builder: (context, data, reload) {
          final u = data.user;
          final rank = u['rank'] as Json?;
          final style = u['style'] as Json?;
          final trophies = ((u['trophies'] as List?) ?? const []).cast<Json>();
          final communities = ((u['communities'] as List?) ?? const []).cast<Json>();
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
            children: [
              Row(
                children: [
                  Avatar(u['display_name'] as String, size: 64),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(u['display_name'] as String, style: V.display(20)),
                        Text(
                          '@${u['login']} · ${u['friends']} ${plural(u['friends'] as num, 'друг', 'друга', 'друзей')}',
                          style: V.body(13, color: V.muted),
                        ),
                        if ((u['title'] as String?)?.isNotEmpty == true) ...[
                          const SizedBox(height: 6),
                          Pill(u['title'] as String, icon: Icons.sell, color: V.amber, wrap: true),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _friendButton(data.relation),
              if (u['visible'] != true) ...[
                const SizedBox(height: 24),
                const Icon(Icons.lock_outline, color: V.muted, size: 36),
                const SizedBox(height: 8),
                Text(
                  'Судья показывает профиль только друзьям — или никому.',
                  textAlign: TextAlign.center,
                  style: V.body(14, color: V.muted),
                ),
              ] else ...[
                if ((u['bio'] as String? ?? '').isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Text(u['bio'] as String, style: V.body(15)),
                ],
                const SizedBox(height: 14),
                if (rank != null)
                  Panel(
                    accent: V.cyan,
                    child: Row(
                      children: [
                        Icon(vIcon(rank['icon'] as String?), color: V.cyan, size: 28),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(rank['name'] as String, style: V.display(17)),
                              const SizedBox(height: 6),
                              Bar((rank['progress'] as num? ?? 0).toDouble()),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text('${u['xp']} XP', style: V.display(15, color: V.cyan)),
                      ],
                    ),
                  ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(child: _Stat('${u['verdicts']}', 'вердиктов')),
                    const SizedBox(width: 8),
                    Expanded(child: _Stat('${u['streak']}', 'дней подряд')),
                    const SizedBox(width: 8),
                    Expanded(child: _Stat(u['season_place'] == null ? '—' : '${u['season_place']}', 'место в сезоне')),
                  ],
                ),
                if (style != null) ...[
                  const SectionTitle('Стиль', icon: Icons.balance),
                  Panel(
                    accent: V.violet,
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(vIcon(style['icon'] as String?), color: V.violet),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(style['name'] as String, style: V.body(15.5, weight: FontWeight.w800)),
                              Text(style['desc'] as String? ?? '', style: V.body(13.5, color: V.muted)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                if (trophies.isNotEmpty) ...[
                  const SectionTitle('Трофеи', icon: Icons.emoji_events),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final t in trophies)
                        Pill(t['name'] as String, icon: vIcon(t['icon'] as String?), color: V.amber, wrap: true),
                    ],
                  ),
                ],
                const SectionTitle('Достижения', icon: Icons.military_tech),
                Text(
                  '${((u['achievements'] as List?) ?? const []).length} из ${achievementsDict.length}',
                  style: V.body(14, color: V.muted),
                ),
                if (communities.isNotEmpty) ...[
                  const SectionTitle('Сообщества', icon: Icons.groups),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final c in communities)
                        InkWell(
                          borderRadius: BorderRadius.circular(999),
                          onTap: () => openCommunity(context, c['slug'] as String),
                          child: Pill(c['name'] as String, icon: Icons.groups, color: V.violet),
                        ),
                    ],
                  ),
                ],
              ],
            ],
          );
        },
      ),
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(this.value, this.label);

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Panel(
    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
    child: Column(
      children: [
        Text(value, style: V.display(17)),
        const SizedBox(height: 2),
        Text(
          label,
          textAlign: TextAlign.center,
          style: V.body(11.5, color: V.muted),
        ),
      ],
    ),
  );
}
