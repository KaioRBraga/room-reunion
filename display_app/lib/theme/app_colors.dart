import 'package:flutter/material.dart';

/// Paleta espelhando o tema escuro do site (app/static/css/app.css):
/// azul #007BBB + preto, fundo/superfícies em tons de carvão.
class AppColors {
  AppColors._();

  static const primary = Color(0xFF007BBB);
  static const primaryDark = Color(0xFF00688F);
  static const primaryDarker = Color(0xFF00567A);

  static const ink = Color(0xFF0B0B0D);
  static const bg = Color(0xFF11151B);
  static const surface = Color(0xFF1A1F27);
  static const surfaceAlt = Color(0xFF212833);
  static const border = Color(0xFF2B323D);

  static const text = Color(0xFFE7EAF0);
  static const textMuted = Color(0xFF8B93A3);

  static const available = Color(0xFF1F9D55);
  static const startingSoon = Color(0xFFE0A100);
  static const inUse = Color(0xFFDC3545);
}
