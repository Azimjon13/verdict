// A case as swipeable frames («Дело в кадрах»), then the verdict — and in Быстрый суд the guess of the majority.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'result_screen.dart';

/// Быстрый суд: the next case the player hasn't judged, again and again.
class QuickRun extends StatefulWidget {
  const QuickRun({super.key, this.except, this.atVerdict = false});

  final int? except;

  /// Open the case on its last frame — the verdict.
  final bool atVerdict;

  @override
  State<QuickRun> createState() => _QuickRunState();
}

class _QuickRunState extends State<QuickRun> {
  @override
  Widget build(BuildContext context) {
    final api = SessionScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: const Text('Быстрый суд')),
      body: Loader<Json>(
        load: () => api.get('/quick/next', query: widget.except == null ? null : {'except': '${widget.except}'}),
        builder: (context, data, reload) {
          if (data['done'] == true || data['case'] == null) {
            return ListView(
              padding: const EdgeInsets.all(28),
              children: [
                const SizedBox(height: 40),
                const Icon(Icons.emoji_events, size: 56, color: V.amber),
                const SizedBox(height: 16),
                Text('Все дела рассужены', textAlign: TextAlign.center, style: V.display(22)),
                const SizedBox(height: 10),
                Text(
                  'Вы вынесли вердикт по каждому делу в игре. Новые появляются, когда команда одобряет дела авторов.',
                  textAlign: TextAlign.center,
                  style: V.body(14, color: V.muted),
                ),
              ],
            );
          }
          return CaseView(caseData: data['case'] as Json, quick: true, remaining: (data['remaining'] as num?)?.toInt(),
              atVerdict: widget.atVerdict);
        },
      ),
    );
  }
}

/// One case by id (the case of the day, the archive).
class CaseScreen extends StatelessWidget {
  const CaseScreen({super.key, required this.caseId, this.quick = false});

  final int caseId;
  final bool quick;

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.read(context).api;
    return Scaffold(
      appBar: AppBar(title: Text(quick ? 'Быстрый суд' : 'Дело')),
      body: Loader<Json>(
        load: () => api.get('/cases/$caseId'),
        builder: (context, data, reload) => CaseView(caseData: data['case'] as Json, quick: quick),
      ),
    );
  }
}

class CaseView extends StatefulWidget {
  const CaseView({super.key, required this.caseData, required this.quick, this.remaining, this.atVerdict = false});

  final Json caseData;
  final bool quick;
  final int? remaining;
  final bool atVerdict;

  @override
  State<CaseView> createState() => _CaseViewState();
}

class _CaseViewState extends State<CaseView> {
  late int _page = widget.atVerdict ? panels.length - 1 : 0;
  late final _pages = PageController(initialPage: _page);
  final _opened = DateTime.now();

  Json get c => widget.caseData;
  List<Json> get panels => ((c['comic'] as Json)['panels'] as List).cast<Json>();
  List<Json> get cast => ((c['comic'] as Json)['cast'] as List).cast<Json>();

  void _go(int page) =>
      _pages.animateToPage(page, duration: const Duration(milliseconds: 320), curve: Curves.easeOutCubic);

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final cat = s.category(c['category'] as String?);
    final accent = V.hue(cat['hue'] as num? ?? 190);
    final last = panels.length - 1;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: Pill(cat['name'] as String, icon: vIcon(cat['icon'] as String?), color: accent),
              ),
              const SizedBox(width: 10),
              Text('${_page + 1} / ${panels.length}', style: V.mono(12, color: V.muted)),
              if (_page < last) ...[
                const SizedBox(width: 6),
                TextButton(onPressed: () => _go(last), child: const Text('К вердикту')),
              ],
            ],
          ),
        ),
        Expanded(
          child: PageView.builder(
            controller: _pages,
            itemCount: panels.length,
            onPageChanged: (p) => setState(() => _page = p),
            itemBuilder: (context, i) => _frame(panels[i], accent),
          ),
        ),
        if (_page < last)
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 12),
              child: Row(
                children: [
                  IconButton(
                    onPressed: _page == 0 ? null : () => _go(_page - 1),
                    icon: const Icon(Icons.arrow_back),
                    color: V.muted,
                  ),
                  Expanded(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(
                          panels.length,
                          (i) => AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            margin: const EdgeInsets.symmetric(horizontal: 3),
                            width: i == _page ? 18 : 7,
                            height: 7,
                            decoration: BoxDecoration(
                              color: i == _page ? V.cyan : (i < _page ? V.cyan.withValues(alpha: .4) : V.line),
                              borderRadius: BorderRadius.circular(4),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  FilledButton.icon(
                    onPressed: () => _go(_page + 1),
                    icon: const Icon(Icons.arrow_forward, size: 18),
                    label: Text(_page + 1 == last ? 'К вердикту' : 'Дальше'),
                    style: FilledButton.styleFrom(backgroundColor: V.cyan, foregroundColor: V.bg),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _frame(Json p, Color accent) {
    final Widget body = switch (p['kind']) {
      'world' => _world(p, accent),
      'story' => _story(p),
      'cast' => _people(p),
      'evidence' => _evidence(p),
      'witnesses' => _witnesses(p),
      _ => VerdictPanel(caseData: c, quick: widget.quick, opened: _opened, remaining: widget.remaining),
    };
    return SingleChildScrollView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 24), child: body);
  }

  Widget _world(Json p, Color accent) {
    final w = c['world'] as Json;
    return Panel(
      accent: accent,
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Kicker(w['setting'] as String? ?? '', color: accent),
          const SizedBox(height: 12),
          Text(c['title'] as String, style: V.display(26, weight: FontWeight.w900)),
          const SizedBox(height: 12),
          _line(Icons.place, p['place'] as String? ?? ''),
          if ((p['era'] as String? ?? '').isNotEmpty) _line(Icons.hourglass_empty, p['era'] as String),
          if ((p['role'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 10),
            Pill('Ваша роль: ${p['role']}', icon: Icons.person, color: V.cyan, filled: true, wrap: true),
          ],
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.only(left: 12),
            decoration: const BoxDecoration(
              border: Border(left: BorderSide(color: V.amber, width: 3)),
            ),
            child: Text(p['text'] as String? ?? '', style: V.body(15.5, height: 1.55)),
          ),
        ],
      ),
    );
  }

  Widget _line(IconData icon, String text) => Padding(
    padding: const EdgeInsets.only(bottom: 4),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: V.muted),
        const SizedBox(width: 8),
        Expanded(
          child: Text(text, style: V.body(13.5, color: V.muted)),
        ),
      ],
    ),
  );

  Widget _story(Json p) {
    final segments = (p['segments'] as List).cast<Json>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final seg in segments)
          if (seg['type'] == 'speech')
            _bubble(seg['who'] as int?, seg['text'] as String, tag: seg['tag'] as String?)
          else
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(seg['text'] as String, style: V.body(16, height: 1.6)),
            ),
      ],
    );
  }

  Widget _bubble(int? who, String text, {String? tag, String? footer}) {
    final person = who == null || who >= cast.length ? null : cast[who];
    final name = person?['short'] as String? ?? ((tag ?? '').isNotEmpty ? tag! : 'Голос');
    final hue = person?['hue'] as num?;
    final color = hue == null ? V.muted : V.hue(hue);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Avatar(name, hue: hue, size: 36),
          const SizedBox(width: 10),
          Expanded(
            child: Container(
              padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
              decoration: BoxDecoration(
                color: const Color(0xFF0F1433),
                borderRadius: const BorderRadius.only(
                  topRight: Radius.circular(14),
                  bottomLeft: Radius.circular(14),
                  bottomRight: Radius.circular(14),
                ),
                border: Border.all(color: color.withValues(alpha: .4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: V.body(12.5, weight: FontWeight.w800, color: color),
                  ),
                  const SizedBox(height: 4),
                  Text('«$text»', style: V.body(15.5, height: 1.5)),
                  if (footer != null) ...[const SizedBox(height: 8), Text(footer, style: V.body(12, color: V.dim))],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _people(Json p) => Column(
    children: [
      Align(
        alignment: Alignment.centerLeft,
        child: Text('Участники', style: V.display(18)),
      ),
      const SizedBox(height: 12),
      for (final i in (p['people'] as List).cast<int>())
        if (i < cast.length)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Panel(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Avatar(cast[i]['name'] as String, hue: cast[i]['hue'] as num?, size: 44),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          [
                            cast[i]['name'],
                            if ((cast[i]['age'] as String? ?? '').isNotEmpty) cast[i]['age'],
                          ].join(', '),
                          style: V.body(15.5, weight: FontWeight.w800),
                        ),
                        if ((cast[i]['role'] as String? ?? '').isNotEmpty)
                          Text(
                            cast[i]['role'] as String,
                            style: V.body(13, color: V.hue(cast[i]['hue'] as num? ?? 190)),
                          ),
                        if ((cast[i]['relations'] as String? ?? '').isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(cast[i]['relations'] as String, style: V.body(13.5, color: V.muted)),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
    ],
  );

  Widget _evidence(Json p) {
    Widget list(String title, IconData icon, Color color, List items) => Panel(
      accent: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: V.display(16, color: color)),
          const SizedBox(height: 10),
          for (final f in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(icon, size: 18, color: color),
                  const SizedBox(width: 10),
                  Expanded(child: Text('$f', style: V.body(14.5))),
                ],
              ),
            ),
        ],
      ),
    );
    return Column(
      children: [
        list('Известно', Icons.check_circle_outline, V.green, p['facts'] as List? ?? []),
        if ((p['unknowns'] as List? ?? []).isNotEmpty) ...[
          const SizedBox(height: 12),
          list('Неизвестно', Icons.help_outline, V.amber, p['unknowns'] as List),
        ],
      ],
    );
  }

  Widget _witnesses(Json p) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text('Свидетели', style: V.display(18)),
      const SizedBox(height: 4),
      Text('Они могут ошибаться — или лгать.', style: V.body(13, color: V.muted)),
      const SizedBox(height: 8),
      for (final i in (p['people'] as List).cast<int>())
        if (i < cast.length)
          _bubble(
            i,
            cast[i]['claim'] as String? ?? '',
            footer: [
              if ((cast[i]['trust'] as String? ?? '').isNotEmpty) 'Доверие: ${cast[i]['trust']}',
              if ((cast[i]['interest'] as String? ?? '').isNotEmpty) 'Интерес: ${cast[i]['interest']}',
            ].join('\n'),
          ),
    ],
  );
}

/// The last frame: pick a verdict; in Быстрый суд then guess how most players decided.
class VerdictPanel extends StatefulWidget {
  const VerdictPanel({super.key, required this.caseData, required this.quick, required this.opened, this.remaining});

  final Json caseData;
  final bool quick;
  final DateTime opened;
  final int? remaining;

  @override
  State<VerdictPanel> createState() => _VerdictPanelState();
}

class _VerdictPanelState extends State<VerdictPanel> {
  String? _choice;
  bool _guessing = false;
  bool _busy = false;
  String? _error;
  final _own = TextEditingController();

  Json get c => widget.caseData;
  List<Json> get decisions => (c['decisions'] as List).cast<Json>();

  @override
  void dispose() {
    _own.dispose();
    super.dispose();
  }

  void _pick(String key) {
    HapticFeedback.mediumImpact();
    setState(() {
      _choice = key;
      _error = null;
      if (widget.quick) _guessing = true;
    });
  }

  Future<void> _submit({String guess = ''}) async {
    if (_choice == null) return;
    if (_choice == 'other' && _own.text.trim().length < 10) {
      setState(() => _error = 'Опишите своё решение — хотя бы одним предложением.');
      return;
    }
    HapticFeedback.heavyImpact();
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = SessionScope.read(context).api;
    try {
      final out = await api.post('/cases/${c['id']}/verdict', {
        'option': _choice,
        'mode': widget.quick ? 'quick' : 'full',
        'guess': guess,
        'reasoning': _choice == 'other' ? _own.text.trim() : '',
        'duration_ms': DateTime.now().difference(widget.opened).inMilliseconds,
      });
      if (!mounted) return;
      SessionScope.read(context).refreshMe();
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ResultScreen(result: out, caseData: c, quick: widget.quick),
        ),
      );
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _option(Json d, {required bool selected, required VoidCallback onTap}) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Panel(
      accent: selected ? V.cyan : null,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      onTap: _busy ? null : onTap,
      child: Row(
        children: [
          OptionLetter(d['key'] as String, active: selected),
          const SizedBox(width: 14),
          Expanded(
            child: Text(d['text'] as String, style: V.body(15, weight: FontWeight.w700)),
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final my = c['my_vote'] as Json?;
    if (_guessing) {
      final picked = decisions.firstWhere(
        (d) => d['key'] == _choice,
        orElse: () => {'key': _choice, 'text': 'Своё решение'},
      );
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const OptionLetter('2', size: 28, active: true),
              const SizedBox(width: 10),
              Expanded(child: Text('Как решило большинство?', style: V.display(19))),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Угадаете — +5 XP. Ваш вердикт: ${picked['key']} — ${picked['text']}',
            style: V.body(13.5, color: V.muted),
          ),
          TextButton.icon(
            onPressed: _busy ? null : () => setState(() => _guessing = false),
            icon: const Icon(Icons.undo, size: 18),
            label: const Text('Изменить вердикт'),
          ),
          const SizedBox(height: 4),
          for (final d in decisions) _option(d, selected: false, onTap: () => _submit(guess: d['key'] as String)),
          const SizedBox(height: 4),
          GhostButton(
            'Не угадывать — показать итоги',
            icon: Icons.skip_next,
            onPressed: _busy ? null : () => _submit(),
          ),
          if (_busy) const Padding(padding: EdgeInsets.only(top: 16), child: Loading()),
          if (_error != null) _errorBox(),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            if (widget.quick) ...[const OptionLetter('1', size: 28, active: true), const SizedBox(width: 10)],
            Expanded(child: Text('Ваш вердикт', style: V.display(21))),
          ],
        ),
        const SizedBox(height: 6),
        Text(c['title'] as String, style: V.body(14, color: V.muted)),
        if (my != null) ...[
          const SizedBox(height: 10),
          Pill(
            'Вы уже судили это дело: ${my['option'] == 'other' ? 'своё решение' : my['option']}',
            icon: Icons.history,
            color: V.amber,
          ),
        ],
        const SizedBox(height: 14),
        for (final d in decisions) _option(d, selected: _choice == d['key'], onTap: () => _pick(d['key'] as String)),
        if (!widget.quick && c['allows_own_decision'] == true) ...[
          _option({'key': 'other', 'text': 'Своё решение'}, selected: _choice == 'other', onTap: () => _pick('other')),
          if (_choice == 'other')
            TextField(
              controller: _own,
              minLines: 3,
              maxLines: 6,
              maxLength: 1000,
              decoration: const InputDecoration(hintText: 'Что бы вы сделали — и почему?'),
            ),
        ],
        if (!widget.quick) ...[
          const SizedBox(height: 8),
          GradientButton(
            'Вынести вердикт',
            icon: Icons.gavel,
            busy: _busy,
            onPressed: _choice == null ? null : () => _submit(),
          ),
        ],
        if (_error != null) _errorBox(),
        if (widget.remaining != null) ...[
          const SizedBox(height: 14),
          Text(
            'Ещё не рассужено: ${widget.remaining}',
            textAlign: TextAlign.center,
            style: V.body(12.5, color: V.dim),
          ),
        ],
      ],
    );
  }

  Widget _errorBox() => Padding(
    padding: const EdgeInsets.only(top: 12),
    child: Panel(
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
  );
}
