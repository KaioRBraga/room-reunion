import 'package:flutter/material.dart';

import '../services/device_config.dart';
import '../theme/app_colors.dart';
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

  InputDecoration _inputDecoration(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      labelStyle: const TextStyle(color: AppColors.textMuted),
      hintStyle: const TextStyle(color: AppColors.textMuted),
      filled: true,
      fillColor: AppColors.surfaceAlt,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Container(
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.border),
              ),
              padding: const EdgeInsets.all(28),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Text(
                      'Configuração do painel',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppColors.text,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Escaneie o QR code da sala na página "Dispositivos" do painel '
                      'admin, ou cole a URL do servidor e o token manualmente.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                    ),
                    if (widget.initialError != null) ...[
                      const SizedBox(height: 16),
                      Text(
                        widget.initialError!,
                        style: const TextStyle(color: Colors.redAccent),
                        textAlign: TextAlign.center,
                      ),
                    ],
                    const SizedBox(height: 24),
                    TextFormField(
                      controller: _urlController,
                      style: const TextStyle(color: AppColors.text),
                      decoration: _inputDecoration('URL do servidor', hint: 'http://10.100.0.20:5000'),
                      validator: (v) =>
                          (v == null || v.trim().isEmpty) ? 'Informe a URL do servidor' : null,
                    ),
                    const SizedBox(height: 16),
                    TextFormField(
                      controller: _tokenController,
                      style: const TextStyle(color: AppColors.text),
                      decoration: _inputDecoration('Token da sala'),
                      validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o token' : null,
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: _saving ? null : _scanQrCode,
                      icon: const Icon(Icons.qr_code_scanner),
                      label: const Text('Escanear QR code'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.primary,
                        side: const BorderSide(color: AppColors.border),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Opacity(
                      opacity: _saving ? 0.6 : 1.0,
                      child: Material(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(999),
                        clipBehavior: Clip.antiAlias,
                        elevation: 0,
                        child: InkWell(
                          onTap: _saving ? null : _save,
                          splashColor: Colors.black.withValues(alpha: 0.08),
                          highlightColor: Colors.black.withValues(alpha: 0.04),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            alignment: Alignment.center,
                            child: _saving
                                ? const SizedBox(
                                    height: 18,
                                    width: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Color(0xFF0F172A),
                                    ),
                                  )
                                : const Text(
                                    'Salvar e continuar',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      color: Color(0xFF0F172A),
                                      fontSize: 15,
                                    ),
                                  ),
                          ),
                        ),
                      ),
                    ),
                  ],
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
