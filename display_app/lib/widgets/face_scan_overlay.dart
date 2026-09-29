import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../services/api_client.dart';

/// Varredura facial silenciosa: captura frames periódicos com a câmera frontal
/// e envia ao servidor. Quando reconhecido, exibe overlay verde por 3 s e
/// chama [onCheckInSuccess].
///
/// Deve ser montado quando o status da sala for "starting_soon" e desmontado
/// quando o check-in for concluído ou a reserva sair da janela de aviso.
class FaceScanOverlay extends StatefulWidget {
  final ApiClient api;
  final void Function(String userName) onCheckInSuccess;

  const FaceScanOverlay({
    super.key,
    required this.api,
    required this.onCheckInSuccess,
  });

  @override
  State<FaceScanOverlay> createState() => _FaceScanOverlayState();
}

class _FaceScanOverlayState extends State<FaceScanOverlay> {
  CameraController? _ctrl;
  Timer? _timer;
  bool _scanning = false;
  bool _showSuccess = false;
  String _successName = '';

  static const _interval = Duration(milliseconds: 2500);
  static const _successDuration = Duration(seconds: 3);

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    final cameras = await availableCameras();
    // Prefere câmera frontal; cai para a primeira disponível se não houver.
    final cam = cameras.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.front,
      orElse: () => cameras.first,
    );
    final ctrl = CameraController(cam, ResolutionPreset.low, enableAudio: false);
    await ctrl.initialize();
    if (!mounted) {
      await ctrl.dispose();
      return;
    }
    setState(() => _ctrl = ctrl);
    _timer = Timer.periodic(_interval, (_) => _captureAndSend());
  }

  Future<void> _captureAndSend() async {
    if (_scanning || _showSuccess || _ctrl == null || !_ctrl!.value.isInitialized) return;
    _scanning = true;
    try {
      final xfile = await _ctrl!.takePicture();
      final bytes = await File(xfile.path).readAsBytes();
      final result = await widget.api.faceCheckIn(bytes);
      if (result['status'] == 'checked_in' && mounted) {
        _timer?.cancel();
        setState(() {
          _showSuccess = true;
          _successName = result['user'] as String? ?? '';
        });
        Future.delayed(_successDuration, () {
          if (mounted) widget.onCheckInSuccess(_successName);
        });
      }
    } catch (_) {
      // Erros de rede/câmera são silenciosos — tenta novamente no próximo ciclo.
    } finally {
      _scanning = false;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _ctrl?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_showSuccess) {
      return _SuccessBanner(name: _successName);
    }
    // Indicador discreto de câmera ativa (ícone no canto).
    return Positioned(
      bottom: 16,
      right: 16,
      child: Tooltip(
        message: 'Reconhecimento facial ativo',
        child: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.black54,
            borderRadius: BorderRadius.circular(8),
          ),
          child: const Icon(Icons.face_retouching_natural, color: Colors.white70, size: 20),
        ),
      ),
    );
  }
}

class _SuccessBanner extends StatelessWidget {
  final String name;
  const _SuccessBanner({required this.name});

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: Container(
        color: Colors.black.withAlpha(180),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle_outline, color: Color(0xFF1f9d55), size: 72),
            const SizedBox(height: 16),
            Text(
              'Check-in realizado',
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
            ),
            if (name.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                name,
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(color: Colors.white70),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
