// Treasure hunts in the app: the team hides spots on the app's screens (admin → «Приложение или Unity», scene = the
// screen: home, archive, judge, ratings, account, case, result, campaign). A spot sits at x, y % of its screen, as
// visible as the team set it; tapping it opens the gift. The panel lists the hunts that are on, with their hints.
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'fx.dart';
import 'icons.dart';
import 'links.dart';
import 'main.dart';
import 'theme.dart';
import 'widgets.dart';

/// Draws the spots of [scene] over [child]. The tree stays the same with or without spots, so the screen under it
/// keeps its state when a spot appears or is found.
class HuntLayer extends StatelessWidget {
  const HuntLayer({super.key, required this.scene, required this.child});

  final String scene;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final spots = SessionScope.of(context).spotsOn(scene);
    return LayoutBuilder(
      builder: (context, box) => Stack(fit: StackFit.expand, children: [child, for (final s in spots) _place(s, box)]),
    );
  }

  Widget _place(Json s, BoxConstraints box) {
    final size = (s['size'] as num? ?? 24).toDouble();
    final hit = max(size + 16, 48.0);
    final x = (s['x'] as num? ?? 50).toDouble().clamp(0, 100) / 100 * box.maxWidth;
    final y = (s['y'] as num? ?? 50).toDouble().clamp(0, 100) / 100 * box.maxHeight;
    return Positioned(
      key: ValueKey('spot-${s['id']}'),
      left: (x - hit / 2).clamp(0, max(0, box.maxWidth - hit)).toDouble(),
      top: (y - hit / 2).clamp(0, max(0, box.maxHeight - hit)).toDouble(),
      width: hit,
      height: hit,
      child: HuntSpot(spot: s),
    );
  }
}

class HuntSpot extends StatefulWidget {
  const HuntSpot({super.key, required this.spot});

  final Json spot;

  @override
  State<HuntSpot> createState() => _HuntSpotState();
}

class _HuntSpotState extends State<HuntSpot> with SingleTickerProviderStateMixin {
  late final AnimationController _glint = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 2600),
  );
  bool _busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final still = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (still) {
      _glint.stop();
    } else if (!_glint.isAnimating) {
      _glint.repeat();
    }
  }

  @override
  void dispose() {
    _glint.dispose();
    super.dispose();
  }

  Future<void> _open() async {
    if (_busy) return;
    setState(() => _busy = true);
    HapticFeedback.mediumImpact();
    try {
      final out = await SessionScope.read(context).claimSpot((widget.spot['id'] as num).toInt());
      if (mounted) await showFound(context, out);
    } on ApiException catch (e) {
      if (mounted) {
        await showDialog<void>(
          context: context,
          builder: (c) => AlertDialog(
            backgroundColor: V.panel2,
            title: Text(e.code == 'account' ? 'Нужен аккаунт' : 'Тайник'),
            content: Text(e.message),
            actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Понятно'))],
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.spot;
    final size = (s['size'] as num? ?? 24).toDouble();
    final opacity = (s['opacity'] as num? ?? .34).toDouble().clamp(.08, 1).toDouble();
    return Semantics(
      button: true,
      label: 'Тайник',
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _open,
        child: Center(
          child: AnimatedBuilder(
            animation: _glint,
            builder: (context, child) {
              // a short flash once a cycle, then rest: easy to miss when the team made it faint
              final t = _glint.value;
              final flash = t < .18 ? sin(t / .18 * pi) : 0.0;
              return Opacity(
                opacity: (opacity + (1 - opacity) * flash * .6).clamp(0, 1).toDouble(),
                child: Transform.scale(scale: 1 + flash * .18, child: child),
              );
            },
            child: Container(
              width: size,
              height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                boxShadow: [BoxShadow(color: V.amber.withValues(alpha: .55), blurRadius: size * .7)],
              ),
              child: Icon(vIcon(s['icon'] as String?), size: size * .82, color: V.amber),
            ),
          ),
        ),
      ),
    );
  }
}

/// «Тайник найден»: the gift (XP, a trophy, a title, a code, a message), the hunt's progress and its main prize.
Future<void> showFound(BuildContext context, Json out) => showDialog<void>(
  context: context,
  builder: (c) => Dialog(
    backgroundColor: V.panel2,
    insetPadding: const EdgeInsets.all(20),
    child: Stack(
      children: [
        _Found(out: out),
        const Positioned.fill(child: Confetti(count: 50)),
      ],
    ),
  ),
);

class _Found extends StatelessWidget {
  const _Found({required this.out});

  final Json out;

  Widget _gift(BuildContext context, Json g, {bool prize = false}) {
    final xp = (g['xp'] as num? ?? 0).toInt();
    return Panel(
      accent: prize ? V.magenta : V.amber,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(vIcon(g['icon'] as String?), color: prize ? V.magenta : V.amber, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (prize)
                      Text(
                        'Главный приз охоты',
                        style: V.body(12, weight: FontWeight.w800, color: V.magenta),
                      ),
                    Text(g['name'] as String? ?? '', style: V.body(16, weight: FontWeight.w800)),
                    Text(
                      '${g['kind_name'] ?? ''}${xp > 0 ? ' · +$xp XP' : ''}',
                      style: V.body(12.5, color: prize ? V.magenta : V.amber),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if ((g['text'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(g['text'] as String, style: V.body(13.5, color: V.muted)),
          ],
          if (g['code'] != null) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(child: SelectableText('${g['code']}', style: V.mono(17))),
                IconButton(
                  tooltip: 'Скопировать код',
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: '${g['code']}'));
                    snack(context, 'Код скопирован.');
                  },
                  icon: const Icon(Icons.copy, color: V.cyan),
                ),
              ],
            ),
          ],
          if (g['code_missing'] == true)
            Text('Коды закончились — команда пришлёт его позже.', style: V.body(12.5, color: V.muted)),
          if ((g['link'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 8),
            GhostButton('Открыть', icon: Icons.open_in_new, onPressed: () => openLink(context, g['link'] as String)),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final gift = out['gift'] as Json?;
    final prize = out['prize'] as Json?;
    final found = (out['found'] as num? ?? 0).toInt(), total = (out['total'] as num? ?? 0).toInt();
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Icon(Icons.diamond, color: V.amber, size: 46),
          const SizedBox(height: 8),
          Text('Тайник найден!', textAlign: TextAlign.center, style: V.display(21)),
          const SizedBox(height: 4),
          Text(
            'Найдено $found из $total',
            textAlign: TextAlign.center,
            style: V.body(13.5, color: V.muted),
          ),
          const SizedBox(height: 8),
          Bar(total == 0 ? 0 : found / total),
          const SizedBox(height: 16),
          if (gift != null)
            _gift(context, gift)
          else
            Text(
              'В этом тайнике нет подарка, но он засчитан в охоту.',
              textAlign: TextAlign.center,
              style: V.body(14, color: V.muted),
            ),
          if (prize != null) ...[const SizedBox(height: 10), _gift(context, prize, prize: true)],
          const SizedBox(height: 16),
          GradientButton('Забрать', icon: Icons.check, onPressed: () => Navigator.pop(context)),
        ],
      ),
    );
  }
}

String timeLeft(num seconds) {
  final s = seconds.toInt();
  final d = s ~/ 86400, h = (s % 86400) ~/ 3600, m = (s % 3600) ~/ 60;
  if (d > 0) return 'ещё $d ${plural(d, 'день', 'дня', 'дней')}${h > 0 ? ' $h ч' : ''}';
  if (h > 0) return 'ещё $h ч${m > 0 ? ' $m мин' : ''}';
  return 'ещё ${max(m, 1)} мин';
}

/// The hunts that are on: progress, time left, the main prize, and every spot — found (with its gift) or its hint
/// and where to look.
class HuntPanel extends StatelessWidget {
  const HuntPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final hunts = SessionScope.of(context).hunts;
    if (hunts.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionTitle('Охота за тайниками', icon: Icons.diamond_outlined),
        for (final h in hunts) ...[_hunt(h), const SizedBox(height: 8)],
      ],
    );
  }

  Widget _hunt(Json h) {
    final found = (h['found'] as num? ?? 0).toInt(), total = (h['total'] as num? ?? 0).toInt();
    final prize = h['prize'] as Json?;
    final spots = ((h['spots'] as List?) ?? const []).cast<Json>();
    return Panel(
      accent: V.amber,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(h['title'] as String? ?? '', style: V.display(16)),
          if ((h['intro'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(h['intro'] as String, style: V.body(13.5, color: V.muted)),
          ],
          const SizedBox(height: 10),
          Bar(total == 0 ? 0 : found / total, color: V.amber),
          const SizedBox(height: 6),
          Text(
            'Найдено $found из $total${h['seconds_left'] != null ? ' · ${timeLeft(h['seconds_left'] as num)}' : ''}',
            style: V.body(12.5, color: V.amber),
          ),
          if (prize != null) ...[
            const SizedBox(height: 8),
            Pill(
              h['prize_taken'] == true ? 'Приз получен: ${prize['name']}' : 'Приз за все тайники: ${prize['name']}',
              icon: vIcon(prize['icon'] as String?),
              color: V.magenta,
              wrap: true,
            ),
          ],
          const SizedBox(height: 6),
          for (final s in spots)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    s['found'] == true ? Icons.check_circle : (s['empty'] == true ? Icons.block : Icons.help_outline),
                    size: 18,
                    color: s['found'] == true ? V.green : V.muted,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(
                            text: s['found'] == true
                                ? (s['gift'] as String? ?? 'Найден')
                                : (s['hint'] as String? ?? '').isEmpty
                                ? 'Тайник'
                                : s['hint'] as String,
                            style: V.body(13.5, weight: FontWeight.w700),
                          ),
                          TextSpan(
                            text:
                                ' · ${s['scene'] == null ? 'на сайте: ' : ''}${s['page'] ?? ''}'
                                '${s['empty'] == true && s['found'] != true ? ' · пуст' : ''}',
                            style: V.body(12.5, color: V.muted),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// On «Играть»: a hunt is on — how far the player got; the hints are on «Судья».
class HuntBanner extends StatelessWidget {
  const HuntBanner({super.key, required this.onOpen});

  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final hunts = SessionScope.of(context).hunts;
    if (hunts.isEmpty) return const SizedBox.shrink();
    final found = hunts.fold<int>(0, (a, h) => a + (h['found'] as num? ?? 0).toInt());
    final total = hunts.fold<int>(0, (a, h) => a + (h['total'] as num? ?? 0).toInt());
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Panel(
        accent: V.amber,
        onTap: onOpen,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            const Icon(Icons.diamond_outlined, color: V.amber),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    hunts.length == 1 ? hunts.first['title'] as String? ?? 'Охота' : 'Идёт охота за тайниками',
                    style: V.body(14.5, weight: FontWeight.w800),
                  ),
                  Text('Найдено $found из $total · подсказки в «Судье»', style: V.body(12.5, color: V.amber)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: V.muted),
          ],
        ),
      ),
    );
  }
}
