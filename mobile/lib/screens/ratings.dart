// «Рейтинг»: the season (a calendar month), all time, the instinct for the majority, the streak.
import 'package:flutter/material.dart';

import '../api.dart';
import '../icons.dart';
import '../main.dart';
import '../theme.dart';
import '../widgets.dart';
import 'profile.dart';

class RatingsScreen extends StatefulWidget {
  const RatingsScreen({super.key});

  @override
  State<RatingsScreen> createState() => _RatingsScreenState();
}

class _RatingsScreenState extends State<RatingsScreen> {
  String _board = 'season';
  bool _friends = false;

  @override
  Widget build(BuildContext context) {
    final s = SessionScope.of(context);
    final boards = {
      ...((s.catalog['social'] as Json?)?['boards'] as Json?) ??
          {
            'season': {'name': 'Сезон', 'unit': 'XP'},
          },
      'seasons': {'name': 'Прошлые сезоны'},
    };
    final b = boards[_board] as Json;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Рейтинг судей', style: V.display(24, weight: FontWeight.w900)),
              const SizedBox(height: 12),
              SizedBox(
                height: 38,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
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
                  ],
                ),
              ),
              const SizedBox(height: 8),
              if (_board != 'seasons') Text(b['desc'] as String? ?? '', style: V.body(12.5, color: V.dim)),
              if (s.signedIn && _board != 'seasons')
                SwitchListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  value: _friends,
                  onChanged: (v) => setState(() => _friends = v),
                  activeThumbColor: V.cyan,
                  title: Text('Только друзья', style: V.body(14, weight: FontWeight.w700)),
                ),
            ],
          ),
        ),
        if (_board == 'seasons')
          const Expanded(child: SeasonsView())
        else
          Expanded(
            child: Loader<Json>(
              key: ValueKey('$_board$_friends'),
              load: () =>
                  s.api.get('/ratings', query: {'board': _board, if (_friends && s.signedIn) 'scope': 'friends'}),
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
                        child: Pill(
                          'Сезон «${capitalize(data['season'] as String)}»: осталось ${data['days_left']} ${plural(data['days_left'] as num, 'день', 'дня', 'дней')}',
                          icon: Icons.emoji_events,
                          color: V.amber,
                        ),
                      ),
                    if (rows.isEmpty)
                      Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          'Здесь пока пусто. Вынесите вердикт — и рейтинг откроется.',
                          textAlign: TextAlign.center,
                          style: V.body(14, color: V.muted),
                        ),
                      ),
                    for (final r in rows)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Panel(
                          accent: r['login'] == me ? V.cyan : (r['place'] == 1 ? V.amber : null),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                          onTap: () => openProfile(context, r['login'] as String),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 34,
                                child: (r['place'] as int) <= 3
                                    ? Icon(
                                        r['place'] == 1 ? Icons.workspace_premium : Icons.military_tech,
                                        color: r['place'] == 1 ? V.amber : V.muted,
                                      )
                                    : Text(
                                        '${r['place']}',
                                        textAlign: TextAlign.center,
                                        style: V.display(14, color: V.muted),
                                      ),
                              ),
                              const SizedBox(width: 6),
                              Avatar(r['display_name'] as String, size: 34),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      r['display_name'] as String,
                                      overflow: TextOverflow.ellipsis,
                                      style: V.body(14.5, weight: FontWeight.w800),
                                    ),
                                    Row(
                                      children: [
                                        Icon(vIcon((r['rank'] as Json)['icon'] as String?), size: 13, color: V.muted),
                                        const SizedBox(width: 4),
                                        Flexible(
                                          child: Text(
                                            (r['title'] as String?) ?? (r['rank'] as Json)['name'] as String,
                                            overflow: TextOverflow.ellipsis,
                                            style: V.body(12, color: V.muted),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text('${r['value']}', style: V.display(16, color: V.cyan)),
                                  Text(
                                    (r['note'] as String?)?.isNotEmpty == true
                                        ? r['note'] as String
                                        : b['unit'] as String? ?? '',
                                    style: V.body(11, color: V.dim),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
      ],
    );
  }
}

/// The current season's trophies and the closed seasons with their podium.
class SeasonsView extends StatelessWidget {
  const SeasonsView({super.key});

  @override
  Widget build(BuildContext context) {
    final api = SessionScope.read(context).api;
    return Loader<Json>(
      load: () => api.get('/seasons'),
      builder: (context, data, reload) {
        final current = data['current'] as Json;
        final past = ((data['past'] as List?) ?? const []).cast<Json>();
        return ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
          children: [
            Panel(
              accent: V.amber,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.emoji_events, color: V.amber),
                      const SizedBox(width: 10),
                      Expanded(child: Text('Идёт сезон «${current['name']}»', style: V.display(16))),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'До конца ${current['days_left']} ${plural(current['days_left'] as num, 'день', 'дня', 'дней')}. Лучшие получат:',
                    style: V.body(13, color: V.muted),
                  ),
                  const SizedBox(height: 10),
                  for (final t in ((current['trophies'] as List?) ?? const []).cast<Json>())
                    Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Row(
                        children: [
                          Icon(vIcon(t['icon'] as String?), size: 18, color: V.amber),
                          const SizedBox(width: 8),
                          SizedBox(
                            width: 64,
                            child: Text(
                              t['from'] == t['to'] ? '${t['from']} место' : '${t['from']}–${t['to']}',
                              style: V.body(13, weight: FontWeight.w800),
                            ),
                          ),
                          Expanded(
                            child: Text('${t['name']} · +${t['xp']} XP', style: V.body(13, color: V.muted)),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            const SectionTitle('Прошлые сезоны', icon: Icons.archive),
            if (past.isEmpty) Text('Первый сезон ещё идёт.', style: V.body(14, color: V.muted)),
            for (final season in past)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Panel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(child: Text(season['name'] as String, style: V.display(16))),
                          Text(
                            '${season['players']} ${plural(season['players'] as num, 'судья', 'судьи', 'судей')}',
                            style: V.body(12, color: V.dim),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      for (final r in ((season['podium'] as List?) ?? const []).cast<Json>())
                        InkWell(
                          onTap: () => openProfile(context, r['login'] as String),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 5),
                            child: Row(
                              children: [
                                SizedBox(
                                  width: 26,
                                  child: Text(
                                    '${r['place']}',
                                    style: V.display(14, color: r['place'] == 1 ? V.amber : V.muted),
                                  ),
                                ),
                                Avatar(r['display_name'] as String, size: 28),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(r['display_name'] as String, style: V.body(14, weight: FontWeight.w700)),
                                ),
                                Text(
                                  '${r['value']} XP',
                                  style: V.body(13, weight: FontWeight.w800, color: V.cyan),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}
