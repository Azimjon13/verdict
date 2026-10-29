<?php
defined('APP_ROOT') || exit;

/**
 * «Быстрый суд»: экран после вердикта — угадал ли игрок большинство, как решили все, последствие.
 * @var array   $s        ситуация
 * @var string  $choice   ключ решения игрока
 * @var ?string $guess    ключ, который игрок приписал большинству (null — пропустил)
 * @var array   $majority ключи большинства среди других игроков до этого голоса ([] — никто ещё не голосовал)
 * @var ?int    $correct  1/0 — угадал ли; null — не угадывал или не с кем сравнить
 * @var array   $counts   [ключ => голоса] уже с голосом игрока
 * @var array   $stats    quick_stats()
 * @var ?array  $judge    профиль судьи для полоски под результатом (см. judge-teaser)
 */
$decision = situation_decision($s, $choice);
$total = array_sum($counts);
$text = static fn(string $key): string => situation_decision($s, $key)['text'] ?? 'Другое решение';
$majorityText = implode(' / ', array_map(static fn(string $k): string => '«' . $text($k) . '»', $majority));
$minePct = $total ? (int)round(($counts[$choice] ?? 0) / $total * 100) : 0;
$effects = array_filter($decision['effects'] ?? []);
$conseq = trim((string)($decision['immediate'] ?? '')) ?: trim((string)($decision['longterm'] ?? ''));

if ($correct === 1) {
    [$tone, $icon, $title, $sub] = ['win', 'check-circle', 'Вы угадали большинство!',
        'Большинство действительно выбрало ' . $majorityText . '.'];
} elseif ($correct === 0) {
    [$tone, $icon, $title, $sub] = ['miss', 'target', 'Не угадали', 'Большинство выбрало ' . $majorityText . '.'];
} elseif (!$majority) {
    [$tone, $icon, $title, $sub] = ['first', 'flag', 'Вы первый судья этого дела', 'Сравнивать пока не с кем — ваш вердикт станет точкой отсчёта для остальных.'];
} else {
    [$tone, $icon, $title, $sub] = ['skip', 'users', 'Вы не угадывали', 'Большинство выбрало ' . $majorityText . '.'];
}
?>
<section class="quick-result panel" id="quick-result" tabindex="-1" aria-live="polite">
    <div class="guess-banner guess-<?= $tone ?>">
        <span class="guess-icon"><?= icon($icon) ?></span>
        <div>
            <h2><?= e($title) ?></h2>
            <p><?= e($sub) ?></p>
        </div>
        <?php if ($correct === 1): ?><span class="guess-points">+1</span><?php endif; ?>
    </div>

    <div class="quick-choice">
        <span class="opt-letter"><?= e($choice === 'other' ? '+' : $choice) ?></span>
        <div>
            <span class="label-mono">Ваш вердикт</span>
            <b><?= e($text($choice)) ?></b>
            <?php if ($total > 1): ?>
                <small><?= $majority && in_array($choice, $majority, true) ? 'Вы решили как большинство.' : 'Так решили ' . $minePct . '% игроков.' ?></small>
            <?php endif; ?>
        </div>
    </div>

    <?php if ($conseq !== '' || $effects): ?>
        <div class="quick-block">
            <h3 class="result-h"><?= icon('zap') ?>Что было дальше</h3>
            <?php if ($conseq !== ''): ?><p class="quick-conseq"><?= e($conseq) ?></p><?php endif; ?>
            <?php if ($effects): ?>
                <div class="deltas">
                    <?php foreach (METRICS as $k => $m): if (empty($effects[$k])) continue; $v = (int)$effects[$k]; ?>
                        <span class="delta <?= $v > 0 ? 'up' : 'down' ?>"><?= icon($m['icon']) ?><?= e($m['name']) ?> <b><?= $v > 0 ? '+' . $v * METRIC_STEP : $v * METRIC_STEP ?></b></span>
                    <?php endforeach; ?>
                </div>
            <?php endif; ?>
        </div>
    <?php endif; ?>

    <div class="quick-block">
        <h3 class="result-h"><?= icon('chart') ?>Как решили все <span class="result-sub"><?= $total ?> <?= plural($total, 'вердикт', 'вердикта', 'вердиктов') ?></span></h3>
        <ul class="dist">
            <?php foreach ($s['decisions'] as $d): $n = $counts[$d['key']] ?? 0; $pct = $total ? (int)round($n / $total * 100) : 0; ?>
                <li class="dist-row<?= $d['key'] === $choice ? ' is-mine' : '' ?><?= in_array($d['key'], $majority, true) ? ' is-majority' : '' ?>">
                    <span class="opt-letter opt-letter-sm"><?= e($d['key']) ?></span>
                    <div class="dist-body">
                        <div class="dist-top">
                            <span class="dist-text"><?= e($d['text']) ?><?= $d['key'] === $choice ? ' <em>ваш выбор</em>' : '' ?><?= $d['key'] === $guess ? ' <em class="em-guess">ваша догадка</em>' : '' ?></span>
                            <b><?= $pct ?>%</b>
                        </div>
                        <div class="dist-bar"><i style="--w: <?= $pct ?>%"></i></div>
                    </div>
                </li>
            <?php endforeach; ?>
        </ul>
    </div>

    <?php if ($s['ambiguity']['conflict'] !== ''): ?>
        <p class="quick-conflict"><?= icon('swords') ?><span><b>Почему нет правильного ответа:</b> <?= e($s['ambiguity']['conflict']) ?></span></p>
    <?php endif; ?>

    <?php if (!empty($judge)): ?><?= partial('judge-teaser', ['judge' => $judge]) ?><?php endif; ?>

    <div class="quick-foot">
        <span class="quick-score" title="Сколько раз вы угадали выбор большинства">
            <?= icon('target') ?>Угадано: <b data-quick-score><?= $stats['score'] ?></b> из <?= $stats['guesses'] ?>
            <?php if ($stats['streak'] > 1): ?><span class="streak"><?= icon('flame') ?>серия <?= $stats['streak'] ?></span><?php endif; ?>
        </span>
        <div class="quick-actions">
            <a class="btn" href="case.php?id=<?= $s['id'] ?>"><?= icon('file') ?>Полное досье</a>
            <a class="btn btn-primary" href="quick.php" data-quick-next>Следующее дело<?= icon('arrow-right') ?></a>
        </div>
    </div>
</section>
