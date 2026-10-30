// For screenshots and design review: opens one real screen with real data from a server, chosen by ?screen=.
//   flutter build web -t tool/showcase.dart --dart-define=VERDICT_API=http://127.0.0.1:8099
//   …/index.html?screen=home | archive | judge | ratings | account | case | verdict | result | talk | talk-open
import 'package:flutter/material.dart';
import 'package:verdict_mobile/main.dart';
import 'package:verdict_mobile/screens/case_screen.dart';
import 'package:verdict_mobile/screens/result_screen.dart';
import 'package:verdict_mobile/screens/talk.dart';
import 'package:verdict_mobile/session.dart';
import 'package:verdict_mobile/theme.dart';
import 'package:verdict_mobile/widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final session = await Session.load();
  final screen = Uri.base.queryParameters['screen'] ?? 'home';
  runApp(SessionScope(
    session: session,
    child: MaterialApp(debugShowCheckedModeBanner: false, theme: V.theme(), home: _Show(screen)),
  ));
}

class _Show extends StatelessWidget {
  const _Show(this.screen);

  final String screen;

  Future<Widget> _build(BuildContext context) async {
    final s = SessionScope.read(context);
    await s.loadCatalog();
    const tabs = {'home': 0, 'archive': 1, 'judge': 2, 'ratings': 3, 'account': 4};
    if (tabs.containsKey(screen)) return Shell(initialTab: tabs[screen]!);
    if (screen == 'case') return const QuickRun();
    if (screen == 'verdict') return const QuickRun(atVerdict: true);
    if (screen == 'talk-open') {  // the seeded discussion under case 3, after one's own verdict
      await s.api.post('/cases/3/verdict', {'option': 'A'});
      return const TalkScreen(caseId: 3, title: 'Перевал Кызыл-Тау');
    }
    final next = await s.api.get('/quick/next');
    final c = next['case'] as Map<String, dynamic>;
    if (screen == 'talk') return TalkScreen(caseId: c['id'] as int, title: c['title'] as String);
    final out = await s.api.post('/cases/${c['id']}/verdict', {'option': 'A', 'guess': 'A', 'mode': 'quick'});
    return ResultScreen(result: out, caseData: c, quick: true);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Widget>(
        future: _build(context),
        builder: (context, snap) => snap.hasError
            ? Scaffold(body: ErrorView(snap.error!, onRetry: () {}))
            : (snap.data ?? const Scaffold(body: Loading())),
      );
}
