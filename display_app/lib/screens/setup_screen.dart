import 'package:flutter/material.dart';

import '../services/device_config.dart';
import 'qr_scan_screen.dart';

class SetupScreen extends StatefulWidget {
  final void Function(DeviceConfig) onSaved;
  final String? initialError;

  const SetupScreen({super.key, required this.onSaved, this.initialError});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  final _formKey = GlobalKey<FormState>();
  final _urlController = TextEditingController(text: 'http://');
  final _tokenController = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF222831),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        'Configuração do painel',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Escaneie o QR code da sala na página "Dispositivos" do painel '
                        'admin, ou cole a URL do servidor e o token manualmente.',
                        textAlign: TextAlign.center,
                      ),
                      if (widget.initialError != null) ...[
                        const SizedBox(height: 16),
                        Text(
                          widget.initialError!,
                          style: const TextStyle(color: Colors.red),
                          textAlign: TextAlign.center,
                        ),
                      ],
                      const SizedBox(height: 24),
                      TextFormField(
                        controller: _urlController,
                        decoration: const InputDecoration(
                          labelText: 'URL do servidor',
                          hintText: 'http://10.100.0.20:5000',
                        ),
                        validator: (v) =>
                            (v == null || v.trim().isEmpty) ? 'Informe a URL do servidor' : null,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _tokenController,
                        decoration: const InputDecoration(labelText: 'Token da sala'),
                        validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o token' : null,
                      ),
                      const SizedBox(height: 16),
                      OutlinedButton.icon(
                        onPressed: _saving ? null : _scanQrCode,
                        icon: const Icon(Icons.qr_code_scanner),
                        label: const Text('Escanear QR code'),
                      ),
                      const SizedBox(height: 24),
                      FilledButton(
                        onPressed: _saving ? null : _save,
                        child: _saving
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Salvar e continuar'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _scanQrCode() async {
    final config = await Navigator.of(context).push<DeviceConfig>(
      MaterialPageRoute(builder: (_) => const QrScanScreen()),
    );
    if (config == null || !mounted) return;
    _urlController.text = config.serverUrl;
    _tokenController.text = config.token;
    await _save();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    final serverUrl = _urlController.text.trim().replaceAll(RegExp(r'/+$'), '');
    final token = _tokenController.text.trim();
    await DeviceConfig.save(serverUrl, token);
    if (!mounted) return;
    widget.onSaved(DeviceConfig(serverUrl: serverUrl, token: token));
  }
}
