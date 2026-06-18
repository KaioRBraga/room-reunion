import 'package:flutter/material.dart';

import 'screens/display_screen.dart';
import 'screens/setup_screen.dart';
import 'services/device_config.dart';

void main() {
  runApp(const ReadyRoomDisplayApp());
}

class ReadyRoomDisplayApp extends StatelessWidget {
  const ReadyRoomDisplayApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ReadyRoom Display',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
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
