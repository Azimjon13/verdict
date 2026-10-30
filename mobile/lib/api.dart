// The VERDICT game API (/api/v1): every request carries the player's id, and the account's token once signed in.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

typedef Json = Map<String, dynamic>;

class ApiException implements Exception {
  ApiException(this.status, this.message, {this.code, this.body});

  /// HTTP status; 0 when the server couldn't be reached.
  final int status;

  /// A Russian message the server meant for the player (or ours, for network trouble).
  final String message;
  final String? code;
  final Json? body;

  bool get offline => status == 0;

  @override
  String toString() => message;
}

class Api {
  Api({required this.baseUrl, required this.voterId, this.token, http.Client? client})
      : client = client ?? http.Client();

  String baseUrl;
  String voterId;
  String? token;
  final http.Client client;
  static const timeout = Duration(seconds: 20);

  Uri _uri(String path, [Map<String, String>? query]) {
    final base = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    return Uri.parse('$base/api/v1$path').replace(queryParameters: query);
  }

  Map<String, String> get _headers => {
        'X-Voter-Id': voterId,
        'Accept': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<Json> get(String path, {Map<String, String>? query}) =>
      _send(() => client.get(_uri(path, query), headers: _headers));

  Future<Json> post(String path, [Json? body]) => _send(() => client.post(_uri(path),
      headers: {..._headers, 'Content-Type': 'application/json'}, body: jsonEncode(body ?? const {})));

  Future<Json> _send(Future<http.Response> Function() request) async {
    http.Response r;
    try {
      r = await request().timeout(timeout);
    } on TimeoutException {
      throw ApiException(0, 'Сервер не отвечает. Попробуйте ещё раз.');
    } on http.ClientException {
      throw ApiException(0, 'Нет связи с сервером. Проверьте интернет.');
    }
    Json body;
    try {
      final decoded = jsonDecode(utf8.decode(r.bodyBytes));
      body = decoded is Map<String, dynamic> ? decoded : {'ok': false};
    } on FormatException {
      throw ApiException(r.statusCode, 'Сервер ответил не так, как ожидалось (${r.statusCode}).');
    }
    if (r.statusCode >= 400 || body['ok'] == false) {
      throw ApiException(r.statusCode, (body['error'] as String?) ?? 'Ошибка сервера (${r.statusCode}).',
          code: body['code'] as String?, body: body);
    }
    return body;
  }
}
