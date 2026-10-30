// «Играть»: the rank and its progress, the case of the day, Быстрый суд, the player's world at a glance.
import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'case_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.onTab});

  final void Function(int tab) onTab;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Key _loader = UniqueKey();

  Future<(Json, Json)> _load() async {
    final api = SessionScope.read(context).api;
    final r = await Future.wait([api.get('/profile'), api.get('/daily')]);
    return (r[0], r[1]);
  }

  void _refresh() => setState(() => _loader = UniqueKey());

  Future<void> _quick() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const QuickRun()));
    _refresh();
  }

  Future<void> _openCase(int id, {bool quick = true}) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => CaseScreen(caseId: id, quick: quick)));
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    return Loader<(Json, Json)>(
      key: _loader,
      load: _load,
      builder: (context, data, reload) {
        final career = data.$1['career'] as Json;
        final profile = data.$1['profile'] as Json;
        final daily = data.$2;
        final quick = profile['quick'] as Json? ?? {};
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
          children: [
            Row(children: [
              Text('VERDICT', style: V.display(22, weight: FontWeight.w900)),
              const Spacer(),
              if (s.signedIn)
                IconButton(
                  tooltip: 'Уведомления',
                  onPressed: () => widget.onTab(4),
                  icon: Badge(
                      isLabelVisible: s.unread > 0,
                      label: Text('${s.unread}'),
                      backgroundColor: V.magenta,
                      child: const Icon(Icons.notifications_outlined, color: V.muted)),
                ),
            ]),
            const SizedBox(height: 4),
            Text(s.signedIn ? 'Добро пожаловать, ${s.user!['display_name']}.' : 'Нет правильного ответа. Есть только твой вердикт.',
                style: V.body(14, color: V.muted)),
            const SizedBox(height: 16),
            RankCard(career: career, onTap: () => widget.onTab(2)),
            const SizedBox(height: 12),
            if (daily['case'] != null) DailyCard(daily: daily, onOpen: () => _openCase((daily['case'] as Json)['id'] as int)),
            const SizedBox(height: 16),
            GradientButton('Быстрый суд', icon: Icons.play_arrow, onPressed: _quick),
            const SizedBox(height: 10),
            Text('Вердикт за минуту: прочтите дело, решите и угадайте, как решило большинство.',
                textAlign: TextAlign.center, style: V.body(12.5, color: V.dim)),
            const SizedBox(height: 18),
            Row(children: [
              Expanded(child: _Stat(icon: Icons.gavel, value: '${profile['verdicts'] ?? 0}', label: 'вердиктов')),
              const SizedBox(width: 10),
              Expanded(child: _Stat(icon: Icons.track_changes, value: '${quick['score'] ?? 0}/${quick['guesses'] ?? 0}', label: 'угадано')),
              const SizedBox(width: 10),
              Expanded(child: _Stat(icon: Icons.local_fire_department, value: '${career['streak'] ?? 0}', label: 'дней подряд')),
            ]),
            if (!s.signedIn) ...[
              const SizedBox(height: 18),
              Panel(
                accent: V.violet,
                onTap: () => widget.onTab(4),
                child: Row(children: [
                  const Icon(Icons.person_add_alt, color: V.violet),
                  const SizedBox(width: 12),
                  Expanded(
                      child: Text('Заведите аккаунт — попадёте в рейтинг, сохраните прогресс и будете играть на сайте и в приложении одним судьёй.',
                          style: V.body(13.5, color: V.muted))),
                ]),
              ),
            ],
          ],
        );
      },
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.icon, required this.value, required this.label});

  final IconData icon;
  final String value;
  final String label;

  @override
  Widget build(BuildContext context) => Panel(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        child: Column(children: [
          Icon(icon, size: 18, color: V.cyan),
          const SizedBox(height: 6),
          Text(value, style: V.display(17)),
          Text(label, style: V.body(11.5, color: V.muted), textAlign: TextAlign.center),
        ]),
      );
}

class RankCard extends StatelessWidget {
  const RankCard({super.key, required this.career, this.onTap});

  final Json career;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final rank = career['rank'] as Json;
    final next = rank['next'] as Json?;
    return Panel(
      accent: V.cyan,
      onTap: onTap,
      child: Row(children: [
        Container(
          width: 54,
          height: 54,
          decoration: BoxDecoration(gradient: V.grad, borderRadius: BorderRadius.circular(16)),
          child: Icon(vIcon(rank['icon'] as String?), color: Colors.white, size: 28),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Kicker('Карьера судьи'),
            const SizedBox(height: 4),
            Text(rank['name'] as String, style: V.display(18)),
            const SizedBox(height: 8),
            Bar((rank['progress'] as num).toDouble()),
            const SizedBox(height: 6),
            Text(next == null ? '${career['xp']} XP · высший ранг' : '${career['xp']} XP · до «${next['name']}» ${rank['to_next']} XP',
                style: V.body(12.5, color: V.muted)),
          ]),
        ),
      ]),
    );
  }
}

class DailyCard extends StatefulWidget {
  const DailyCard({super.key, required this.daily, required this.onOpen});

  final Json daily;
  final VoidCallback onOpen;

  @override
  State<DailyCard> createState() => _DailyCardState();
}

class _DailyCardState extends State<DailyCard> {
  late int _left = (widget.daily['seconds_left'] as num?)?.toInt() ?? 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _left > 0) setState(() => _left--);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.daily['case'] as Json;
    final cat = SessionScope.of(context).category(c['category'] as String?);
    final done = widget.daily['bonus_taken'] == true;
    final judged = widget.daily['judged'] == true;
    final h = _left ~/ 3600, m = (_left % 3600) ~/ 60, sec = _left % 60;
    String two(int v) => v.toString().padLeft(2, '0');
    return Panel(
      accent: V.amber,
      onTap: judged ? null : widget.onOpen,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.calendar_today, size: 16, color: V.amber),
          const SizedBox(width: 8),
          Text('ДЕЛО ДНЯ', style: V.mono(11, color: V.amber)),
          const Spacer(),
          Text('${two(h)}:${two(m)}:${two(sec)}', style: V.mono(12, color: V.amber)),
        ]),
        const SizedBox(height: 10),
        Text(c['title'] as String, style: V.display(19)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 6, children: [
          Pill(cat['name'] as String, icon: vIcon(cat['icon'] as String?), color: V.hue(cat['hue'] as num? ?? 190)),
          if (done)
            const Pill('Бонус получен', icon: Icons.check, color: V.green)
          else if (judged)
            const Pill('Вы его уже судили', icon: Icons.check, color: V.muted)
          else
            Pill('+${widget.daily['bonus_xp']} XP сегодня', icon: Icons.bolt, color: V.amber),
        ]),
        if (!judged) ...[
          const SizedBox(height: 12),
          Row(children: [
            Text('Рассудить', style: V.body(14, weight: FontWeight.w800, color: V.amber)),
            const SizedBox(width: 4),
            const Icon(Icons.arrow_forward, size: 18, color: V.amber),
          ]),
        ],
      ]),
    );
  }
}
