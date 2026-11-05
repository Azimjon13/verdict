// The app against a fake server that answers with real API responses (test/fixtures, saved from the site).
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:verdict_mobile/links.dart';
import 'package:verdict_mobile/main.dart';
import 'package:verdict_mobile/screens/communities.dart';
import 'package:verdict_mobile/screens/profile.dart';
import 'package:verdict_mobile/screens/result_screen.dart';
import 'package:verdict_mobile/screens/talk.dart';
import 'package:verdict_mobile/session.dart';
import 'package:verdict_mobile/widgets.dart';

String fixture(String name) => File('test/fixtures/$name.json').readAsStringSync();

class FakeServer {
  FakeServer({this.telegramReady = false});

  final requests = <http.Request>[];
  final bool telegramReady;
  int _chosen = 0;
  final _claimed = <int>{};
  bool _joined = false;

  /// GET /hunt without the spots found so far.
  String _hunt() {
    final h = jsonDecode(fixture('hunt')) as Map<String, dynamic>;
    h['spots'] = (h['spots'] as List).where((x) => !_claimed.contains(x['id'])).toList();
    return jsonEncode(h);
  }

  /// GET /communities/`<slug>`: the fixture's player is a member once they joined here.
  String _community() {
    final c = jsonDecode(fixture('community')) as Map<String, dynamic>;
    c['me'] = _joined ? {'status': 'active', 'role': 'member'} : null;
    return jsonEncode(c);
  }

  String _me() {
    final m = jsonDecode(fixture('me')) as Map<String, dynamic>;
    m['telegram'] = {'linked': false, 'bot': telegramReady ? 'verdict_bot' : null, 'ready': telegramReady};
    if (!_joined) m['communities'] = [];
    return jsonEncode(m);
  }

  late final client = MockClient((req) async {
    requests.add(req);
    final path = req.url.path.replaceFirst('/api/v1', '');
    var status = 200;
    String body;
    switch (path) {
      case '/hunt':
        body = _hunt();
      case '/hunt/spots/6/claim':
        _claimed.add(6);
        body = fixture('hunt_claim');
      case '/communities':
        body = fixture('communities');
      case '/communities/klub-strogikh-sudey':
        body = _community();
      case '/communities/klub-strogikh-sudey/join':
        _joined = true;
        body = jsonEncode({'ok': true, 'result': 'joined'});
      case '/me':
        body = _me();
      case '/me/profile':
      case '/notifications/read':
        body = jsonEncode({'ok': true, 'unread': 0});
      case '/notifications':
        body = jsonEncode({
          'ok': true,
          'unread': 1,
          'items': [
            {
              'id': 1,
              'kind': 'community_joined',
              'icon': 'users',
              'text': 'Вас приняли в сообщество «Клуб строгих судей».',
              'link': '/c/klub-strogikh-sudey',
              'created_at': '2026-11-05T09:00:00Z',
              'read': false,
            },
          ],
        });
      case '/friends':
        body = fixture('friends');
      case '/reports':
        body = jsonEncode({'ok': true, 'new': true});
      case '/campaigns':
        body = fixture('campaigns');
      case '/campaigns/rubezh':
        body = fixture('campaign');
      case '/campaigns/rubezh/start':
        body = fixture('campaign_start');
      case '/campaigns/rubezh/choose':
        body = fixture(['campaign_choose1', 'campaign_choose2', 'campaign_end'][_chosen++ % 3]);
      case '/gifts':
        body = fixture('gifts');
      case '/seasons':
        body = fixture('seasons');
      case '/users/player1':
      case '/users/player2':
        body = fixture('user');
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

/// The app on a phone; [signedIn] — as player1 of the fixtures, with a saved token.
Future<FakeServer> start(WidgetTester tester, {bool signedIn = false, bool telegram = false}) async {
  tester.view.physicalSize = const Size(1080, 2340);
  tester.view.devicePixelRatio = 3;
  addTearDown(tester.view.reset);
  SharedPreferences.setMockInitialValues(
    signedIn ? {'token': 'test-token', 'login': 'player1', 'name': 'Анна Ветрова'} : {},
  );
  final server = FakeServer(telegramReady: telegram);
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
    final first = (catalog['categories'] as Map<String, dynamic>).entries.first; // its chip is on screen
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

  testWidgets('a campaign: start, a chapter, its consequences, what came of it', (tester) async {
    final server = await start(tester);
    await scrollTo(tester, 'Последний Рубеж');
    await tapText(tester, 'Последний Рубеж');
    expect(find.text('Начать кампанию'), findsOneWidget);
    await tapText(tester, 'Начать кампанию');
    expect(server.paths, contains('/campaigns/rubezh/start'));
    expect(find.text('Три ампулы'), findsWidgets);
    await tapText(tester, 'К вердикту');
    final option =
        (jsonDecode(fixture('campaign_start'))['campaign']['chapter']['case']['decisions'] as List).first['text']
            as String;
    await tapText(tester, option);
    expect(find.text('ВЕРДИКТ'), findsOneWidget); // the stamp on the chosen option
    await tapText(tester, 'Вынести вердикт');
    final chose = server.requests.lastWhere((r) => r.url.path.endsWith('/choose'));
    expect(jsonDecode(chose.body), {'option': 'A'});
    expect(find.text('Последствия решения'), findsOneWidget);
    await scrollTo(tester, 'Глава 2');
    await tapText(tester, 'Глава 2');
    expect(find.text('ЧТО БЫЛО ДАЛЬШЕ'), findsOneWidget); // a kicker: upper case
    await tapText(tester, 'К новому делу');
    expect(find.text('К вердикту'), findsOneWidget);
  });

  testWidgets("ratings: a judge's profile, past seasons", (tester) async {
    final server = await start(tester);
    await tester.tap(find.text('Рейтинг').last);
    await settle(tester);
    final first = (jsonDecode(fixture('ratings'))['rows'] as List).first;
    await tapText(tester, first['display_name'] as String);
    expect(server.paths, contains('/users/${first['login']}'));
    expect(find.text('Войдите, чтобы добавить судью в друзья.'), findsOneWidget);
    await tester.pageBack();
    await settle(tester);
    await tester.dragUntilVisible(find.text('Прошлые сезоны'), find.byType(ListView).first, const Offset(-200, 0));
    await tapText(tester, 'Прошлые сезоны');
    expect(find.textContaining('Идёт сезон'), findsOneWidget);
  });

  testWidgets('the judge screen lists gifts and the title being worn', (tester) async {
    await start(tester);
    await tester.tap(find.text('Судья').last);
    await settle(tester);
    await scrollTo(tester, 'Подарки и трофеи');
    expect(find.textContaining('Вы носите: Чемпион сезона'), findsOneWidget);
  });

  testWidgets('a spot on the home screen: found, the gift, gone; the hunts and their hints on «Судья»', (tester) async {
    final server = await start(tester);
    final spot = find.byKey(const ValueKey('spot-6'));
    expect(spot, findsOneWidget);
    expect(find.byKey(const ValueKey('spot-7')), findsNothing); // it is in the archive
    expect(find.text('Найдено 0 из 5 · подсказки в «Судье»'), findsOneWidget);
    await tester.tap(spot);
    await settle(tester);
    expect(server.paths, contains('/hunt/spots/6/claim'));
    expect(find.text('Тайник найден!'), findsOneWidget);
    expect(find.text('Зоркий глаз'), findsOneWidget);
    expect(find.text('Найдено 1 из 2'), findsOneWidget);
    await tapText(tester, 'Забрать');
    await settle(tester, 20);
    expect(find.byKey(const ValueKey('spot-6')), findsNothing);

    await tester.tap(find.text('Архив').last);
    await settle(tester);
    expect(find.byKey(const ValueKey('spot-7')), findsOneWidget);
    await tester.tap(find.text('Судья').last);
    await settle(tester);
    await scrollTo(tester, 'Охота за тайниками');
    await scrollTo(tester, 'Тайники в приложении');
    final hint = find.textContaining('Среди папок с делами · Приложение · Архив', findRichText: true);
    await tester.scrollUntilVisible(hint, 250, scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('на сайте: Главная', findRichText: true), findsWidgets); // a spot of the website
  });

  testWidgets('communities: the list, a page with its rules and rating, joining', (tester) async {
    final server = await start(tester, signedIn: true);
    await tester.tap(find.text('Рейтинг').last);
    await settle(tester);
    await tapText(tester, 'Сообщества');
    expect(find.text('Клуб строгих судей'), findsOneWidget);
    await tapText(tester, 'Клуб строгих судей');
    expect(find.text('Правила'), findsOneWidget);
    await tapText(tester, 'Вступить');
    expect(find.text('Правила сообщества'), findsOneWidget);
    await tester.tap(find.text('Принимаю правила'));
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, 'Вступить'));
    await settle(tester);
    final join = server.requests.lastWhere((r) => r.url.path.endsWith('/join'));
    expect(jsonDecode(join.body), {'accept_rules': true});
    expect(find.text('Вы в сообществе «Клуб строгих судей».'), findsOneWidget);
    expect(find.text('Вы в сообществе · участник'), findsOneWidget);
    await scrollTo(tester, 'Участники');
  });

  testWidgets('the account: who sees the profile, Telegram, a notification opens what it is about', (tester) async {
    final server = await start(tester, signedIn: true, telegram: true);
    await tester.tap(find.text('Аккаунт').last);
    await settle(tester);
    expect(find.text('Анна Ветрова'), findsWidgets);
    expect(find.text('Подключить'), findsOneWidget); // the bot is connected on the server
    await tapText(tester, 'Профиль');
    await tapText(tester, 'Мне');
    await tapText(tester, 'Сохранить');
    final saved = server.requests.lastWhere((r) => r.url.path.endsWith('/me/profile'));
    expect(jsonDecode(saved.body), {'bio': '', 'visibility': 'private', 'in_ratings': true});
    expect(find.text('Профиль сохранён.'), findsOneWidget);
    await scrollTo(tester, 'Вас приняли в сообщество «Клуб строгих судей».');
    await tapText(tester, 'Вас приняли в сообщество «Клуб строгих судей».');
    expect(server.paths, contains('/communities/klub-strogikh-sudey'));
    expect(find.text('Сообщество'), findsOneWidget);
  });

  testWidgets('a report on a judge goes to the team', (tester) async {
    final server = await start(tester, signedIn: true);
    await tester.tap(find.text('Рейтинг').last);
    await settle(tester);
    final first = (jsonDecode(fixture('ratings'))['rows'] as List).first;
    await tapText(tester, first['display_name'] as String);
    await tester.tap(find.byType(PopupMenuButton<String>));
    await settle(tester);
    await tapText(tester, 'Пожаловаться');
    expect(find.text('Отправить команде'), findsOneWidget);
    await tapText(tester, 'Спам или реклама');
    await tapText(tester, 'Отправить команде');
    final sent = server.requests.lastWhere((r) => r.url.path.endsWith('/reports'));
    expect(jsonDecode(sent.body), {'target': 'user', 'login': first['login'], 'reason': 'spam', 'text': ''});
    expect(find.text('Спасибо! Команда посмотрит жалобу.'), findsOneWidget);
  });

  test('links of the site open the app\'s own screens', () {
    expect(appRoute('/u/anna'), isA<ProfileScreen>());
    expect(appRoute('/c/klub#members'), isA<CommunityScreen>());
    expect(appRoute('/talk/17'), isA<TalkScreen>());
    expect(appRoute('/friends'), isNull);
    expect(appTab('/friends'), 4);
    expect(appTab('/judge#gifts'), 2);
    expect(appTab('/'), 0);
    expect(appTab('/u/anna'), isNull);
    expect(appRoute('/seasons/2026-10'), isA<Scaffold>());
    expect(appRoute('/case/x'), isNull);
    final line = shareLine(
      {'id': 17, 'title': 'Шёпот'},
      {'key': 'B', 'text': 'Промолчать', 'share': .345},
      Uri.parse('https://v.uz/case/17'),
    );
    expect(
      line,
      'Дело «Шёпот»: мой вердикт — B, «Промолчать». Так решили 35% судей. А как решите вы? https://v.uz/case/17',
    );
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
