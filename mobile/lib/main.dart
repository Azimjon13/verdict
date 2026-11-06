// VERDICT — the mobile app. The same game, cases and account as the website, through its API (/api/v1).
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'hunt.dart';
import 'intro.dart';
import 'links.dart';
import 'screens/account.dart';
import 'screens/archive.dart';
import 'screens/home.dart';
import 'screens/judge.dart';
import 'screens/ratings.dart';
import 'session.dart';
import 'theme.dart';
import 'widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  for (final font in ['Manrope', 'Unbounded']) {
    LicenseRegistry.addLicense(() async* {
      yield LicenseEntryWithLineBreaks([font], await rootBundle.loadString('assets/fonts/OFL-$font.txt'));
    });
  }
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(statusBarColor: Colors.transparent, systemNavigationBarColor: Color(0xFF060818)),
  );
  runApp(VerdictApp(session: await Session.load()));
}

class VerdictApp extends StatelessWidget {
  const VerdictApp({super.key, required this.session});

  final Session session;

  @override
  Widget build(BuildContext context) => SessionScope(
    session: session,
    child: MaterialApp(
      title: 'VERDICT',
      debugShowCheckedModeBanner: false,
      theme: V.theme(),
      locale: const Locale('ru'),
      builder: (context, child) => PhoneColumn(child: child ?? const SizedBox.shrink()),
      // The app opens on Boot; a link the phone opened the app with (verdict.azero.uz/case/17 …) waits for it.
      onGenerateInitialRoutes: (name) => [
        MaterialPageRoute(builder: (_) => Boot(link: name == Navigator.defaultRouteName ? null : name)),
      ],
      // A link opened with the app while it runs.
      onGenerateRoute: (settings) => linkRoute(settings.name ?? Navigator.defaultRouteName),
    ),
  );
}

/// On a tablet or a wide window the game keeps a phone's column, centred: the layout it was made for, easier to read.
class PhoneColumn extends StatelessWidget {
  const PhoneColumn({super.key, required this.child});

  final Widget child;
  static const width = 600.0;

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    if (mq.size.width <= width + 120) return child;
    return ColoredBox(
      color: V.bg,
      child: Center(
        child: SizedBox(
          width: width,
          child: MediaQuery(
            data: mq.copyWith(size: Size(width, mq.size.height)),
            child: child,
          ),
        ),
      ),
    );
  }
}

/// Gives every screen the session (and rebuilds them when it changes: sign-in, unread count, catalog).
class SessionScope extends InheritedNotifier<Session> {
  const SessionScope({super.key, required Session session, required super.child}) : super(notifier: session);

  static Session of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<SessionScope>()!.notifier!;
  static Session read(BuildContext context) => context.getInheritedWidgetOfExactType<SessionScope>()!.notifier!;
}

/// First the game's dictionaries, then the app.
class Boot extends StatefulWidget {
  const Boot({super.key, this.link});

  /// A link of the site the app was opened with: shown once the app is ready.
  final String? link;

  @override
  State<Boot> createState() => _BootState();
}

class _BootState extends State<Boot> {
  Object? _error;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    final s = SessionScope.read(context);
    setState(() => _error = null);
    try {
      await s.loadCatalog();
      s.refreshMe();
      s.refreshHunt();
      if (mounted) setState(() => _ready = true);
      final link = widget.link;
      if (link != null) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) openLink(context, link);
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_ready) return SessionScope.of(context).showIntro ? const Intro() : const Shell();
    return Scaffold(
      body: _error != null
          ? ErrorView(_error!, onRetry: _start)
          : Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('VERDICT', style: V.display(30, weight: FontWeight.w900)),
                  const SizedBox(height: 10),
                  Text(
                    'Нет правильного ответа.\nЕсть только твой вердикт.',
                    textAlign: TextAlign.center,
                    style: V.body(14, color: V.muted),
                  ),
                  const SizedBox(height: 26),
                  const SizedBox(
                    width: 26,
                    height: 26,
                    child: CircularProgressIndicator(strokeWidth: 2.5, color: V.cyan),
                  ),
                ],
              ),
            ),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key, this.initialTab = 0});

  final int initialTab;

  static _ShellState? _current;

  /// Back to the tabs and onto [tab] (0 Играть … 4 Аккаунт) — from anywhere in the app.
  static void goTo(BuildContext context, int tab) {
    Navigator.of(context).popUntil((r) => r.isFirst);
    _current?.go(tab);
  }

  @override
  State<Shell> createState() => _ShellState();
}

/// The tabs as scenes of a treasure hunt (admin → «Приложение или Unity» → the scene).
const scenes = ['home', 'archive', 'judge', 'ratings', 'account'];

class _ShellState extends State<Shell> with WidgetsBindingObserver {
  late int _tab = widget.initialTab;
  final _keys = List.generate(5, (_) => GlobalKey());

  @override
  void initState() {
    super.initState();
    Shell._current = this;
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    if (Shell._current == this) Shell._current = null;
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      final s = SessionScope.read(context);
      s.refreshMe();
      s.refreshHunt();
    }
  }

  void go(int tab) => setState(() => _tab = tab);

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final pages = [
      HomeScreen(key: _keys[0], onTab: go),
      ArchiveScreen(key: _keys[1]),
      JudgeScreen(key: _keys[2]),
      RatingsScreen(key: _keys[3]),
      AccountScreen(key: _keys[4]),
    ];
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: IndexedStack(
          index: _tab,
          children: [for (var i = 0; i < pages.length; i++) HuntLayer(scene: scenes[i], child: pages[i])],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: go,
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.gavel_outlined),
            selectedIcon: Icon(Icons.gavel),
            label: 'Играть',
          ),
          const NavigationDestination(
            icon: Icon(Icons.inventory_2_outlined),
            selectedIcon: Icon(Icons.inventory_2),
            label: 'Архив',
          ),
          const NavigationDestination(
            icon: Icon(Icons.balance_outlined),
            selectedIcon: Icon(Icons.balance),
            label: 'Судья',
          ),
          const NavigationDestination(
            icon: Icon(Icons.emoji_events_outlined),
            selectedIcon: Icon(Icons.emoji_events),
            label: 'Рейтинг',
          ),
          NavigationDestination(
            icon: Badge(
              isLabelVisible: s.unread > 0,
              label: Text('${s.unread}'),
              backgroundColor: V.magenta,
              child: Icon(s.signedIn ? Icons.person_outline : Icons.login),
            ),
            selectedIcon: Badge(
              isLabelVisible: s.unread > 0,
              label: Text('${s.unread}'),
              backgroundColor: V.magenta,
              child: Icon(s.signedIn ? Icons.person : Icons.login),
            ),
            label: s.signedIn ? 'Аккаунт' : 'Войти',
          ),
        ],
      ),
    );
  }
}
