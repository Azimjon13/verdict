// The app against a fake server that answers with real API responses (test/fixtures, saved from the site).
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:verdict_mobile/main.dart';
import 'package:verdict_mobile/session.dart';
import 'package:verdict_mobile/widgets.dart';

String fixture(String name) => File('test/fixtures/$name.json').readAsStringSync();

class FakeServer {
  final requests = <http.Request>[];

  late final client = MockClient((req) async {
    requests.add(req);
    final path = req.url.path.replaceFirst('/api/v1', '');
    var status = 200;
    String body;
    switch (path) {
      case '/catalog':
        body = fixture('catalog');
      case '/profile':
        body = fixture('profile');
      case '/daily':
        body = fixture('daily');
      case '/world':
        body = fixture('world');
      case '/cases':
        body = fixture('cases');
      case '/ratings':
        body = fixture('ratings');
      case '/quick/next':
        body = fixture('quick_next');
      case '/cases/17/verdict':
        body = fixture('verdict');
      case '/cases/17/comments':
        status = 403;
        body = fixture('comments_locked');
      case '/auth/login':
        status = 401;
        body = jsonEncode({'ok': false, 'error': 'Неверный логин или пароль.'});
      default:
        status = 404;
        body = jsonEncode({'ok': false, 'error': 'Не найдено.'});
    }
    return http.Response.bytes(utf8.encode(body), status, headers: {'content-type': 'application/json; charset=utf-8'});
  });

  Iterable<String> get paths => requests.map((r) => r.url.path.replaceFirst('/api/v1', ''));
}

/// The case-of-the-day countdown ticks every second, so «settle» is a number of short pumps.
Future<void> settle(WidgetTester tester, [int steps = 12]) async {
  for (var i = 0; i < steps; i++) {
    await tester.pump(const Duration(milliseconds: 120));
  }
}

Future<FakeServer> start(WidgetTester tester) async {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 3;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues({});
  final server = FakeServer();
  final session = await Session.load(client: server.client);
  await tester.pumpWidget(VerdictApp(session: session));
  await settle(tester);
  return server;
}

/// Lists build lazily: scroll the screen's main list until the text is built.
Future<void> scrollTo(WidgetTester tester, String text) async {
  await tester.scrollUntilVisible(find.text(text), 250, scrollable: find.byType(Scrollable).first);
  await tester.pump();
}

Future<void> tapText(WidgetTester tester, String text) async {
  final f = find.text(text).last;
  await tester.ensureVisible(f);
  await tester.pump();
  await tester.tap(f);
  await settle(tester);
}

void main() {
  testWidgets('home: rank, the case of the day, Быстрый суд; every request carries the player id', (tester) async {
    final server = await start(tester);
    final daily = jsonDecode(fixture('daily'))['case']['title'] as String;
    expect(find.text('VERDICT'), findsWidgets);
    expect(find.text('Стажёр'), findsOneWidget);
    expect(find.text(daily), findsOneWidget);
    expect(find.text('Быстрый суд'), findsOneWidget);
    expect(server.paths, containsAll(['/catalog', '/profile', '/daily']));
    final ids = server.requests.map((r) => r.headers['X-Voter-Id']).toSet();
    expect(ids, hasLength(1));
    expect(ids.single, matches(RegExp(r'^[0-9a-f]{32}$')));
  });

  testWidgets('Быстрый суд: frames, a verdict, the guess, the result', (tester) async {
    final server = await start(tester);
    await tapText(tester, 'Быстрый суд');
    expect(find.text('Шёпот у смертного ложа'), findsWidgets);
    expect(find.textContaining('Ваша роль'), findsOneWidget);
    await tapText(tester, 'К вердикту');
    expect(find.text('Ваш вердикт'), findsOneWidget);
    await tapText(tester, 'Записать волю короля: наследник — Тео');
    expect(find.text('Как решило большинство?'), findsOneWidget);
    await tapText(tester, 'Промолчать: корона переходит Альрику по закону');
    final sent = server.requests.lastWhere((r) => r.url.path.endsWith('/verdict'));
    final body = jsonDecode(sent.body) as Map<String, dynamic>;
    expect(body['option'], 'A');
    expect(body['guess'], 'B');
    expect(body['mode'], 'quick');
    await settle(tester, 20);
    expect(find.text('Вы угадали большинство!'), findsOneWidget);
    await scrollTo(tester, 'Как решили судьи');
    await scrollTo(tester, 'Следующее дело');
    await tapText(tester, 'Обсуждение');
    expect(find.text('Обсуждение откроется после вашего вердикта'), findsOneWidget);
  });

  testWidgets('archive: every case, filtered by category', (tester) async {
    await start(tester);
    await tester.tap(find.text('Архив').last);
    await settle(tester);
    final cases = (jsonDecode(fixture('cases'))['cases'] as List).cast<Map<String, dynamic>>();
    expect(find.text('Архив дел'), findsOneWidget);
    expect(find.text(cases.first['title'] as String), findsOneWidget);
    final catalog = jsonDecode(fixture('catalog')) as Map<String, dynamic>;
    final first = (catalog['categories'] as Map<String, dynamic>).entries.first;  // its chip is on screen
    await tapText(tester, first.value['name'] as String);
    final other = cases.firstWhere((c) => c['category'] != first.key)['title'] as String;
    expect(find.text(other), findsNothing);
    final same = cases.firstWhere((c) => c['category'] == first.key)['title'] as String;
    await scrollTo(tester, same);
  });

  testWidgets('sign-in shows the server\'s message', (tester) async {
    await start(tester);
    await tester.tap(find.text('Войти').last);
    await settle(tester);
    await tester.enterText(find.widgetWithText(TextField, 'Логин'), 'nobody');
    await tester.enterText(find.widgetWithText(TextField, 'Пароль'), 'wrong-password');
    await tester.tap(find.widgetWithText(GradientButton, 'Войти'));
    await settle(tester);
    expect(find.text('Неверный логин или пароль.'), findsOneWidget);
  });

  testWidgets('ratings and the judge profile load', (tester) async {
    await start(tester);
    await tester.tap(find.text('Рейтинг').last);
    await settle(tester);
    expect(find.text('Рейтинг судей'), findsOneWidget);
    await tester.tap(find.text('Судья').last);
    await settle(tester);
    expect(find.text('Профиль судьи'), findsOneWidget);
    await scrollTo(tester, 'Ваш мир');
  });

  test('dates as the website writes them', () {
    expect(ruDate('2026-10-29T09:05:00Z').endsWith('.10.2026'), isTrue);
    expect(ruDate('2026-10-29T09:05:00Z', time: true), matches(RegExp(r'^\d\d\.10\.2026 \d\d:05$')));
    expect(ruDate('nonsense'), 'nonsense');
  });

  test('a fresh player id per phone, kept, and a new one after signing out', () async {
    SharedPreferences.setMockInitialValues({});
    final a = await Session.load(client: FakeServer().client);
    final b = await Session.load(client: FakeServer().client);
    expect(a.api.voterId, b.api.voterId); // kept between launches
    expect(newVoterId(), isNot(a.api.voterId));
    await a.signOut();
    expect(a.api.voterId, isNot(b.api.voterId));
    expect(a.signedIn, isFalse);
  });
}
