// VERDICT — the mobile app. The same game, cases and account as the website, through its API (/api/v1).
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent, systemNavigationBarColor: Color(0xFF060818)));
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
          home: const Boot(),
        ),
      );
}

/// Gives every screen the session (and rebuilds them when it changes: sign-in, unread count, catalog).
class SessionScope extends InheritedNotifier<Session> {
  const SessionScope({super.key, required Session session, required super.child}) : super(notifier: session);

  static Session of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<SessionScope>()!.notifier!;
  static Session read(BuildContext context) => context.getInheritedWidgetOfExactType<SessionScope>()!.notifier!;
}

/// First the game's dictionaries, then the app.
class Boot extends StatefulWidget {
  const Boot({super.key});

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
      if (mounted) setState(() => _ready = true);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_ready) return const Shell();
    return Scaffold(
      body: _error != null
          ? ErrorView(_error!, onRetry: _start)
          : Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Text('VERDICT', style: V.display(30, weight: FontWeight.w900)),
                const SizedBox(height: 10),
                Text('Нет правильного ответа.\nЕсть только твой вердикт.', textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
                const SizedBox(height: 26),
                const SizedBox(width: 26, height: 26, child: CircularProgressIndicator(strokeWidth: 2.5, color: V.cyan)),
              ]),
            ),
    );
  }
}

class Shell extends StatefulWidget {
  const Shell({super.key, this.initialTab = 0});

  final int initialTab;

  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> with WidgetsBindingObserver {
  late int _tab = widget.initialTab;
  final _keys = List.generate(5, (_) => GlobalKey());

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) SessionScope.read(context).refreshMe();
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
      body: SafeArea(bottom: false, child: IndexedStack(index: _tab, children: pages)),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: go,
        destinations: [
          const NavigationDestination(icon: Icon(Icons.gavel_outlined), selectedIcon: Icon(Icons.gavel), label: 'Играть'),
          const NavigationDestination(icon: Icon(Icons.inventory_2_outlined), selectedIcon: Icon(Icons.inventory_2), label: 'Архив'),
          const NavigationDestination(icon: Icon(Icons.balance_outlined), selectedIcon: Icon(Icons.balance), label: 'Судья'),
          const NavigationDestination(icon: Icon(Icons.emoji_events_outlined), selectedIcon: Icon(Icons.emoji_events), label: 'Рейтинг'),
          NavigationDestination(
            icon: Badge(isLabelVisible: s.unread > 0, label: Text('${s.unread}'), backgroundColor: V.magenta,
                child: Icon(s.signedIn ? Icons.person_outline : Icons.login)),
            selectedIcon: Badge(isLabelVisible: s.unread > 0, label: Text('${s.unread}'), backgroundColor: V.magenta,
                child: Icon(s.signedIn ? Icons.person : Icons.login)),
            label: s.signedIn ? 'Аккаунт' : 'Войти',
          ),
        ],
      ),
    );
  }
}
