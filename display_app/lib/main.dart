import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'screens/display_screen.dart';
import 'screens/setup_screen.dart';
import 'services/device_config.dart';
import 'theme/app_colors.dart';

void main() {
  runApp(const ReadyRoomDisplayApp());
}

class ReadyRoomDisplayApp extends StatelessWidget {
  const ReadyRoomDisplayApp({super.key});

  @override
  Widget build(BuildContext context) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: Brightness.dark,
      primary: AppColors.primary,
      surface: AppColors.surface,
    );
    final textTheme = GoogleFonts.interTextTheme(ThemeData.dark().textTheme);

    return MaterialApp(
      title: 'ReadyRoom Display',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        colorScheme: colorScheme,
        scaffoldBackgroundColor: AppColors.bg,
        textTheme: textTheme,
        fontFamily: GoogleFonts.inter().fontFamily,
      ),
      home: const RootScreen(),
    );
  }
}

class RootScreen extends StatefulWidget {
  const RootScreen({super.key});

  @override
  State<RootScreen> createState() => _RootScreenState();
}

class _RootScreenState extends State<RootScreen> {
  DeviceConfig? _config;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final config = await DeviceConfig.load();
    if (!mounted) return;
    setState(() {
      _config = config;
      _loading = false;
    });
  }

  void _onConfigured(DeviceConfig config) {
    setState(() => _config = config);
  }

  void _onReconfigure() {
    setState(() => _config = null);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final config = _config;
    if (config == null) {
      return SetupScreen(onSaved: _onConfigured);
    }
    return DisplayScreen(config: config, onReconfigure: _onReconfigure);
  }
}
