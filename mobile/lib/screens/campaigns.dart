// Story campaigns: a chain of cases where each chapter begins where the last verdict left off, with the campaign's own
// world meters and one of several endings.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../fx.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'case_screen.dart';

String _progressText(Json c) {
  final p = c['progress'] as Json;
  final chapters = (c['chapters'] as List).length;
  if (p['finished'] == true) return 'Пройдена: «${(p['ending'] as Json?)?['title'] ?? ''}»';
  if (p['started'] == true) return 'Глава ${(p['chapter_index'] as int) + 1} из $chapters';
  return '$chapters ${plural(chapters, 'глава', 'главы', 'глав')}';
}

/// On the home screen: the campaigns as cards.
class CampaignsSection extends StatelessWidget {
  const CampaignsSection({super.key, required this.campaigns, required this.onChanged});

  final List<Json> campaigns;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    if (campaigns.isEmpty) return const SizedBox.shrink();
    final s = SessionScope.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionTitle('Кампании', icon: Icons.auto_stories),
        for (final c in campaigns)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Panel(
              accent: V.hue(s.category(c['category'] as String?)['hue'] as num? ?? 260),
              onTap: () async {
                await Navigator.of(context)
                    .push(MaterialPageRoute(builder: (_) => CampaignScreen(campaignKey: c['key'] as String)));
                onChanged();
              },
              child: Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: V.hue(s.category(c['category'] as String?)['hue'] as num? ?? 260).withValues(alpha: .16),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Icon(
                      vIcon(c['icon'] as String?),
                      color: V.hue(s.category(c['category'] as String?)['hue'] as num? ?? 260),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(c['title'] as String, style: V.display(16)),
                        const SizedBox(height: 3),
                        Text(
                          c['teaser'] as String? ?? '',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: V.body(13, color: V.muted),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          _progressText(c),
                          style: V.body(12, weight: FontWeight.w700, color: V.cyan),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right, color: V.muted),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

/// A campaign: its story so far, the chapters, the campaign's world, the ending.
class CampaignScreen extends StatefulWidget {
  const CampaignScreen({super.key, required this.campaignKey});

  final String campaignKey;

  @override
  State<CampaignScreen> createState() => _CampaignScreenState();
}

class _CampaignScreenState extends State<CampaignScreen> {
  Key _loader = UniqueKey();
  bool _busy = false;

  Future<void> _play(Json c, {bool restart = false}) async {
    final api = SessionScope.read(context).api;
    setState(() => _busy = true);
    try {
      var campaign = c;
      final p = c['progress'] as Json;
      if (restart || p['started'] != true) {
        campaign = (await api.post('/campaigns/${widget.campaignKey}/start'))['campaign'] as Json;
      }
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ChapterScreen(campaign: campaign)));
      if (mounted) setState(() => _loader = UniqueKey());
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Кампания')),
      body: Loader<Json>(
        key: _loader,
        load: () async => (await api.get('/campaigns/${widget.campaignKey}'))['campaign'] as Json,
        builder: (context, c, reload) {
          final p = c['progress'] as Json;
          final chapters = (c['chapters'] as List).cast<String>();
          final choices = ((p['choices'] as List?) ?? const []).cast<Json>();
          final ending = p['ending'] as Json?;
          final current = p['chapter_index'] as int? ?? 0;
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
            children: [
              Kicker('${chapters.length} ${plural(chapters.length, 'глава', 'главы', 'глав')}'),
              const SizedBox(height: 8),
              Text(c['title'] as String, style: V.display(26, weight: FontWeight.w900)),
              const SizedBox(height: 10),
              Text(c['intro'] as String? ?? '', style: V.body(15, height: 1.55)),
              const SectionTitle('Главы', icon: Icons.format_list_numbered),
              for (var i = 0; i < chapters.length; i++)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Panel(
                    accent: p['started'] == true && p['finished'] != true && i == current ? V.cyan : null,
                    child: Row(
                      children: [
                        Icon(
                          i < choices.length
                              ? Icons.check_circle
                              : (i == current && p['finished'] != true ? Icons.play_circle : Icons.lock_outline),
                          color: i < choices.length ? V.green : (i == current && p['finished'] != true ? V.cyan : V.dim),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text('${i + 1}. ${chapters[i]}', style: V.body(15, weight: FontWeight.w700)),
                        ),
                        if (i < choices.length) OptionLetter(choices[i]['option'] as String, size: 26),
                      ],
                    ),
                  ),
                ),
              if (p['started'] == true) ...[
                const SectionTitle('Мир кампании', icon: Icons.public),
                _Meters(meters: p['meters'] as Json),
              ],
              if (ending != null) ...[const SizedBox(height: 16), EndingCard(ending: ending)],
              const SizedBox(height: 20),
              if (p['finished'] == true)
                GradientButton(
                  'Пройти заново',
                  icon: Icons.replay,
                  busy: _busy,
                  onPressed: () => _play(c, restart: true),
                )
              else
                GradientButton(
                  p['started'] == true ? 'Продолжить: глава ${current + 1}' : 'Начать кампанию',
                  icon: Icons.play_arrow,
                  busy: _busy,
                  onPressed: () => _play(c),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _Meters extends StatelessWidget {
  const _Meters({required this.meters, this.delta});

  final Json meters;
  final Json? delta;

  @override
  Widget build(BuildContext context) {
    final names = SessionScope.of(context).metrics();
    return Column(
      children: [
        for (final e in names.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 9),
            child: Row(
              children: [
                Icon(vIcon((e.value as Json)['icon'] as String?), size: 16, color: V.muted),
                const SizedBox(width: 8),
                SizedBox(
                  width: 112,
                  child: Text((e.value as Json)['name'] as String, style: V.body(13, weight: FontWeight.w700)),
                ),
                Expanded(child: Bar(((meters[e.key] as num? ?? 50) / 100).toDouble())),
                SizedBox(
                  width: 58,
                  child: Text(
                    delta?[e.key] == null
                        ? '${meters[e.key] ?? 50}'
                        : '${(delta![e.key] as num) > 0 ? '+' : ''}${delta![e.key]}',
                    textAlign: TextAlign.right,
                    style: V.display(
                      13,
                      color: delta?[e.key] == null ? V.text : ((delta![e.key] as num) > 0 ? V.green : V.red),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class EndingCard extends StatelessWidget {
  const EndingCard({super.key, required this.ending});

  final Json ending;

  @override
  Widget build(BuildContext context) {
    final color = switch (ending['tone']) {
      'up' => V.green,
      'down' => V.red,
      _ => V.amber,
    };
    return Panel(
      accent: color,
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Kicker('Концовка', color: color),
          const SizedBox(height: 10),
          Row(
            children: [
              Icon(vIcon(ending['icon'] as String?), color: color, size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Text(ending['title'] as String, style: V.display(20, color: color)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(ending['text'] as String? ?? '', style: V.body(15, height: 1.55)),
        ],
      ),
    );
  }
}

/// The current chapter: what earlier verdicts led to, then the case — and the choice goes to the campaign.
class ChapterScreen extends StatelessWidget {
  const ChapterScreen({super.key, required this.campaign});

  final Json campaign;

  @override
  Widget build(BuildContext context) {
    final chapter = campaign['chapter'] as Json;
    final bridges = ((chapter['bridges'] as List?) ?? const []).cast<Json>();
    final key = campaign['key'] as String;
    Future<void> choose(String option) async {
      final out = await SessionScope.read(context).api.post('/campaigns/$key/choose', {'option': option});
      if (!context.mounted) return;
      if (((out['campaign'] as Json)['progress'] as Json)['finished'] == true) HapticFeedback.heavyImpact();
      SessionScope.read(context).refreshMe();
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => StepScreen(step: out)));
    }

    final view = CaseView(caseData: chapter['case'] as Json, quick: false, onChoose: choose);
    return Scaffold(
      appBar: AppBar(
        title: Text('${campaign['title']} · глава ${(chapter['index'] as int) + 1}', overflow: TextOverflow.ellipsis),
      ),
      body: bridges.isEmpty ? view : _Bridges(bridges: bridges, child: view),
    );
  }
}

/// «Что было дальше» — the consequences of earlier chapters, read before the new case.
class _Bridges extends StatefulWidget {
  const _Bridges({required this.bridges, required this.child});

  final List<Json> bridges;
  final Widget child;

  @override
  State<_Bridges> createState() => _BridgesState();
}

class _BridgesState extends State<_Bridges> {
  bool _read = false;

  @override
  Widget build(BuildContext context) {
    if (_read) return widget.child;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
      children: [
        const Kicker('Что было дальше', color: V.amber),
        const SizedBox(height: 12),
        for (final b in widget.bridges)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Panel(
              accent: V.amber,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'После дела «${b['from']}»',
                    style: V.body(12.5, weight: FontWeight.w800, color: V.amber),
                  ),
                  const SizedBox(height: 6),
                  Text(b['text'] as String, style: V.body(15.5, height: 1.55)),
                ],
              ),
            ),
          ),
        const SizedBox(height: 8),
        GradientButton('К новому делу', icon: Icons.arrow_forward, onPressed: () => setState(() => _read = true)),
      ],
    );
  }
}

/// After a chapter: its consequences and how the campaign's world moved — then the next chapter or the ending.
class StepScreen extends StatelessWidget {
  const StepScreen({super.key, required this.step});

  final Json step;

  @override
  Widget build(BuildContext context) {
    final r = step['result'] as Json;
    final c = step['campaign'] as Json;
    final p = c['progress'] as Json;
    final ending = p['ending'] as Json?;
    final finished = p['finished'] == true;
    return Scaffold(
      appBar: AppBar(title: Text(c['title'] as String)),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 28),
            children: [
              Kicker('Глава ${(r['chapter_index'] as int) + 1}: ваш вердикт'),
              const SizedBox(height: 10),
              Row(
                children: [
                  OptionLetter(r['option'] as String, active: true, size: 40),
                  const SizedBox(width: 12),
                  Expanded(child: Text('Последствия решения', style: V.display(18))),
                ],
              ),
              const SizedBox(height: 12),
              for (final (key, title, icon) in [
                ('immediate', 'Сразу', Icons.bolt),
                ('longterm', 'Со временем', Icons.hourglass_bottom),
              ])
                if ((r[key] as String? ?? '').isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Panel(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(icon, size: 18, color: V.amber),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  title,
                                  style: V.body(12, weight: FontWeight.w800, color: V.amber),
                                ),
                                Text(r[key] as String, style: V.body(14.5)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              const SectionTitle('Мир кампании', icon: Icons.public),
              _Meters(meters: p['meters'] as Json, delta: r['meters_delta'] as Json?),
              if (ending != null) ...[const SizedBox(height: 14), EndingCard(ending: ending)],
              const SizedBox(height: 20),
              if (!finished)
                GradientButton(
                  'Глава ${(p['chapter_index'] as int) + 1}',
                  icon: Icons.arrow_forward,
                  onPressed: () {
                    Navigator.of(context)
                        .pushReplacement(MaterialPageRoute(builder: (_) => ChapterScreen(campaign: c)));
                  },
                )
              else
                GradientButton('К кампании', icon: Icons.auto_stories, onPressed: () => Navigator.of(context).pop()),
            ],
          ),
          if (finished) const Positioned.fill(child: Confetti()),
        ],
      ),
    );
  }
}
