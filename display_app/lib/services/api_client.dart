import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/display_status.dart';

const _requestTimeout = Duration(seconds: 8);
const _faceTimeout = Duration(seconds: 20);

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  final String token;
  final http.Client _http;

  ApiClient({required this.baseUrl, required this.token, http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'X-Display-Token': token,
      };

  Future<DisplayStatus> fetchStatus() async {
    final resp = await _guard(() => _http
        .get(_uri('/api/display/status'), headers: _headers)
        .timeout(_requestTimeout, onTimeout: _onTimeout));
    return _parse(resp);
  }

  Future<DisplayStatus> checkIn() => _post('/api/display/check-in');

  Future<DisplayStatus> endMeeting() => _post('/api/display/end');

  Future<DisplayStatus> extend({int minutes = 15}) =>
      _post('/api/display/extend', body: {'minutes': minutes});

  Future<DisplayStatus> startNow({
    required String username,
    required String pin,
    String title = 'Reunião via painel',
  }) =>
      _post('/api/display/start-now', body: {
        'username': username,
        'pin': pin,
        'title': title,
      });

  Future<DisplayStatus> book({
    required String username,
    required String pin,
    required String title,
    required DateTime start,
    required DateTime end,
    int attendeesCount = 1,
    String? virtualRoomUrl,
  }) =>
      _post('/api/display/book', body: {
        'username': username,
        'pin': pin,
        'title': title,
        'start': start.toIso8601String(),
        'end': end.toIso8601String(),
        'attendees_count': attendeesCount,
        if (virtualRoomUrl != null && virtualRoomUrl.isNotEmpty) 'virtual_room_url': virtualRoomUrl,
      });

  void close() => _http.close();

  // Converte erros de rede (socket, TLS) em ApiException com mensagem legível.
  Future<T> _guard<T>(Future<T> Function() fn) async {
    try {
      return await fn();
    } on SocketException {
      throw ApiException('Sem conexão com o servidor. Verifique a rede do dispositivo.');
    } on HandshakeException {
      throw ApiException('Erro de certificado TLS na conexão com o servidor.');
    }
  }

  /// Envia um frame JPEG para o servidor e retorna o mapa de resposta.
  /// {"status": "checked_in", "user": nome} ou {"status": "no_match"/"no_booking"}.
  Future<Map<String, dynamic>> faceCheckIn(Uint8List jpegFrame) async {
    final request = http.MultipartRequest('POST', _uri('/api/display/face-checkin'))
      ..headers['X-Display-Token'] = token
      ..files.add(http.MultipartFile.fromBytes('frame', jpegFrame, filename: 'frame.jpg'));
    final streamed = await _guard(() => _http
        .send(request)
        .timeout(_faceTimeout, onTimeout: _onTimeout));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode >= 400) {
      Map<String, dynamic>? decoded;
      try {
        decoded = jsonDecode(body) as Map<String, dynamic>;
      } on FormatException {
        // corpo não é JSON (ex.: texto "Unauthorized")
      }
      throw ApiException(decoded?['error'] as String? ?? 'Erro ao processar reconhecimento (HTTP ${streamed.statusCode}).');
    }
    return jsonDecode(body) as Map<String, dynamic>;
  }

  /// Identifica o usuário pelo rosto e cria uma reserva imediata.
  /// Retorna {"status": "started", "user": nome} ou {"status": "no_match"}.
  Future<Map<String, dynamic>> faceStartNow(Uint8List jpegFrame) async {
    final request = http.MultipartRequest('POST', _uri('/api/display/face-start-now'))
      ..headers['X-Display-Token'] = token
      ..files.add(http.MultipartFile.fromBytes('frame', jpegFrame, filename: 'frame.jpg'));
    final streamed = await _guard(() => _http
        .send(request)
        .timeout(_faceTimeout, onTimeout: _onTimeout));
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode >= 400) {
      Map<String, dynamic>? decoded;
      try {
        decoded = jsonDecode(body) as Map<String, dynamic>;
      } on FormatException {
        // corpo não é JSON (ex.: texto "Unauthorized")
      }
      throw ApiException(decoded?['error'] as String? ?? 'Erro ao iniciar reunião (HTTP ${streamed.statusCode}).');
    }
    return jsonDecode(body) as Map<String, dynamic>;
  }

  Future<DisplayStatus> _post(String path, {Map<String, dynamic>? body}) async {
    final resp = await _guard(() => _http
        .post(
          _uri(path),
          headers: _headers,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(_requestTimeout, onTimeout: _onTimeout));
    return _parse(resp);
  }

  Never _onTimeout() {
    throw ApiException(
      'Não foi possível conectar ao servidor em $baseUrl (tempo esgotado). '
      'Verifique a rede do dispositivo e a URL configurada.',
    );
  }

  DisplayStatus _parse(http.Response resp) {
    final Map<String, dynamic> decoded;
    try {
      final json = jsonDecode(utf8.decode(resp.bodyBytes));
      if (json is! Map<String, dynamic>) {
        throw ApiException('Resposta inesperada do servidor (HTTP ${resp.statusCode}).');
      }
      decoded = json;
    } on FormatException {
      throw ApiException(
        'Resposta inválida do servidor (HTTP ${resp.statusCode}). '
        'Verifique se a URL está correta e aponta para o ReadyRoom.',
      );
    }
    if (resp.statusCode >= 400) {
      throw ApiException(decoded['error'] as String? ?? 'Erro de comunicação com o servidor.');
    }
    return DisplayStatus.fromJson(decoded);
  }
}
