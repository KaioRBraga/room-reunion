import 'package:shared_preferences/shared_preferences.dart';

class DeviceConfig {
  static const _keyServerUrl = 'server_url';
  static const _keyToken = 'display_token';

  final String serverUrl;
  final String token;

  DeviceConfig({required this.serverUrl, required this.token});

  static Future<DeviceConfig?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final serverUrl = prefs.getString(_keyServerUrl);
    final token = prefs.getString(_keyToken);
    if (serverUrl == null || token == null || serverUrl.isEmpty || token.isEmpty) {
      return null;
    }
    return DeviceConfig(serverUrl: serverUrl, token: token);
  }

  static Future<void> save(String serverUrl, String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyServerUrl, serverUrl);
    await prefs.setString(_keyToken, token);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyServerUrl);
    await prefs.remove(_keyToken);
  }
}
