// «Судья»: the judge style, how the player's verdicts move the world, the career, achievements and the world itself.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'home.dart';

class JudgeScreen extends StatefulWidget {
  const JudgeScreen({super.key});

  @override
  State<JudgeScreen> createState() => _JudgeScreenState();
}

class _JudgeScreenState extends State<JudgeScreen> {
  Key _loader = UniqueKey();

  Future<(Json, Json)> _load() async {
    final api = SessionScope.read(context).api;
    final r = await Future.wait([api.get('/profile'), api.get('/world')]);
    return (r[0], r[1]['world'] as Json);
  }

  Future<void> _reset() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        backgroundColor: V.panel2,
        title: const Text('Начать мир заново?'),
        content: const Text('Показатели мира вернутся к 50, события забудутся. Вердикты, опыт, ранг и достижения останутся.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Оставить')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Начать заново')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await SessionScope.read(context).api.post('/world/reset');
    setState(() => _loader = UniqueKey());
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final metrics = s.metrics();
    final achievementsDict = s.catalog['achievements'] as Json? ?? {};
    return Loader<(Json, Json)>(
      key: _loader,
      load: _load,
      builder: (context, data, reload) {
        final profile = data.$1['profile'] as Json;
        final career = data.$1['career'] as Json;
        final world = data.$2;
        final style = profile['archetype'] as Json?;
        final leans = profile['leans'] as Json? ?? {};
        final unlocked = ((career['achievements'] as List?) ?? const []).cast<Json>();
        final have = {for (final a in unlocked) if (a['unlocked'] == true) a['key']};
        final min = (s.catalog['judge'] as Json?)?['min_verdicts'] as num? ?? 5;
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
          children: [
            Text('Профиль судьи', style: V.display(24, weight: FontWeight.w900)),
            const SizedBox(height: 14),
            RankCard(career: career),
            const SizedBox(height: 12),
            if (style != null)
              Panel(
                accent: V.violet,
                padding: const EdgeInsets.all(18),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Icon(vIcon(style['icon'] as String?), color: V.violet, size: 30),
                    const SizedBox(width: 12),
                    Expanded(child: Text(style['name'] as String, style: V.display(20))),
                  ]),
                  const SizedBox(height: 10),
                  Text(style['desc'] as String? ?? '', style: V.body(14.5)),
                  if ((style['strength'] as String? ?? '').isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text('Сильная сторона', style: V.body(12, weight: FontWeight.w800, color: V.green)),
                    Text(style['strength'] as String, style: V.body(13.5, color: V.muted)),
                  ],
                  if ((style['blind'] as String? ?? '').isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text('Слепое пятно', style: V.body(12, weight: FontWeight.w800, color: V.amber)),
                    Text(style['blind'] as String, style: V.body(13.5, color: V.muted)),
                  ],
                ]),
              )
            else
              Panel(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Какой вы судья?', style: V.display(18)),
                  const SizedBox(height: 6),
                  Text('Стиль откроется после $min вердиктов. Осталось: ${profile['left']}.', style: V.body(14, color: V.muted)),
                  const SizedBox(height: 10),
                  Bar(((profile['decided'] as num? ?? 0) / min).toDouble()),
                ]),
              ),
            const SectionTitle('Куда вы ведёте мир', icon: Icons.tune),
            Text('Насколько ваши решения поднимают или опускают показатель по сравнению с другими вариантами тех же дел.',
                style: V.body(12.5, color: V.dim)),
            const SizedBox(height: 10),
            for (final e in metrics.entries) _Lean(name: (e.value as Json)['name'] as String, icon: (e.value as Json)['icon'] as String?,
                lean: ((leans[e.key] as Json?)?['lean'] as num? ?? 0).toDouble()),
            SectionTitle('Ваш мир', icon: Icons.public, trailing: TextButton(onPressed: _reset, child: const Text('Заново'))),
            Text('${world['count']} ${plural(world['count'] as num, 'вердикт', 'вердикта', 'вердиктов')} '
                '${plural(world['count'] as num, 'изменил', 'изменили', 'изменили')} его.',
                style: V.body(12.5, color: V.dim)),
            const SizedBox(height: 10),
            for (final e in metrics.entries) _Meter(name: (e.value as Json)['name'] as String, icon: (e.value as Json)['icon'] as String?,
                value: ((world['metrics'] as Json)[e.key] as num? ?? 50).toDouble()),
            for (final ev in ((world['active'] as List?) ?? const []).cast<Json>())
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Panel(
                  accent: ev['tone'] == 'up' ? V.green : V.red,
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(vIcon(ev['icon'] as String?), color: ev['tone'] == 'up' ? V.green : V.red),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(ev['name'] as String, style: V.body(14.5, weight: FontWeight.w800)),
                        Text(ev['text'] as String? ?? '', style: V.body(13, color: V.muted)),
                      ]),
                    ),
                  ]),
                ),
              ),
            SectionTitle('Достижения', icon: Icons.emoji_events, trailing: Text('${have.length}/${achievementsDict.length}', style: V.mono(12))),
            GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: .9,
              children: [
                for (final e in achievementsDict.entries)
                  Tooltip(
                    message: (e.value as Json)['desc'] as String? ?? '',
                    triggerMode: TooltipTriggerMode.tap,
                    child: Opacity(
                      opacity: have.contains(e.key) ? 1 : .35,
                      child: Panel(
                        accent: have.contains(e.key) ? V.amber : null,
                        padding: const EdgeInsets.all(8),
                        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                          Icon(vIcon((e.value as Json)['icon'] as String?), color: have.contains(e.key) ? V.amber : V.muted),
                          const SizedBox(height: 6),
                          Text((e.value as Json)['name'] as String, textAlign: TextAlign.center, maxLines: 2,
                              overflow: TextOverflow.ellipsis, style: V.body(11.5, weight: FontWeight.w700)),
                        ]),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        );
      },
    );
  }
}

class _Lean extends StatelessWidget {
  const _Lean({required this.name, required this.icon, required this.lean});

  final String name;
  final String? icon;
  final double lean;

  @override
  Widget build(BuildContext context) {
    final up = lean >= 0;
    final pct = (lean * 100).round();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(children: [
        Icon(vIcon(icon), size: 16, color: V.muted),
        const SizedBox(width: 8),
        SizedBox(width: 112, child: Text(name, style: V.body(13, weight: FontWeight.w700))),
        Expanded(
          child: LayoutBuilder(builder: (context, box) {
            final half = box.maxWidth / 2;
            final w = half * lean.abs().clamp(0, 1);
            return Stack(alignment: Alignment.center, children: [
              Container(height: 8, decoration: BoxDecoration(color: Colors.white.withValues(alpha: .06), borderRadius: BorderRadius.circular(4))),
              Container(width: 1.5, height: 14, color: V.dim),
              Positioned(
                left: up ? half : half - w,
                child: Container(width: w, height: 8, decoration: BoxDecoration(
                    color: up ? const Color(0xFF3987E5) : const Color(0xFFD95926), borderRadius: BorderRadius.circular(4))),
              ),
            ]);
          }),
        ),
        SizedBox(
            width: 46,
            child: Text(pct == 0 ? '0%' : '${up ? '+' : '−'}${pct.abs()}%', textAlign: TextAlign.right, style: V.body(12.5, color: V.muted))),
      ]),
    );
  }
}

class _Meter extends StatelessWidget {
  const _Meter({required this.name, required this.icon, required this.value});

  final String name;
  final String? icon;
  final double value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          Icon(vIcon(icon), size: 16, color: V.muted),
          const SizedBox(width: 8),
          SizedBox(width: 112, child: Text(name, style: V.body(13, weight: FontWeight.w700))),
          Expanded(child: Bar(value / 100, color: value <= 20 ? V.red : (value >= 80 ? V.green : null))),
          SizedBox(width: 40, child: Text('${value.round()}', textAlign: TextAlign.right, style: V.display(13))),
        ]),
      );
}
