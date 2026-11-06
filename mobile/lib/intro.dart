// The first launch on a new phone: three cards on what the game is, then the game. Skippable; shown once.
import 'package:flutter/material.dart';

import 'main.dart';
import 'theme.dart';
import 'widgets.dart';

class Intro extends StatefulWidget {
  const Intro({super.key});

  @override
  State<Intro> createState() => _IntroState();
}

class _IntroState extends State<Intro> {
  final _pages = PageController();
  int _at = 0;

  static const _cards = [
    (
      Icons.gavel,
      'Вы — судья',
      'Каждое дело — история без правильного ответа: закон против совести, долг против милосердия. '
          'Прочтите, взвесьте и вынесите вердикт.',
    ),
    (
      Icons.public,
      'Решения меняют ваш мир',
      'Вердикты двигают доверие, стабильность и репутацию вашего мира, приносят опыт, ранги и достижения. '
          'Дело дня — раз в сутки, с бонусом.',
    ),
    (
      Icons.track_changes,
      'Угадайте большинство',
      'В Быстром суде после вердикта угадайте, как решило большинство. Потом — как разделились все судьи, '
          'обсуждение и рейтинг сезона.',
    ),
  ];

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  void _done() => SessionScope.read(context).introDone();

  @override
  Widget build(BuildContext context) {
    final last = _at == _cards.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(onPressed: _done, child: const Text('Пропустить')),
            ),
            Expanded(
              child: PageView(
                controller: _pages,
                onPageChanged: (i) => setState(() => _at = i),
                children: [
                  for (final c in _cards)
                    SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
                      child: Column(
                        children: [
                          const SizedBox(height: 24),
                          Container(
                            width: 116,
                            height: 116,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: V.grad,
                              boxShadow: [BoxShadow(color: V.violet.withValues(alpha: .45), blurRadius: 40)],
                            ),
                            child: Icon(c.$1, size: 54, color: Colors.white),
                          ),
                          const SizedBox(height: 34),
                          Text(
                            c.$2,
                            textAlign: TextAlign.center,
                            style: V.display(24, weight: FontWeight.w900),
                          ),
                          const SizedBox(height: 14),
                          Text(
                            c.$3,
                            textAlign: TextAlign.center,
                            style: V.body(16, color: V.muted),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < _cards.length; i++)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    width: i == _at ? 22 : 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: i == _at ? V.cyan : V.line,
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
              child: SizedBox(
                width: double.infinity,
                child: GradientButton(
                  last ? 'Начать' : 'Дальше',
                  icon: last ? Icons.play_arrow : Icons.arrow_forward,
                  onPressed: last
                      ? _done
                      : () => _pages.nextPage(duration: const Duration(milliseconds: 280), curve: Curves.easeOut),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
