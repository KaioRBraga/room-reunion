import 'dart:convert';
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
    final resp = await _http
        .get(_uri('/api/display/status'), headers: _headers)
        .timeout(_requestTimeout, onTimeout: _onTimeout);
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

  /// Envia um frame JPEG para o servidor e retorna o mapa de resposta.
  /// {"status": "checked_in", "user": nome} ou {"status": "no_match"/"no_booking"}.
  Future<Map<String, dynamic>> faceCheckIn(Uint8List jpegFrame) async {
    final request = http.MultipartRequest('POST', _uri('/api/display/face-checkin'))
      ..headers['X-Display-Token'] = token
      ..files.add(http.MultipartFile.fromBytes('frame', jpegFrame, filename: 'frame.jpg'));
    final streamed = await _http
        .send(request)
        .timeout(_faceTimeout, onTimeout: _onTimeout);
    final body = await streamed.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  /// Identifica o usuário pelo rosto e cria uma reserva imediata.
  /// Retorna {"status": "started", "user": nome} ou {"status": "no_match"}.
  Future<Map<String, dynamic>> faceStartNow(Uint8List jpegFrame) async {
    final request = http.MultipartRequest('POST', _uri('/api/display/face-start-now'))
      ..headers['X-Display-Token'] = token
      ..files.add(http.MultipartFile.fromBytes('frame', jpegFrame, filename: 'frame.jpg'));
    final streamed = await _http
        .send(request)
        .timeout(_faceTimeout, onTimeout: _onTimeout);
    final body = await streamed.stream.bytesToString();
    final decoded = jsonDecode(body) as Map<String, dynamic>;
    if (streamed.statusCode >= 400) {
      throw ApiException(decoded['error'] as String? ?? 'Erro ao iniciar reunião.');
    }
    return decoded;
  }

  Future<DisplayStatus> _post(String path, {Map<String, dynamic>? body}) async {
    final resp = await _http
        .post(
          _uri(path),
          headers: _headers,
          body: body != null ? jsonEncode(body) : null,
        )
        .timeout(_requestTimeout, onTimeout: _onTimeout);
    return _parse(resp);
  }

  Never _onTimeout() {
    throw ApiException(
      'Não foi possível conectar ao servidor em $baseUrl (tempo esgotado). '
      'Verifique a rede do dispositivo e a URL configurada.',
    );
  }

  DisplayStatus _parse(http.Response resp) {
    final decoded = jsonDecode(utf8.decode(resp.bodyBytes)) as Map<String, dynamic>;
    if (resp.statusCode >= 400) {
      throw ApiException(decoded['error'] as String? ?? 'Erro de comunicação com o servidor.');
    }
    return DisplayStatus.fromJson(decoded);
  }
}
