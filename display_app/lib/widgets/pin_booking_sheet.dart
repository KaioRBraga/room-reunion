import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

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

  @override
  Widget build(BuildContext context) {
    final timeFormat = DateFormat('HH:mm');
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Agendar ${timeFormat.format(widget.start)} - ${timeFormat.format(widget.end)}',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
              ),
              const SizedBox(height: 4),
              const Text(
                'Apenas para hoje. Use seu usuário e PIN cadastrados no perfil do site.',
                style: TextStyle(color: Colors.black54, fontSize: 12),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _usernameController,
                decoration: const InputDecoration(labelText: 'Usuário'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o usuário' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _pinController,
                decoration: const InputDecoration(labelText: 'PIN'),
                keyboardType: TextInputType.number,
                obscureText: true,
                maxLength: 6,
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o PIN' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _titleController,
                decoration: const InputDecoration(labelText: 'Título da reunião'),
                validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe um título' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _attendeesController,
                decoration: const InputDecoration(labelText: 'Número de participantes'),
                keyboardType: TextInputType.number,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _virtualUrlController,
                decoration: const InputDecoration(labelText: 'URL da sala virtual (opcional)'),
                keyboardType: TextInputType.url,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: _busy
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Agendar'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
