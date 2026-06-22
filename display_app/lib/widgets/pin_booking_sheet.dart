import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../theme/app_colors.dart';

typedef PinBookingSubmit = Future<void> Function({
  required String username,
  required String pin,
  required String title,
  required int attendeesCount,
  String? virtualRoomUrl,
});

Future<void> showPinBookingSheet({
  required BuildContext context,
  required DateTime start,
  required DateTime end,
  required PinBookingSubmit onSubmit,
}) {
  return showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (context) => _PinBookingForm(start: start, end: end, onSubmit: onSubmit),
  );
}

class _PinBookingForm extends StatefulWidget {
  final DateTime start;
  final DateTime end;
  final PinBookingSubmit onSubmit;

  const _PinBookingForm({required this.start, required this.end, required this.onSubmit});

  @override
  State<_PinBookingForm> createState() => _PinBookingFormState();
}

class _PinBookingFormState extends State<_PinBookingForm> {
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _pinController = TextEditingController();
  final _titleController = TextEditingController();
  final _attendeesController = TextEditingController(text: '1');
  final _virtualUrlController = TextEditingController();
  bool _busy = false;
  String? _error;

  // Sugestão de URL (meet.jit.si/<título>) some que o usuário customize o
  // campo - mesma regra usada no agendamento pelo site (calendar.js/room_map.js).
  String? _lastAutoVirtualUrl;

  @override
  void initState() {
    super.initState();
    _titleController.addListener(_updateVirtualUrlSuggestion);
  }

  @override
  void dispose() {
    _titleController.removeListener(_updateVirtualUrlSuggestion);
    _usernameController.dispose();
    _pinController.dispose();
    _titleController.dispose();
    _attendeesController.dispose();
    _virtualUrlController.dispose();
    super.dispose();
  }

  String _slugifyForJitsi(String text) {
    const accented = 'áàãâäéèêëíìîïóòõôöúùûüçñÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇÑ';
    const plain = 'aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN';
    final buffer = StringBuffer();
    for (final rune in text.runes) {
      final ch = String.fromCharCode(rune);
      final idx = accented.indexOf(ch);
      buffer.write(idx >= 0 ? plain[idx] : ch);
    }
    return buffer
        .toString()
        .replaceAll(RegExp(r'[^a-zA-Z0-9\s]'), '')
        .trim()
        .replaceAll(RegExp(r'\s+'), '_');
  }

  void _updateVirtualUrlSuggestion() {
    final current = _virtualUrlController.text.trim();
    if (current.isNotEmpty && current != _lastAutoVirtualUrl) {
      return; // usuário digitou uma URL própria - não sobrescreve
    }
    final slug = _slugifyForJitsi(_titleController.text);
    final suggestion = slug.isEmpty ? '' : 'https://meet.jit.si/$slug';
    _lastAutoVirtualUrl = suggestion;
    _virtualUrlController.text = suggestion;
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.onSubmit(
        username: _usernameController.text.trim(),
        pin: _pinController.text.trim(),
        title: _titleController.text.trim(),
        attendeesCount: int.tryParse(_attendeesController.text.trim()) ?? 1,
        virtualRoomUrl:
            _virtualUrlController.text.trim().isEmpty ? null : _virtualUrlController.text.trim(),
      );
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  InputDecoration _decoration(String label) {
    return InputDecoration(
      labelText: label,
      labelStyle: const TextStyle(color: AppColors.textMuted),
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
    final timeFormat = DateFormat('HH:mm');
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 12,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Text(
                'Agendar ${timeFormat.format(widget.start)} - ${timeFormat.format(widget.end)}',
                style: const TextStyle(color: AppColors.text, fontWeight: FontWeight.bold, fontSize: 18),
              ),
              const SizedBox(height: 4),
              const Text(
                'Apenas para hoje. Use seu usuário e PIN cadastrados no perfil do site.',
                style: TextStyle(color: AppColors.textMuted, fontSize: 12),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _usernameController,
                style: const TextStyle(color: AppColors.text),
                decoration: _decoration('Usuário'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o usuário' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _pinController,
                style: const TextStyle(color: AppColors.text),
                decoration: _decoration('PIN'),
                keyboardType: TextInputType.number,
                obscureText: true,
                maxLength: 6,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o PIN' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _titleController,
                style: const TextStyle(color: AppColors.text),
                decoration: _decoration('Título da reunião'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe um título' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _attendeesController,
                style: const TextStyle(color: AppColors.text),
                decoration: _decoration('Número de participantes'),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _virtualUrlController,
                style: const TextStyle(color: AppColors.text),
                decoration: _decoration('URL da sala virtual (opcional)'),
                keyboardType: TextInputType.url,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.redAccent)),
              ],
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _busy ? null : _submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  child: _busy
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Agendar', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
