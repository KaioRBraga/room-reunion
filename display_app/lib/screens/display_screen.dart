import 'dart:async';

import 'package:flutter/material.dart';
import 'package:screen_brightness/screen_brightness.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../models/display_status.dart';
import '../services/api_client.dart';
import '../services/device_config.dart';
import '../theme/app_colors.dart';
import '../widgets/display_body.dart';
import '../widgets/pin_booking_sheet.dart';
import '../widgets/start_now_pin_sheet.dart';

class DisplayScreen extends StatefulWidget {
  final DeviceConfig config;
  final VoidCallback onReconfigure;

  const DisplayScreen({super.key, required this.config, required this.onReconfigure});

  @override
  State<DisplayScreen> createState() => _DisplayScreenState();
}

class _DisplayScreenState extends State<DisplayScreen> {
  late final ApiClient _client;
  DisplayStatus? _status;
  String? _error;
  bool _busy = false;
  Timer? _pollTimer;
  Timer? _tickTimer;

  bool _screenDimmed = false;

  // Agenda por dia recebida do servidor; default até o primeiro poll chegar.
  List<DaySchedule> _screenSchedule = DaySchedule.defaultSchedule();

  bool _isNightHour() {
    final now = DateTime.now();
    // weekday ISO (1=Seg…7=Dom) → convenção servidor (0=Seg…6=Dom)
    final weekday = now.weekday - 1;
    try {
      final day = _screenSchedule.firstWhere((s) => s.day == weekday);
      if (!day.active) return true;
      final h = now.hour;
      return h >= day.offHour || h < day.onHour;
    } catch (_) {
      return false;
    }
  }

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    _client = ApiClient(baseUrl: widget.config.serverUrl, token: widget.config.token);
    _refresh();
    _pollTimer = Timer.periodic(const Duration(seconds: 15), (_) => _refresh());
    _tickTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(() {});
        _applyScreenSchedule();
      }
    });
    _applyScreenSchedule();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _tickTimer?.cancel();
    ScreenBrightness().resetScreenBrightness();
    super.dispose();
  }

  Future<void> _applyScreenSchedule() async {
    final night = _isNightHour();
    if (night == _screenDimmed) return;
    setState(() => _screenDimmed = night);
    if (night) {
      await ScreenBrightness().setScreenBrightness(0.0);
    } else {
      await ScreenBrightness().resetScreenBrightness();
    }
  }

  Future<void> _refresh() async {
    try {
      final status = await _client.fetchStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _error = null;
        _screenSchedule = status.layout.screenSchedule;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  Future<void> _runAction(
    Future<DisplayStatus> Function() action, {
    String? successMessage,
  }) async {
    setState(() => _busy = true);
    try {
      final status = await action();
      if (!mounted) return;
      setState(() {
        _status = status;
        _error = null;
      });
      if (successMessage != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(successMessage)));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _onStartNow() {
    showStartNowPinSheet(
      context: context,
      onSubmit: ({required String username, required String pin}) async {
        final status = await _client.startNow(username: username, pin: pin);
        if (!mounted) return;
        setState(() {
          _status = status;
          _error = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Reserva criada.')),
        );
      },
    );
  }

  void _onSlotTap(DateTime start, DateTime end) {
    showPinBookingSheet(
      context: context,
      start: start,
      end: end,
      onSubmit: ({
        required String username,
        required String pin,
        required String title,
        required int attendeesCount,
        String? virtualRoomUrl,
      }) async {
        final status = await _client.book(
          username: username,
          pin: pin,
          title: title,
          start: start,
          end: end,
          attendeesCount: attendeesCount,
          virtualRoomUrl: virtualRoomUrl,
        );
        if (!mounted) return;
        setState(() {
          _status = status;
          _error = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Reserva criada com sucesso!')),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_screenDimmed) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: _NightOverlay(),
      );
    }

    final status = _status;
    if (status == null) {
      return Scaffold(
        backgroundColor: AppColors.bg,
        body: Center(
          child: _error != null
              ? Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        _error!,
                        style: const TextStyle(color: AppColors.text),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 16),
                      TextButton(
                        onPressed: widget.onReconfigure,
                        style: TextButton.styleFrom(foregroundColor: AppColors.primary),
                        child: const Text('Reconfigurar painel'),
                      ),
                    ],
                  ),
                )
              : const CircularProgressIndicator(color: AppColors.primary),
        ),
      );
    }

    return Scaffold(
      body: GestureDetector(
        onLongPress: widget.onReconfigure,
        child: DisplayBody(
          status: status,
          now: DateTime.now(),
          busy: _busy,
          onCheckIn: () => _runAction(_client.checkIn, successMessage: 'Check-in confirmado!'),
          onEnd: () => _runAction(_client.endMeeting, successMessage: 'Reunião encerrada.'),
          onExtend: () => _runAction(
            () => _client.extend(minutes: 15),
            successMessage: 'Reunião estendida em 15 minutos.',
          ),
          onStartNow: _onStartNow,
          onSlotTap: _onSlotTap,
        ),
      ),
    );
  }
}

// Overlay preto que absorve todos os toques durante o horário noturno.
class _NightOverlay extends StatelessWidget {
  const _NightOverlay();

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {},
      onLongPress: () {},
      child: const SizedBox.expand(
        child: ColoredBox(color: Colors.black),
      ),
    );
  }
}
