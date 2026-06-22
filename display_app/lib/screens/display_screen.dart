import 'dart:async';

import 'package:flutter/material.dart';

import '../models/display_status.dart';
import '../services/api_client.dart';
import '../services/device_config.dart';
import '../theme/app_colors.dart';
import '../widgets/display_body.dart';
import '../widgets/pin_booking_sheet.dart';

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

  @override
  void initState() {
    super.initState();
    _client = ApiClient(baseUrl: widget.config.serverUrl, token: widget.config.token);
    _refresh();
    _pollTimer = Timer.periodic(const Duration(seconds: 15), (_) => _refresh());
    _tickTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _tickTimer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final status = await _client.fetchStatus();
      if (!mounted) return;
      setState(() {
        _status = status;
        _error = null;
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
          onStartNow: () => _runAction(_client.startNow, successMessage: 'Reserva criada.'),
          onSlotTap: _onSlotTap,
        ),
      ),
    );
  }
}
