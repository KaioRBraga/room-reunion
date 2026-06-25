import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../services/device_config.dart';

/// Lê o QR code gerado na página "Dispositivos" do admin (JSON com `url` e
/// `token`) e devolve um [DeviceConfig] já pronto para uso, evitando que o
/// usuário precise digitar a URL do servidor e o token manualmente.
class QrScanScreen extends StatefulWidget {
  const QrScanScreen({super.key});

  @override
  State<QrScanScreen> createState() => _QrScanScreenState();
}

class _QrScanScreenState extends State<QrScanScreen> {
  // autoZoom: a câmera comum do celular ajusta zoom/foco sozinha e lê esse QR
  // sem problema - o MobileScannerController não faz isso por padrão, e sem
  // dar zoom ele não resolve os módulos do QR a uma distância normal da tela.
  final MobileScannerController _controller = MobileScannerController(autoZoom: true);
  bool _handled = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_handled || capture.barcodes.isEmpty) return;
    final raw = capture.barcodes.first.rawValue;
    if (raw == null) return;

    final config = _parsePayload(raw);
    if (config == null) {
      _showError('QR code inválido. Use o QR gerado na página "Dispositivos" do admin.');
      return;
    }

    _handled = true;
    Navigator.of(context).pop(config);
  }

  DeviceConfig? _parsePayload(String raw) {
    try {
      final data = jsonDecode(raw);
      if (data is! Map) return null;
      final url = (data['url'] as String?)?.trim();
      final token = (data['token'] as String?)?.trim();
      if (url == null || url.isEmpty || token == null || token.isEmpty) return null;
      return DeviceConfig(serverUrl: url, token: token);
    } catch (_) {
      return null;
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Escanear QR code'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () => _controller.toggleTorch(),
            tooltip: 'Lanterna',
          ),
        ],
      ),
      body: MobileScanner(controller: _controller, onDetect: _onDetect),
    );
  }
}
