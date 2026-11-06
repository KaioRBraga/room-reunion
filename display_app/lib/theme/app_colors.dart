import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  static const primary = Color(0xFF45BEE1);
  static const primaryDark = Color(0xFF004E6F);
  static const primaryDarker = Color(0xFF003A56);

  static const ink = Color(0xFF020617);
  static const bg = Color(0xFF060D14);
  static const surface = Color(0xFF0F172A);
  static const surfaceAlt = Color(0xFF1E293B);
  static const border = Color(0xFF334155);

  static const text = Color(0xFFE8EBF0);
  static const textMuted = Color(0xFF94A3B8);

  static const available = Color(0xFF1F9D55);
  static const startingSoon = Color(0xFFE0A100);
  static const inUse = Color(0xFFDC3545);

  static const LinearGradient brandGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [primaryDark, primary],
  );
}
