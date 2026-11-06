// For screenshots and design review: opens one real screen with real data from a server, chosen by ?screen=.
//   flutter build web -t tool/showcase.dart --dart-define=VERDICT_API=http://127.0.0.1:8099
//   …/index.html?screen=home | archive | judge | ratings | account | case | verdict | result | talk | talk-open
//                       | campaign | chapter2 | step | ending | profile | seasons | friends
//                       | found | hunts | communities | community | report | intro | delete | tablet
import 'package:flutter/material.dart';
import 'package:verdict_mobile/hunt.dart';
import 'package:verdict_mobile/intro.dart';
import 'package:verdict_mobile/main.dart';
import 'package:verdict_mobile/report.dart';
import 'package:verdict_mobile/screens/account.dart';
import 'package:verdict_mobile/screens/campaigns.dart';
import 'package:verdict_mobile/screens/communities.dart';
import 'package:verdict_mobile/screens/case_screen.dart';
import 'package:verdict_mobile/screens/profile.dart';
import 'package:verdict_mobile/screens/ratings.dart';
import 'package:verdict_mobile/screens/result_screen.dart';
import 'package:verdict_mobile/screens/talk.dart';
import 'package:verdict_mobile/session.dart';
import 'package:verdict_mobile/theme.dart';
import 'package:verdict_mobile/widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final session = await Session.load();
  final screen = Uri.base.queryParameters['screen'] ?? 'home';
  runApp(
    SessionScope(
      session: session,
      child: MaterialApp(debugShowCheckedModeBanner: false, theme: V.theme(), home: _Show(screen)),
    ),
  );
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
    if (screen == 'campaign') return const CampaignScreen(campaignKey: 'rubezh');
    if (screen == 'profile') return const ProfileScreen(login: 'player1');
    if (screen == 'seasons') return const Scaffold(body: SafeArea(child: SeasonsView()));
    if (screen == 'friends') {
      await s.signIn('player1', 'password123');
      return const Shell(initialTab: 4);
    }
    if (screen == 'intro') return const Intro();
    if (screen == 'delete') {
      await s.signIn('player2', 'password123');
      return _After(
        const Shell(initialTab: 4),
        (c) => showDialog<bool>(
          context: c,
          builder: (_) => DeleteAccountDialog(session: s),
        ),
      );
    }
    if (screen == 'tablet') return const PhoneColumn(child: Shell());
    if (screen == 'hunts') {
      await s.refreshHunt();
      return Scaffold(
        appBar: AppBar(title: const Text('Судья')),
        body: ListView(padding: const EdgeInsets.all(16), children: const [HuntPanel()]),
      );
    }
    if (screen == 'found') {
      await s.refreshHunt();
      final spot = s.spots.firstWhere((x) => x['scene'] == 'home');
      final out = await s.claimSpot(spot['id'] as int);
      return _After(const Shell(), (c) => showFound(c, out));
    }
    if (const ['communities', 'community', 'report'].contains(screen)) {
      await s.signIn('player1', 'password123');
      if (screen == 'communities') return const CommunitiesScreen();
      if (screen == 'community') return const CommunityScreen(slug: 'klub-strogikh-sudey');
      return _After(
        const ProfileScreen(login: 'player2'),
        (c) => report(c, target: 'user', login: 'player2', what: 'Судья @player2'),
      );
    }
    if (const ['chapter2', 'step', 'ending'].contains(screen)) {
      await s.api.post('/campaigns/rubezh/start');
      var out = await s.api.post('/campaigns/rubezh/choose', {'option': 'A'});
      if (screen == 'chapter2') return ChapterScreen(campaign: out['campaign'] as Map<String, dynamic>);
      if (screen == 'ending') {
        await s.api.post('/campaigns/rubezh/choose', {'option': 'B'});
        out = await s.api.post('/campaigns/rubezh/choose', {'option': 'A'});
      }
      return StepScreen(step: out);
    }
    if (screen == 'talk-open') {
      // the seeded discussion under case 3, after one's own verdict
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

/// Shows [child] and then does [then] (opens a dialog or a sheet over it).
class _After extends StatefulWidget {
  const _After(this.child, this.then);

  final Widget child;
  final void Function(BuildContext context) then;

  @override
  State<_After> createState() => _AfterState();
}

class _AfterState extends State<_After> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Future.delayed(const Duration(milliseconds: 1500), () {
        if (mounted) widget.then(context);
      });
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
