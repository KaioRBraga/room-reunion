import 'dart:async';
import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../theme/app_colors.dart';

/// Abre bottom sheet com câmera frontal para identificar o usuário e criar
/// uma reserva imediata sem necessidade de PIN.
/// [onFallback] é chamado após fechar o sheet quando o rosto não é reconhecido,
/// para abrir o fluxo normal de PIN.
Future<void> showFaceStartNowSheet({
  required BuildContext context,
  required ApiClient api,
  required VoidCallback onSuccess,
  VoidCallback? onFallback,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (_) => _FaceStartNowBody(api: api, onSuccess: onSuccess, onFallback: onFallback),
  );
}

class _FaceStartNowBody extends StatefulWidget {
  final ApiClient api;
  final VoidCallback onSuccess;
  final VoidCallback? onFallback;

  const _FaceStartNowBody({
    required this.api,
    required this.onSuccess,
    this.onFallback,
  });

  @override
  State<_FaceStartNowBody> createState() => _FaceStartNowBodyState();
}

class _FaceStartNowBodyState extends State<_FaceStartNowBody> {
  CameraController? _ctrl;
  bool _busy = false;
  String? _error;
  String? _successName;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        if (mounted) setState(() => _error = 'Nenhuma câmera disponível.');
        return;
      }
      final cam = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      final ctrl = CameraController(cam, ResolutionPreset.low, enableAudio: false);
      await ctrl.initialize();
      if (!mounted) { await ctrl.dispose(); return; }
      setState(() => _ctrl = ctrl);
      // Aguarda um frame para a câmera estabilizar antes de capturar
      await Future.delayed(const Duration(milliseconds: 600));
      if (mounted) _capture();
    } catch (e) {
      if (mounted) setState(() => _error = 'Câmera indisponível: $e');
    }
  }

  Future<void> _capture() async {
    if (_ctrl == null || !_ctrl!.value.isInitialized || _busy) return;
    setState(() { _busy = true; _error = null; });
    try {
      final xfile = await _ctrl!.takePicture();
      final bytes = await File(xfile.path).readAsBytes();
      final result = await widget.api.faceStartNow(bytes);
      if (!mounted) return;
      if (result['status'] == 'started') {
        setState(() => _successName = result['user'] as String? ?? '');
        await Future.delayed(const Duration(seconds: 2));
        if (mounted) {
          Navigator.of(context).pop();
          widget.onSuccess();
        }
      } else {
        setState(() => _error = 'Rosto não reconhecido. Tente novamente.');
        await Future.delayed(const Duration(seconds: 2));
        if (mounted) {
          Navigator.of(context).pop();
          widget.onFallback?.call();
        }
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Erro ao processar imagem.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _ctrl?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Center(
            child: Container(
              width: 36, height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
          const Text(
            'Iniciar reunião com rosto',
            style: TextStyle(color: AppColors.text, fontWeight: FontWeight.bold, fontSize: 18),
          ),
          const SizedBox(height: 4),
          const Text(
            'Posicione-se de frente para a câmera.',
            style: TextStyle(color: AppColors.textMuted, fontSize: 12),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          if (_successName != null) ...[
            const Icon(Icons.check_circle, color: Color(0xFF1f9d55), size: 56),
            const SizedBox(height: 8),
            Text(
              'Olá, $_successName! Reunião iniciada.',
              style: const TextStyle(color: AppColors.text, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
          ] else ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: _ctrl != null && _ctrl!.value.isInitialized
                  ? SizedBox(
                      height: 240,
                      child: CameraPreview(_ctrl!),
                    )
                  : Container(
                      height: 240,
                      color: AppColors.surfaceAlt,
                      child: const Center(
                        child: CircularProgressIndicator(color: AppColors.primary),
                      ),
                    ),
            ),
            const SizedBox(height: 12),
            if (_busy)
              const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: AppColors.primary),
                  ),
                  SizedBox(width: 8),
                  Text('Identificando…', style: TextStyle(color: AppColors.textMuted, fontSize: 13)),
                ],
              )
            else if (_error != null)
              Text(
                _error!,
                style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                textAlign: TextAlign.center,
              ),
          ],
        ],
      ),
    );
  }
}
