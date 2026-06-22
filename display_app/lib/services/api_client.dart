import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/display_status.dart';

const _requestTimeout = Duration(seconds: 8);

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

  Future<DisplayStatus> startNow({String title = 'Reunião via painel'}) =>
      _post('/api/display/start-now', body: {'title': title});

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
