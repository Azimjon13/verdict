// Who is playing: the player id kept on the phone, the account's token once signed in, the game's dictionaries.
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

const defaultServer = String.fromEnvironment('VERDICT_API', defaultValue: 'https://verdict.azero.uz');

String newVoterId() {
  final r = Random.secure();
  return List.generate(32, (_) => r.nextInt(16).toRadixString(16)).join();
}

class Session extends ChangeNotifier {
  Session(this._prefs, {http.Client? client})
      : api = Api(
          baseUrl: _prefs.getString('server') ?? defaultServer,
          voterId: _prefs.getString('voter') ?? newVoterId(),
          token: _prefs.getString('token'),
          client: client,
        ) {
    _prefs.setString('voter', api.voterId);
    final login = _prefs.getString('login');
    if (api.token != null && login != null) {
      user = {'login': login, 'display_name': _prefs.getString('name') ?? login};
    }
  }

  static Future<Session> load({http.Client? client}) async =>
      Session(await SharedPreferences.getInstance(), client: client);

  final SharedPreferences _prefs;
  final Api api;

  /// The game's dictionaries (GET /catalog): categories, meters, ranks, judge styles, achievements.
  Json catalog = {};
  Json? user;
  int unread = 0;

  bool get signedIn => api.token != null && user != null;
  String get server => api.baseUrl;

  Future<void> loadCatalog() async {
    catalog = await api.get('/catalog');
    notifyListeners();
  }

  Json category(String? key) => (catalog['categories'] as Json?)?[key] as Json? ?? {'name': key ?? '', 'hue': 190};
  Json metrics() => (catalog['metrics'] as Json?) ?? {};
  List<dynamic> ranks() => (catalog['ranks'] as List?) ?? [];

  Future<void> _signedIn(Json out) async {
    api.token = out['token'] as String;
    api.voterId = out['voter_id'] as String;
    user = (out['user'] as Json);
    await _prefs.setString('token', api.token!);
    await _prefs.setString('voter', api.voterId);
    await _prefs.setString('login', user!['login'] as String);
    await _prefs.setString('name', user!['display_name'] as String);
    notifyListeners();
    await refreshMe();
  }

  Future<void> signIn(String login, String password) async =>
      _signedIn(await api.post('/auth/login', {'login': login, 'password': password, 'device': 'Приложение'}));

  Future<void> register(String login, String name, String password) async => _signedIn(await api.post(
      '/auth/register', {'login': login, 'display_name': name, 'password': password, 'device': 'Приложение'}));

  /// Signing out gives the phone a fresh anonymous player, as the website does for a browser.
  Future<void> signOut() async {
    try {
      await api.post('/auth/logout');
    } on ApiException {
      // already gone on the server: forget it here all the same
    }
    await _forget();
  }

  Future<void> _forget() async {
    api.token = null;
    user = null;
    unread = 0;
    api.voterId = newVoterId();
    await _prefs.remove('token');
    await _prefs.remove('login');
    await _prefs.remove('name');
    await _prefs.setString('voter', api.voterId);
    notifyListeners();
  }

  /// The account and its unread notifications; an expired sign-in signs out quietly.
  Future<void> refreshMe() async {
    if (api.token == null) return;
    try {
      final me = await api.get('/me');
      user = me['user'] as Json;
      unread = (me['notifications_unread'] as num?)?.toInt() ?? 0;
      notifyListeners();
    } on ApiException catch (e) {
      if (e.status == 401) await _forget();
    }
  }

  void markRead() {
    unread = 0;
    notifyListeners();
  }

  Future<void> setServer(String url) async {
    var u = url.trim();
    if (u.isEmpty) u = defaultServer;
    if (!u.startsWith('http')) u = 'https://$u';
    api.baseUrl = u;
    await _prefs.setString('server', u);
    notifyListeners();
  }
}
