// Game feel: the «ВЕРДИКТ» stamp on a chosen option and a burst of confetti for a rank-up or an achievement.
// Both are drawn in code (no assets) and stay still when the phone asks to reduce motion.
import 'dart:math';

import 'package:flutter/material.dart';

import 'theme.dart';

/// The stamp lands on the option: big and see-through first, then pressed into the card.
class VerdictStamp extends StatelessWidget {
  const VerdictStamp({super.key, this.label = 'ВЕРДИКТ'});

  final String label;

  @override
  Widget build(BuildContext context) {
    final still = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    return IgnorePointer(
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: still ? 1 : 0, end: 1),
        duration: const Duration(milliseconds: 380),
        curve: Curves.easeOutBack,
        builder: (context, t, child) => Opacity(
          opacity: t.clamp(0, 1).toDouble(),
          child: Transform.rotate(
            angle: -.16,
            child: Transform.scale(scale: 1.9 - .9 * t, child: child),
          ),
        ),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
          decoration: BoxDecoration(
            border: Border.all(color: V.magenta, width: 2.2),
            borderRadius: BorderRadius.circular(6),
            color: V.magenta.withValues(alpha: .08),
          ),
          child: Text(
            label,
            style: V.display(11.5, color: V.magenta, weight: FontWeight.w900),
          ),
        ),
      ),
    );
  }
}

/// A one-off confetti burst from the top of its area. Put it in a Stack over the screen.
class Confetti extends StatefulWidget {
  const Confetti({super.key, this.count = 70});

  final int count;

  @override
  State<Confetti> createState() => _ConfettiState();
}

class _ConfettiState extends State<Confetti> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2200));
  late final List<_Bit> _bits;

  @override
  void initState() {
    super.initState();
    final r = Random();
    const colors = [V.cyan, V.magenta, V.violet, V.amber, V.green];
    _bits = List.generate(widget.count, (_) {
      final angle = -pi / 2 + (r.nextDouble() - .5) * pi * .9;
      final speed = .55 + r.nextDouble() * .75;
      return _Bit(
        cos(angle) * speed,
        sin(angle) * speed,
        colors[r.nextInt(colors.length)],
        r.nextDouble() * pi,
        (r.nextDouble() - .5) * 12,
        5 + r.nextDouble() * 6,
      );
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !(MediaQuery.maybeDisableAnimationsOf(context) ?? false)) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: AnimatedBuilder(
      animation: _c,
      builder: (context, _) => _c.isAnimating
          ? CustomPaint(size: Size.infinite, painter: _Painter(_bits, _c.value))
          : const SizedBox.shrink(),
    ),
  );
}

class _Bit {
  _Bit(this.vx, this.vy, this.color, this.turn, this.spin, this.size);

  final double vx, vy, turn, spin, size;
  final Color color;
}

class _Painter extends CustomPainter {
  _Painter(this.bits, this.t);

  final List<_Bit> bits;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    final origin = Offset(size.width / 2, size.height * .32);
    final scale = size.shortestSide;
    final paint = Paint();
    for (final b in bits) {
      // thrown up and out, then falling (gravity), fading in the last third
      final x = origin.dx + b.vx * scale * t;
      final y = origin.dy + b.vy * scale * t + 1.1 * scale * t * t;
      paint.color = b.color.withValues(alpha: (1 - ((t - .66) / .34).clamp(0, 1)).toDouble());
      canvas.save();
      canvas.translate(x, y);
      canvas.rotate(b.turn + b.spin * t);
      canvas.drawRect(Rect.fromCenter(center: Offset.zero, width: b.size, height: b.size * .55), paint);
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(_Painter old) => old.t != t;
}
