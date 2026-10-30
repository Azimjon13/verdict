// «Рейтинг»: the season (a calendar month), all time, the instinct for the majority, the streak.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';

class RatingsScreen extends StatefulWidget {
  const RatingsScreen({super.key});

  @override
  State<RatingsScreen> createState() => _RatingsScreenState();
}

class _RatingsScreenState extends State<RatingsScreen> {
  String _board = 'season';

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final boards = ((s.catalog['social'] as Json?)?['boards'] as Json?) ?? {'season': {'name': 'Сезон', 'unit': 'XP'}};
    final b = boards[_board] as Json;
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Рейтинг судей', style: V.display(24, weight: FontWeight.w900)),
          const SizedBox(height: 12),
          SizedBox(
            height: 38,
            child: ListView(scrollDirection: Axis.horizontal, children: [
              for (final e in boards.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    selected: _board == e.key,
                    onSelected: (_) => setState(() => _board = e.key),
                    showCheckmark: false,
                    label: Text((e.value as Json)['name'] as String),
                    labelStyle: V.body(13, weight: FontWeight.w700, color: _board == e.key ? V.bg : V.text),
                    selectedColor: V.cyan,
                    backgroundColor: const Color(0xFF0B0F27),
                    side: BorderSide(color: _board == e.key ? V.cyan : V.line),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 8),
          Text(b['desc'] as String? ?? '', style: V.body(12.5, color: V.dim)),
        ]),
      ),
      Expanded(
        child: Loader<Json>(
          key: ValueKey(_board),
          load: () => s.api.get('/ratings', query: {'board': _board}),
          builder: (context, data, reload) {
            final rows = (data['rows'] as List).cast<Json>();
            final me = s.user?['login'];
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
              children: [
                if (_board == 'season')
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Pill('Сезон «${capitalize(data['season'] as String)}»: осталось ${data['days_left']} ${plural(data['days_left'] as num, 'день', 'дня', 'дней')}',
                        icon: Icons.emoji_events, color: V.amber),
                  ),
                if (rows.isEmpty)
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text('Здесь пока пусто. Вынесите вердикт — и рейтинг откроется.',
                        textAlign: TextAlign.center, style: V.body(14, color: V.muted)),
                  ),
                for (final r in rows)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Panel(
                      accent: r['login'] == me ? V.cyan : (r['place'] == 1 ? V.amber : null),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      child: Row(children: [
                        SizedBox(
                          width: 34,
                          child: (r['place'] as int) <= 3
                              ? Icon(r['place'] == 1 ? Icons.workspace_premium : Icons.military_tech,
                                  color: r['place'] == 1 ? V.amber : V.muted)
                              : Text('${r['place']}', textAlign: TextAlign.center, style: V.display(14, color: V.muted)),
                        ),
                        const SizedBox(width: 6),
                        Avatar(r['display_name'] as String, size: 34),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(r['display_name'] as String, overflow: TextOverflow.ellipsis, style: V.body(14.5, weight: FontWeight.w800)),
                            Row(children: [
                              Icon(vIcon((r['rank'] as Json)['icon'] as String?), size: 13, color: V.muted),
                              const SizedBox(width: 4),
                              Flexible(
                                  child: Text((r['title'] as String?) ?? (r['rank'] as Json)['name'] as String,
                                      overflow: TextOverflow.ellipsis, style: V.body(12, color: V.muted))),
                            ]),
                          ]),
                        ),
                        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                          Text('${r['value']}', style: V.display(16, color: V.cyan)),
                          Text((r['note'] as String?)?.isNotEmpty == true ? r['note'] as String : b['unit'] as String? ?? '',
                              style: V.body(11, color: V.dim)),
                        ]),
                      ]),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    ]);
  }
}
