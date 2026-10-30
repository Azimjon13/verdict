// After the verdict: the consequences, how everyone else decided, the guess, and what the verdict earned.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../theme.dart';
import '../widgets.dart';
import 'case_screen.dart';
import 'talk.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key, required this.result, required this.caseData, required this.quick});

  final Json result;
  final Json caseData;
  final bool quick;

  @override
  Widget build(BuildContext context) {
    final r = result['result'] as Json;
    final guess = result['guess'] as Json?;
    final career = result['career'] as Json?;
    final choice = r['choice'] as String;
    final decisions = (r['decisions'] as List).cast<Json>();
    final mine = decisions.firstWhere((d) => d['key'] == choice, orElse: () => {'key': 'other', 'text': 'Своё решение'});
    final cons = r['consequences'] as Json?;
    final ctrl = r['controversy'] as Json?;
    final amb = r['ambiguity'] as Json?;
    final majority = ((guess?['majority'] as List?) ?? const []).cast<String>();
    final total = (r['total_votes'] as num?)?.toInt() ?? 0;
    final top = decisions.fold<num>(0, (m, d) => (d['share'] as num) > m ? d['share'] as num : m);

    return Scaffold(
      appBar: AppBar(title: Text(caseData['title'] as String, overflow: TextOverflow.ellipsis)),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 28), children: [
        if (quick && guess != null) _GuessBanner(guess: guess, total: total),
        if (career != null) ...[const SizedBox(height: 12), _Rewards(career: career)],
        const SizedBox(height: 16),
        const Kicker('Ваш вердикт'),
        const SizedBox(height: 10),
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          OptionLetter(choice, active: true, size: 40),
          const SizedBox(width: 12),
          Expanded(child: Text(mine['text'] as String, style: V.display(17, weight: FontWeight.w700))),
        ]),
        if (cons != null) ...[
          const SizedBox(height: 14),
          for (final (key, title, icon) in [
            ('immediate', 'Сразу', Icons.bolt),
            ('longterm', 'Со временем', Icons.hourglass_bottom),
            ('characters', 'Люди', Icons.group),
            ('world', 'Мир', Icons.public),
          ])
            if ((cons[key] as String? ?? '').isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Panel(
                  padding: const EdgeInsets.all(14),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(icon, size: 18, color: V.amber),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(title, style: V.body(12, weight: FontWeight.w800, color: V.amber)),
                        const SizedBox(height: 2),
                        Text(cons[key] as String, style: V.body(14.5)),
                      ]),
                    ),
                  ]),
                ),
              ),
        ],
        SectionTitle('Как решили судьи', icon: Icons.bar_chart, trailing: ctrl == null ? null : Pill(ctrl['label'] as String, color: V.magenta)),
        Text('$total ${plural(total, 'вердикт', 'вердикта', 'вердиктов')}', style: V.body(13, color: V.muted)),
        const SizedBox(height: 10),
        for (final d in decisions)
          _SplitRow(d: d, mine: d['key'] == choice, leading: (d['share'] as num) == top && top > 0, majority: majority.contains(d['key'])),
        if ((r['other_votes'] as num? ?? 0) > 0)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Своё решение: ${r['other_votes']}', style: V.body(13, color: V.muted)),
          ),
        if (amb != null && (amb['conflict'] as String? ?? '').isNotEmpty) ...[
          const SectionTitle('Почему нет правильного ответа', icon: Icons.balance),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(amb['conflict'] as String, style: V.body(15, weight: FontWeight.w700)),
              if ((amb['for_one'] as String? ?? '').isNotEmpty) ...[
                const SizedBox(height: 10),
                Text('С одной стороны', style: V.body(12, weight: FontWeight.w800, color: V.cyan)),
                Text(amb['for_one'] as String, style: V.body(14, color: V.muted)),
              ],
              if ((amb['for_other'] as String? ?? '').isNotEmpty) ...[
                const SizedBox(height: 10),
                Text('С другой стороны', style: V.body(12, weight: FontWeight.w800, color: V.magenta)),
                Text(amb['for_other'] as String, style: V.body(14, color: V.muted)),
              ],
            ]),
          ),
        ],
        const SizedBox(height: 22),
        if (quick)
          GradientButton('Следующее дело', icon: Icons.arrow_forward, onPressed: () {
            Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => QuickRun(except: caseData['id'] as int)));
          }),
        const SizedBox(height: 10),
        GhostButton('Обсуждение', icon: Icons.chat_bubble_outline, onPressed: () {
          Navigator.of(context).push(MaterialPageRoute(
              builder: (_) => TalkScreen(caseId: caseData['id'] as int, title: caseData['title'] as String)));
        }),
      ]),
    );
  }
}

class _GuessBanner extends StatelessWidget {
  const _GuessBanner({required this.guess, required this.total});

  final Json guess;
  final int total;

  @override
  Widget build(BuildContext context) {
    final correct = guess['correct'];
    final (IconData icon, Color color, String title, String text) = switch (correct) {
      true => (Icons.track_changes, V.green, 'Вы угадали большинство!', '+5 XP за чутьё.'),
      false => (Icons.close, V.magenta, 'Большинство решило иначе',
          'Чаще всего выбирали: ${(guess['majority'] as List).join(', ')}.'),
      _ => (guess['key'] == null || guess['key'] == '')
          ? (Icons.visibility, V.muted, 'Вы не угадывали', 'В следующий раз попробуйте угадать: +5 XP.')
          : (Icons.flag, V.amber, 'Вы первый судья', 'Сравнить было не с кем — дальше судьи пойдут за вами.'),
    };
    return Panel(
      accent: color,
      child: Row(children: [
        Icon(icon, color: color, size: 30),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: V.display(17, color: color)),
            const SizedBox(height: 4),
            Text(text, style: V.body(13.5, color: V.muted)),
          ]),
        ),
      ]),
    );
  }
}

class _Rewards extends StatelessWidget {
  const _Rewards({required this.career});

  final Json career;

  @override
  Widget build(BuildContext context) {
    final rank = career['rank'] as Json;
    final gained = (career['xp_gained'] as num?)?.toInt() ?? 0;
    final achievements = ((career['achievements'] as List?) ?? const []).cast<Json>();
    final events = ((career['events'] as List?) ?? const []).cast<Json>();
    final next = rank['next'] as Json?;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Panel(
        accent: career['rank_up'] == true ? V.amber : V.cyan,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: gained.toDouble()),
              duration: const Duration(milliseconds: 900),
              curve: Curves.easeOutCubic,
              builder: (_, v, _) => Text('+${v.round()} XP', style: V.display(24, color: V.cyan, weight: FontWeight.w900)),
            ),
            const Spacer(),
            Icon(vIcon(rank['icon'] as String?), color: V.muted, size: 18),
            const SizedBox(width: 6),
            Text(rank['name'] as String, style: V.body(14, weight: FontWeight.w800)),
          ]),
          const SizedBox(height: 10),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: (rank['progress'] as num).toDouble()),
            duration: const Duration(milliseconds: 1100),
            curve: Curves.easeOutCubic,
            builder: (_, v, _) => Bar(v),
          ),
          const SizedBox(height: 6),
          Text(next == null ? '${career['xp']} XP' : '${career['xp']} XP · до «${next['name']}» ${rank['to_next']} XP',
              style: V.body(12.5, color: V.muted)),
          if (career['rank_up'] == true || career['streak_up'] == true || career['daily'] == true) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 6, children: [
              if (career['rank_up'] == true) Pill('Новый ранг: ${rank['name']}', icon: Icons.military_tech, color: V.amber, filled: true),
              if (career['streak_up'] == true)
                Pill('${career['streak']} ${plural(career['streak'] as num, 'день', 'дня', 'дней')} подряд',
                    icon: Icons.local_fire_department, color: V.magenta),
              if (career['daily'] == true) const Pill('Дело дня: +15 XP', icon: Icons.calendar_today, color: V.amber),
            ]),
          ],
        ]),
      ),
      for (final a in achievements)
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Panel(
            accent: V.amber,
            child: Row(children: [
              Icon(vIcon(a['icon'] as String?), color: V.amber, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Достижение: ${a['name']}', style: V.body(15, weight: FontWeight.w800, color: V.amber)),
                  Text(a['desc'] as String? ?? '', style: V.body(13, color: V.muted)),
                ]),
              ),
            ]),
          ),
        ),
      for (final e in events)
        Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Panel(
            accent: e['tone'] == 'up' ? V.green : V.red,
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(vIcon(e['icon'] as String?), color: e['tone'] == 'up' ? V.green : V.red),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${e['meter_name']}: ${e['name']}', style: V.body(15, weight: FontWeight.w800)),
                  Text(e['text'] as String? ?? '', style: V.body(13, color: V.muted)),
                ]),
              ),
            ]),
          ),
        ),
    ]);
  }
}

class _SplitRow extends StatelessWidget {
  const _SplitRow({required this.d, required this.mine, required this.leading, required this.majority});

  final Json d;
  final bool mine;
  final bool leading;
  final bool majority;

  @override
  Widget build(BuildContext context) {
    final share = (d['share'] as num).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        OptionLetter(d['key'] as String, size: 28, active: mine),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                  child: Text(d['text'] as String,
                      style: V.body(13.5, weight: mine ? FontWeight.w800 : FontWeight.w600, color: mine ? V.text : V.muted))),
              const SizedBox(width: 8),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: share * 100),
                duration: const Duration(milliseconds: 900),
                builder: (_, v, _) => Text('${v.round()}%', style: V.display(14, color: mine ? V.cyan : V.text)),
              ),
            ]),
            const SizedBox(height: 6),
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: share),
              duration: const Duration(milliseconds: 900),
              curve: Curves.easeOutCubic,
              builder: (_, v, _) => Bar(v, height: 7, color: mine ? null : (leading ? V.violet : V.dim), gradient: mine),
            ),
            if (mine || majority)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text([if (mine) 'ваш вердикт', if (majority) 'большинство до вас'].join(' · '),
                    style: V.body(11.5, weight: FontWeight.w700, color: mine ? V.cyan : V.violet)),
              ),
          ]),
        ),
      ]),
    );
  }
}
