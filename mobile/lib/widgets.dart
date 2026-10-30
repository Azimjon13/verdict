// Building blocks in the website's style.
import 'package:flutter/material.dart';

import 'api.dart';
import 'icons.dart';
import 'theme.dart';

class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.accent, this.onTap});

  final Widget child;
  final EdgeInsets padding;
  final Color? accent;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final box = Container(
      padding: padding,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xE60B0F27), Color(0xE6070A1C)]),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accent?.withValues(alpha: .55) ?? V.line),
        boxShadow: accent == null ? null : [BoxShadow(color: accent!.withValues(alpha: .18), blurRadius: 22, spreadRadius: -6)],
      ),
      child: child,
    );
    if (onTap == null) return box;
    return Material(
      color: Colors.transparent,
      child: InkWell(borderRadius: BorderRadius.circular(16), onTap: onTap, child: box),
    );
  }
}

class Kicker extends StatelessWidget {
  const Kicker(this.text, {super.key, this.color = V.cyan});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Row(children: [
        Container(width: 18, height: 2, color: color),
        const SizedBox(width: 8),
        Flexible(child: Text(text.toUpperCase(), style: V.mono(11, color: color))),
      ]);
}

class OptionLetter extends StatelessWidget {
  const OptionLetter(this.letter, {super.key, this.size = 34, this.active = false});

  final String letter;
  final double size;
  final bool active;

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: active ? V.grad : null,
          color: active ? null : const Color(0xFF101634),
          border: Border.all(color: active ? Colors.transparent : V.cyan.withValues(alpha: .45)),
        ),
        child: Text(letter == 'other' ? '+' : letter,
            style: V.display(size * .42, color: active ? V.bg : V.cyan, weight: FontWeight.w800)),
      );
}

class Bar extends StatelessWidget {
  const Bar(this.value, {super.key, this.height = 8, this.color, this.gradient = true});

  /// 0…1
  final double value;
  final double height;
  final Color? color;
  final bool gradient;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: BorderRadius.circular(height),
        child: Stack(children: [
          Container(height: height, color: Colors.white.withValues(alpha: .07)),
          FractionallySizedBox(
            widthFactor: value.clamp(0, 1).toDouble(),
            child: Container(
                height: height,
                decoration: BoxDecoration(
                    gradient: gradient && color == null ? V.grad : null, color: color, borderRadius: BorderRadius.circular(height))),
          ),
        ]),
      );
}

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.icon, this.color = V.cyan, this.filled = false, this.wrap = false});

  final String text;
  final IconData? icon;
  final Color color;
  final bool filled;

  /// Long text goes onto more lines instead of ending in «…».
  final bool wrap;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: color.withValues(alpha: filled ? .2 : .08),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: color.withValues(alpha: .45)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 14, color: color), const SizedBox(width: 5)],
          Flexible(
              child: Text(text,
                  style: V.body(12, weight: FontWeight.w700, color: color),
                  overflow: wrap ? TextOverflow.visible : TextOverflow.ellipsis)),
        ]),
      );
}

class Avatar extends StatelessWidget {
  const Avatar(this.name, {super.key, this.hue, this.size = 38});

  final String name;
  final num? hue;
  final double size;

  static int hueOf(String s) => s.codeUnits.fold(7, (a, c) => (a * 31 + c) % 360);

  static String initials(String name) {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    final first = parts.first.characters.first;
    final second = parts.length > 1 ? parts[1].characters.first : (parts.first.characters.length > 1 ? parts.first.characters.elementAt(1) : '');
    return (first + second).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final c = V.hue(hue ?? hueOf(name), s: .7, l: .52);
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * .3),
        gradient: LinearGradient(colors: [c, HSLColor.fromColor(c).withHue((HSLColor.fromColor(c).hue + 40) % 360).toColor()]),
      ),
      child: Text(initials(name), style: V.body(size * .36, weight: FontWeight.w800, color: Colors.white)),
    );
  }
}

class GradientButton extends StatelessWidget {
  const GradientButton(this.label, {super.key, required this.onPressed, this.icon, this.busy = false});

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !busy;
    return Opacity(
      opacity: enabled ? 1 : .55,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: enabled ? onPressed : null,
          borderRadius: BorderRadius.circular(14),
          child: Ink(
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFF2BE4FF), Color(0xFF7C5CF6)]),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [BoxShadow(color: V.cyan.withValues(alpha: .35), blurRadius: 18, spreadRadius: -6)],
            ),
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 15),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, mainAxisSize: MainAxisSize.min, children: [
              if (busy)
                const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.4, color: V.bg))
              else if (icon != null)
                Icon(icon, color: V.bg, size: 20),
              const SizedBox(width: 8),
              Flexible(child: Text(label, style: V.body(16, weight: FontWeight.w800, color: V.bg))),
            ]),
          ),
        ),
      ),
    );
  }
}

class GhostButton extends StatelessWidget {
  const GhostButton(this.label, {super.key, required this.onPressed, this.icon});

  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon ?? Icons.arrow_forward, size: 18),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          foregroundColor: V.text,
          side: const BorderSide(color: V.line),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: V.body(14, weight: FontWeight.w700),
        ),
      );
}

class Loading extends StatelessWidget {
  const Loading({super.key});

  @override
  Widget build(BuildContext context) =>
      const Center(child: Padding(padding: EdgeInsets.all(40), child: CircularProgressIndicator(color: V.cyan)));
}

class ErrorView extends StatelessWidget {
  const ErrorView(this.error, {super.key, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final offline = error is ApiException && (error as ApiException).offline;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(offline ? Icons.wifi_off : Icons.error_outline, size: 46, color: V.cyan),
          const SizedBox(height: 14),
          Text(offline ? 'Нет связи' : 'Что-то пошло не так', style: V.display(20)),
          const SizedBox(height: 8),
          Text('$error', textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
          const SizedBox(height: 18),
          GhostButton('Попробовать снова', icon: Icons.refresh, onPressed: onRetry),
        ]),
      ),
    );
  }
}

/// Loads data and shows it, with pull-to-refresh, a spinner and a retry on error.
class Loader<T> extends StatefulWidget {
  const Loader({super.key, required this.load, required this.builder});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;

  @override
  State<Loader<T>> createState() => _LoaderState<T>();
}

class _LoaderState<T> extends State<Loader<T>> {
  late Future<T> _future = widget.load();

  Future<void> _reload() async {
    final f = widget.load();
    setState(() => _future = f);
    await f.then((_) {}, onError: (_) {});
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: _future,
        builder: (context, snap) {
          if (snap.hasError) return ErrorView(snap.error!, onRetry: _reload);
          if (!snap.hasData) return const Loading();
          return RefreshIndicator(color: V.cyan, onRefresh: _reload, child: widget.builder(context, snap.data as T, _reload));
        },
      );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.icon, this.trailing});

  final String text;
  final IconData? icon;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 22, bottom: 10),
        child: Row(children: [
          if (icon != null) ...[Icon(icon, size: 19, color: V.cyan), const SizedBox(width: 8)],
          Expanded(child: Text(text, style: V.display(16, weight: FontWeight.w700))),
          ?trailing,
        ]),
      );
}

Widget iconOf(String? name, {double size = 20, Color color = V.cyan}) => Icon(vIcon(name), size: size, color: color);

/// «2026-10-29T09:15:00Z» → «29.10.2026» (with the time: «29.10.2026 09:15»), as the website writes dates.
String ruDate(String iso, {bool time = false}) {
  final d = DateTime.tryParse(iso)?.toLocal();
  if (d == null) return iso;
  String two(int v) => v.toString().padLeft(2, '0');
  return '${two(d.day)}.${two(d.month)}.${d.year}${time ? ' ${two(d.hour)}:${two(d.minute)}' : ''}';
}

String capitalize(String s) => s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);

String plural(num n, String one, String few, String many) {
  final a = n.abs() % 100, b = a % 10;
  if (a > 10 && a < 20) return many;
  if (b > 1 && b < 5) return few;
  if (b == 1) return one;
  return many;
}
