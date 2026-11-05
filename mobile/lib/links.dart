// Links: the website's pages open in the browser, the site's own links (in notifications) open inside the app when
// the app has that screen, and results go out through the phone's share sheet.
import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import 'main.dart';
import 'screens/case_screen.dart';
import 'screens/communities.dart';
import 'screens/profile.dart';
import 'screens/ratings.dart';
import 'screens/talk.dart';

/// «/create» → «https://verdict.azero.uz/create» (the server the app plays on).
Uri siteUri(BuildContext context, String path) {
  final base = SessionScope.read(context).server;
  return Uri.parse((base.endsWith('/') ? base.substring(0, base.length - 1) : base) + path);
}

void snack(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));

Future<void> openExternal(BuildContext context, Uri uri) async {
  var ok = false;
  try {
    ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
  } catch (_) {
    ok = false;
  }
  if (!ok && context.mounted) snack(context, 'Не удалось открыть $uri');
}

Future<void> openSite(BuildContext context, String path) => openExternal(context, siteUri(context, path));

/// Pages of the site that are tabs of the app: «/judge#gifts» → «Судья».
const siteTabs = {'': 0, 'play': 1, 'judge': 2, 'ratings': 3, 'friends': 4, 'notifications': 4, 'account': 4};

/// The tab of the app for a link of the site, or null.
int? appTab(String link) {
  final seg = (Uri.tryParse(link)?.pathSegments ?? const <String>[]).where((x) => x.isNotEmpty).toList();
  return seg.length <= 1 ? siteTabs[seg.isEmpty ? '' : seg.first] : null;
}

/// The route inside the app for a link of the site, or null when the app has no such screen.
Widget? appRoute(String link) {
  final uri = Uri.tryParse(link);
  if (uri == null) return null;
  final seg = uri.pathSegments.where((x) => x.isNotEmpty).toList();
  if (seg.isNotEmpty && seg.first == 'seasons') {
    return Scaffold(
      appBar: AppBar(title: const Text('Сезоны')),
      body: const SeasonsView(),
    );
  }
  if (seg.length != 2) return null;
  final id = int.tryParse(seg[1]);
  return switch (seg[0]) {
    'u' => ProfileScreen(login: seg[1]),
    'c' => CommunityScreen(slug: seg[1]),
    'talk' when id != null => TalkScreen(caseId: id, title: 'дело'),
    'case' when id != null => CaseScreen(caseId: id),
    'quick' when id != null => CaseScreen(caseId: id, quick: true),
    _ => null,
  };
}

/// A link of the site's own («/u/anna», «/c/klub#members», «/talk/17»): in the app when it can, else in the browser.
Future<void> openLink(BuildContext context, String link) async {
  final uri = Uri.tryParse(link);
  if (uri == null || link.isEmpty) return;
  final own = !uri.hasScheme || uri.host == Uri.tryParse(SessionScope.read(context).server)?.host;
  final tab = own ? appTab(uri.path) : null;
  if (tab != null) return Shell.goTo(context, tab);
  final route = own ? appRoute(link) : null;
  if (route != null) {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => route));
  } else if (own) {
    await openSite(context, uri.hasScheme ? uri.path : link);
  } else {
    await openExternal(context, uri);
  }
}

Future<void> shareText(BuildContext context, String text, {String? subject}) async {
  final box = context.findRenderObject() as RenderBox?;
  await SharePlus.instance.share(
    ShareParams(
      text: text,
      subject: subject,
      sharePositionOrigin: box == null ? null : box.localToGlobal(Offset.zero) & box.size,
    ),
  );
}
