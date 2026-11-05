// «Войти» / «Аккаунт»: sign in or sign up (the phone's progress joins the account), notifications, the server.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../session.dart';
import '../theme.dart';
import '../widgets.dart';
import 'profile.dart';

class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return s.signedIn ? const _Signed() : const _SignIn();
  }
}

class _SignIn extends StatefulWidget {
  const _SignIn();

  @override
  State<_SignIn> createState() => _SignInState();
}

class _SignInState extends State<_SignIn> {
  bool _register = false;
  bool _busy = false;
  String? _error;
  final _login = TextEditingController();
  final _name = TextEditingController();
  final _password = TextEditingController();

  @override
  void dispose() {
    _login.dispose();
    _name.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final s = SessionScope.read(context);
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      if (_register) {
        await s.register(_login.text.trim(), _name.text.trim(), _password.text);
      } else {
        await s.signIn(_login.text.trim(), _password.text);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              _register
                  ? 'Аккаунт создан. Ваш прогресс теперь в нём.'
                  : 'Вы вошли. Прогресс телефона добавлен в аккаунт.',
            ),
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
    children: [
      Text(_register ? 'Регистрация' : 'Вход', style: V.display(24, weight: FontWeight.w900)),
      const SizedBox(height: 6),
      Text(
        'Один аккаунт на сайте и в приложении: рейтинг, друзья, сообщества и обсуждения. Вердикты, сделанные на этом телефоне, останутся вашими.',
        style: V.body(13.5, color: V.muted),
      ),
      const SizedBox(height: 16),
      SegmentedButton<bool>(
        segments: const [
          ButtonSegment(value: false, label: Text('Вход')),
          ButtonSegment(value: true, label: Text('Регистрация')),
        ],
        selected: {_register},
        onSelectionChanged: (v) => setState(() {
          _register = v.first;
          _error = null;
        }),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _login,
        autocorrect: false,
        textInputAction: TextInputAction.next,
        decoration: const InputDecoration(labelText: 'Логин', prefixIcon: Icon(Icons.alternate_email)),
      ),
      if (_register) ...[
        const SizedBox(height: 12),
        TextField(
          controller: _name,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(labelText: 'Имя или ник', prefixIcon: Icon(Icons.badge_outlined)),
        ),
      ],
      const SizedBox(height: 12),
      TextField(
        controller: _password,
        obscureText: true,
        onSubmitted: (_) => _submit(),
        decoration: InputDecoration(
          labelText: 'Пароль',
          prefixIcon: const Icon(Icons.lock_outline),
          helperText: _register ? 'Не короче 8 символов.' : null,
        ),
      ),
      if (_error != null) ...[
        const SizedBox(height: 12),
        Panel(
          accent: V.red,
          child: Row(
            children: [
              const Icon(Icons.warning_amber, color: V.red),
              const SizedBox(width: 10),
              Expanded(
                child: Text(_error!, style: V.body(14, color: const Color(0xFFFFC2CD))),
              ),
            ],
          ),
        ),
      ],
      const SizedBox(height: 18),
      GradientButton(
        _register ? 'Создать аккаунт' : 'Войти',
        icon: _register ? Icons.person_add : Icons.login,
        busy: _busy,
        onPressed: _submit,
      ),
      if (!_register) ...[
        const SizedBox(height: 12),
        Text(
          'Забыли пароль? Восстановите его на сайте — через Telegram-бот или команду.',
          textAlign: TextAlign.center,
          style: V.body(12.5, color: V.dim),
        ),
      ],
      const SizedBox(height: 26),
      const _ServerCard(),
    ],
  );
}

class _Signed extends StatefulWidget {
  const _Signed();

  @override
  State<_Signed> createState() => _SignedState();
}

class _SignedState extends State<_Signed> {
  Key _loader = UniqueKey();

  final _find = TextEditingController();

  @override
  void dispose() {
    _find.dispose();
    super.dispose();
  }

  Future<Json> _load() async {
    final s = SessionScope.read(context);
    final r = await Future.wait([s.api.get('/notifications'), s.api.get('/friends')]);
    final out = {...r[0], 'social': r[1]};
    if ((out['unread'] as num? ?? 0) > 0) {
      s.api.post('/notifications/read').then((_) => s.markRead(), onError: (_) {});
    }
    return out;
  }

  Future<void> _friend(String login, String action) async {
    try {
      await SessionScope.read(context).api.post('/friends/$login/$action');
      if (mounted) setState(() => _loader = UniqueKey());
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  List<Widget> _friends(Json social) {
    final incoming = ((social['incoming'] as List?) ?? const []).cast<Json>();
    final friends = ((social['friends'] as List?) ?? const []).cast<Json>();
    final outgoing = ((social['outgoing'] as List?) ?? const []).cast<Json>();
    Widget person(Json p, {Widget? trailing, String? sub}) => Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Panel(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        onTap: () => openProfile(context, p['login'] as String),
        child: Row(
          children: [
            Avatar(p['display_name'] as String, size: 36),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(p['display_name'] as String, style: V.body(14.5, weight: FontWeight.w800)),
                  Text(sub ?? '@${p['login']}', style: V.body(12, color: V.muted)),
                ],
              ),
            ),
            ?trailing,
          ],
        ),
      ),
    );
    return [
      SectionTitle(
        'Друзья',
        icon: Icons.group,
        trailing: Text('${friends.length}', style: V.mono(12)),
      ),
      for (final p in incoming)
        person(
          p,
          sub: 'хочет дружить',
          trailing: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                tooltip: 'Отклонить',
                onPressed: () => _friend(p['login'] as String, 'decline'),
                icon: const Icon(Icons.close, color: V.muted),
              ),
              IconButton.filled(
                tooltip: 'Принять',
                onPressed: () => _friend(p['login'] as String, 'accept'),
                style: IconButton.styleFrom(backgroundColor: V.cyan, foregroundColor: V.bg),
                icon: const Icon(Icons.check),
              ),
            ],
          ),
        ),
      for (final p in friends)
        person(
          p,
          sub: '${(p['rank'] as Json?)?['name'] ?? ''} · ${p['xp']} XP',
          trailing: (p['streak'] as num? ?? 0) > 0
              ? Pill('${p['streak']}', icon: Icons.local_fire_department, color: V.magenta)
              : null,
        ),
      for (final p in outgoing)
        person(
          p,
          sub: 'заявка отправлена',
          trailing: TextButton(onPressed: () => _friend(p['login'] as String, 'cancel'), child: const Text('Отозвать')),
        ),
      if (incoming.isEmpty && friends.isEmpty && outgoing.isEmpty)
        Text(
          'Добавьте судей в друзья — из рейтинга или по логину. Друзья видят, как вы решили то же дело, и соревнуются в своём рейтинге.',
          style: V.body(13.5, color: V.muted),
        ),
      const SizedBox(height: 8),
      TextField(
        controller: _find,
        autocorrect: false,
        textInputAction: TextInputAction.search,
        onSubmitted: (v) {
          final login = v.trim().replaceFirst('@', '');
          if (login.isNotEmpty) openProfile(context, login);
        },
        decoration: const InputDecoration(
          hintText: 'Найти судью по логину',
          prefixIcon: Icon(Icons.person_search),
          isDense: true,
        ),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final user = s.user!;
    return Loader<Json>(
      key: _loader,
      load: _load,
      builder: (context, data, reload) {
        final items = (data['items'] as List).cast<Json>();
        final social = data['social'] as Json? ?? {};
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
          children: [
            Panel(
              accent: V.cyan,
              child: Row(
                children: [
                  Avatar(user['display_name'] as String, size: 52),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(user['display_name'] as String, style: V.display(19)),
                        Text('@${user['login']}', style: V.body(13.5, color: V.muted)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            ..._friends(social),
            SectionTitle(
              'Уведомления',
              icon: Icons.notifications_outlined,
              trailing: IconButton(
                onPressed: () => setState(() => _loader = UniqueKey()),
                icon: const Icon(Icons.refresh, color: V.muted),
              ),
            ),
            if (items.isEmpty)
              Panel(
                child: Text(
                  'Пока тихо. Здесь появятся заявки в друзья, ответы сообществ, трофеи сезонов и поддержка ваших комментариев.',
                  style: V.body(14, color: V.muted),
                ),
              ),
            for (final n in items)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Panel(
                  accent: n['read'] == true ? null : V.magenta,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(vIcon(n['icon'] as String?), color: V.cyan, size: 20),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(n['text'] as String, style: V.body(14.5)),
                            const SizedBox(height: 4),
                            Text(
                              ruDate(n['created_at'] as String, time: true) + (n['read'] == true ? '' : ' · новое'),
                              style: V.body(12, color: n['read'] == true ? V.dim : V.magenta),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 22),
            GhostButton(
              'Выйти из аккаунта',
              icon: Icons.logout,
              onPressed: () async {
                final ok = await showDialog<bool>(
                  context: context,
                  builder: (c) => AlertDialog(
                    backgroundColor: V.panel2,
                    title: const Text('Выйти?'),
                    content: const Text(
                      'Телефон начнёт играть новым анонимным судьёй. Войдите снова — и всё вернётся.',
                    ),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Остаться')),
                      FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Выйти')),
                    ],
                  ),
                );
                if (ok == true) await s.signOut();
              },
            ),
            const SizedBox(height: 26),
            const _ServerCard(),
          ],
        );
      },
    );
  }
}

class _ServerCard extends StatefulWidget {
  const _ServerCard();

  @override
  State<_ServerCard> createState() => _ServerCardState();
}

class _ServerCardState extends State<_ServerCard> {
  bool _open = false;
  final _url = TextEditingController();

  @override
  void initState() {
    super.initState();
    _url.text = SessionScope.read(context).server;
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => setState(() => _open = !_open),
            child: Row(
              children: [
                const Icon(Icons.dns_outlined, size: 18, color: V.muted),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Сервер: ${Uri.tryParse(s.server)?.host ?? s.server}',
                    style: V.body(13.5, color: V.muted),
                  ),
                ),
                Icon(_open ? Icons.expand_less : Icons.expand_more, color: V.muted),
              ],
            ),
          ),
          if (_open) ...[
            const SizedBox(height: 12),
            TextField(
              controller: _url,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(labelText: 'Адрес сайта VERDICT'),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                TextButton(onPressed: () => _url.text = defaultServer, child: const Text('По умолчанию')),
                const Spacer(),
                FilledButton(
                  onPressed: () async {
                    await s.setServer(_url.text);
                    try {
                      await s.loadCatalog();
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Сервер на связи.')));
                      }
                    } on ApiException catch (e) {
                      if (context.mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                      }
                    }
                  },
                  child: const Text('Сохранить'),
                ),
              ],
            ),
          ],
          const SizedBox(height: 6),
          Text('VERDICT 1.1 · игрок ${s.api.voterId.substring(0, 6)}…', style: V.body(11.5, color: V.dim)),
        ],
      ),
    );
  }
}
