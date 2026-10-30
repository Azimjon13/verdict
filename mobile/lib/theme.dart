// The website's look: deep night background, cyan and magenta neon, Unbounded for headings, Manrope for text.
import 'package:flutter/material.dart';

class V {
  static const bg = Color(0xFF03040A);
  static const panel = Color(0xFF0A0D22);
  static const panel2 = Color(0xFF10142E);
  static const line = Color(0x2E9AA6D1);
  static const text = Color(0xFFE8EDFF);
  static const muted = Color(0xFF9AA6D1);
  static const dim = Color(0xFF5F6A90);
  static const cyan = Color(0xFF00E5FF);
  static const magenta = Color(0xFFFF2BD6);
  static const violet = Color(0xFF8B5CF6);
  static const amber = Color(0xFFFFB547);
  static const green = Color(0xFF3DDC97);
  static const red = Color(0xFFFF4D6D);
  static const grad = LinearGradient(colors: [Color(0xFF2BE4FF), Color(0xFF8B5CF6), Color(0xFFFF2BD6)]);

  static Color hue(num h, {double s = .85, double l = .62}) => HSLColor.fromAHSL(1, h.toDouble() % 360, s, l).toColor();

  /// Unbounded is a variable font: the weight goes to its «wght» axis.
  static TextStyle display(double size, {FontWeight weight = FontWeight.w800, Color color = text}) => TextStyle(
      fontFamily: 'Unbounded',
      fontSize: size,
      fontWeight: weight,
      fontVariations: [FontVariation('wght', weight.value.toDouble())],
      color: color,
      height: 1.15);

  static TextStyle body(double size, {FontWeight weight = FontWeight.w500, Color color = text, double height = 1.45}) =>
      TextStyle(
          fontFamily: 'Manrope',
          fontSize: size,
          fontWeight: weight,
          fontVariations: [FontVariation('wght', weight.value.toDouble())],
          color: color,
          height: height);

  static TextStyle mono(double size, {Color color = cyan}) =>
      TextStyle(fontFamily: 'monospace', fontSize: size, letterSpacing: 1.6, color: color, fontWeight: FontWeight.w600);

  static ThemeData theme() {
    final base = ThemeData(useMaterial3: true, brightness: Brightness.dark, fontFamily: 'Manrope');
    return base.copyWith(
      scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.dark(
          primary: cyan, secondary: magenta, surface: panel, onSurface: text, error: red, onPrimary: bg),
      textTheme: base.textTheme.apply(bodyColor: text, displayColor: text, fontFamily: 'Manrope'),
      appBarTheme: AppBarTheme(
          backgroundColor: bg, surfaceTintColor: Colors.transparent, elevation: 0, titleTextStyle: display(17)),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: const Color(0xFF060818),
        indicatorColor: cyan.withValues(alpha: .16),
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStateProperty.resolveWith(
            (s) => body(11.5, weight: FontWeight.w700, color: s.contains(WidgetState.selected) ? text : muted)),
        iconTheme: WidgetStateProperty.resolveWith(
            (s) => IconThemeData(color: s.contains(WidgetState.selected) ? cyan : muted, size: 24)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF070A1C),
        labelStyle: body(14, color: muted),
        hintStyle: body(14, color: dim),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: line)),
        enabledBorder:
            OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: line)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: cyan, width: 1.4)),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: ButtonStyle(
          backgroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? cyan : Colors.transparent),
          foregroundColor: WidgetStateProperty.resolveWith((s) => s.contains(WidgetState.selected) ? bg : text),
          side: const WidgetStatePropertyAll(BorderSide(color: line)),
          textStyle: WidgetStatePropertyAll(body(14, weight: FontWeight.w700)),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
          backgroundColor: panel2, contentTextStyle: body(14), behavior: SnackBarBehavior.floating),
      dividerColor: line,
    );
  }
}
