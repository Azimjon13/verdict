// «Архив»: every case in play, by category; opening one gives the full verdict (with one's own decision).
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'case_screen.dart';

class ArchiveScreen extends StatefulWidget {
  const ArchiveScreen({super.key});

  @override
  State<ArchiveScreen> createState() => _ArchiveScreenState();
}

class _ArchiveScreenState extends State<ArchiveScreen> {
  String? _category;
  bool _unjudged = false;
  Key _loader = UniqueKey();

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final categories = (s.catalog['categories'] as Json? ?? {});
    return Loader<Json>(
      key: _loader,
      load: () => s.api.get('/cases'),
      builder: (context, data, reload) {
        var cases = (data['cases'] as List).cast<Json>();
        if (_category != null) cases = cases.where((c) => c['category'] == _category).toList();
        if (_unjudged) cases = cases.where((c) => c['my_verdict'] == null).toList();
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: [
            Text('Архив дел', style: V.display(24, weight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('${data['count']} ${plural(data['count'] as num, 'дело', 'дела', 'дел')} в игре', style: V.body(13.5, color: V.muted)),
            const SizedBox(height: 14),
            SizedBox(
              height: 38,
              child: ListView(scrollDirection: Axis.horizontal, children: [
                _chip('Все', _category == null, () => setState(() => _category = null)),
                for (final e in categories.entries)
                  _chip((e.value as Json)['name'] as String, _category == e.key, () => setState(() => _category = e.key),
                      color: V.hue((e.value as Json)['hue'] as num? ?? 190), icon: vIcon((e.value as Json)['icon'] as String?)),
              ]),
            ),
            const SizedBox(height: 6),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: _unjudged,
              onChanged: (v) => setState(() => _unjudged = v),
              activeThumbColor: V.cyan,
              title: Text('Только нерассуженные', style: V.body(14, weight: FontWeight.w700)),
            ),
            for (final c in cases) _card(context, c),
            if (cases.isEmpty)
              Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Таких дел нет.', textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
              ),
          ],
        );
      },
    );
  }

  Widget _chip(String label, bool on, VoidCallback onTap, {Color color = V.cyan, IconData? icon}) => Padding(
        padding: const EdgeInsets.only(right: 8),
        child: ChoiceChip(
          selected: on,
          onSelected: (_) => onTap(),
          avatar: icon == null ? null : Icon(icon, size: 16, color: on ? V.bg : color),
          label: Text(label),
          showCheckmark: false,
          labelStyle: V.body(13, weight: FontWeight.w700, color: on ? V.bg : V.text),
          selectedColor: color,
          backgroundColor: const Color(0xFF0B0F27),
          side: BorderSide(color: on ? color : V.line),
        ),
      );

  Widget _card(BuildContext context, Json c) {
    final s = SessionScope.of(context);
    final cat = s.category(c['category'] as String?);
    final accent = V.hue(cat['hue'] as num? ?? 190);
    final my = c['my_verdict'];
    final controversy = c['controversy'] as num?;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        onTap: () async {
          await Navigator.of(context).push(MaterialPageRoute(builder: (_) => CaseScreen(caseId: c['id'] as int)));
          setState(() => _loader = UniqueKey());
        },
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(vIcon(cat['icon'] as String?), size: 16, color: accent),
            const SizedBox(width: 6),
            Expanded(child: Text((cat['name'] as String).toUpperCase(), style: V.mono(10.5, color: accent))),
            if (my != null) Pill('Ваш вердикт: ${my == 'other' ? '+' : my}', color: V.cyan, filled: true),
          ]),
          const SizedBox(height: 8),
          Text(c['title'] as String, style: V.display(17)),
          const SizedBox(height: 6),
          Text(c['teaser'] as String? ?? '', maxLines: 3, overflow: TextOverflow.ellipsis, style: V.body(13.5, color: V.muted)),
          const SizedBox(height: 10),
          Row(children: [
            const Icon(Icons.gavel, size: 14, color: V.dim),
            const SizedBox(width: 4),
            Text('${c['votes']}', style: V.body(12.5, color: V.dim)),
            const SizedBox(width: 14),
            const Icon(Icons.place, size: 14, color: V.dim),
            const SizedBox(width: 4),
            Expanded(child: Text(c['setting'] as String? ?? '', overflow: TextOverflow.ellipsis, style: V.body(12.5, color: V.dim))),
            if (controversy != null && controversy >= 60) const Pill('спорное', icon: Icons.local_fire_department, color: V.magenta),
          ]),
        ]),
      ),
    );
  }
}
