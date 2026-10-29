<?php
defined('APP_ROOT') || exit;

/**
 * Экран результата после вердикта.
 * @var array  $s         ситуация
 * @var string $choice    ключ решения (A..H или other)
 * @var string $reasoning обоснование игрока
 * @var array  $counts    [ключ => голоса]
 * @var bool   $preview   дело не одобрено — голос не учитывается
 * @var ?array $next      следующее дело
 * @var bool   $fresh     только что вынесен (для анимаций)
 * @var ?array $judge     профиль судьи для полоски под результатом (см. judge-teaser)
 */
$decision = $choice === 'other' ? null : situation_decision($s, $choice);
$total = array_sum($counts);
$contro = controversy($counts, max(2, count($s['decisions'])));
$effects = array_filter($decision['effects'] ?? []);
$amb = $s['ambiguity'];

$rows = [];
foreach ($s['decisions'] as $d) {
    $rows[] = ['key' => $d['key'], 'text' => $d['text'], 'n' => $counts[$d['key']] ?? 0];
}
if (($counts['other'] ?? 0) > 0 || $choice === 'other') {
    $rows[] = ['key' => 'other', 'text' => 'Другое решение', 'n' => $counts['other'] ?? 0];
}

$shareText = 'Дело «' . $s['title'] . '». Мой вердикт: ' . ($decision['text'] ?? 'своё решение') . '. А что решили бы вы?';
$conseqTiles = [
    'immediate'  => ['Немедленно', 'zap'],
    'longterm'   => ['В долгосрочной перспективе', 'clock'],
    'characters' => ['Персонажи', 'users'],
    'world'      => ['Общество и мир', 'globe'],
];
?>
<section class="result panel<?= $fresh ? ' is-fresh' : '' ?>" id="result" tabindex="-1" aria-live="polite">
    <div class="result-stamp" aria-hidden="true"><span>Вердикт</span><span>вынесен</span></div>

    <?php if ($preview): ?>
        <div class="notice notice-warn"><?= icon('eye') ?><span>Режим предпросмотра: дело ещё не в игре, поэтому голос не сохраняется и не влияет на мир.</span></div>
    <?php endif; ?>

    <div class="result-choice">
        <span class="opt-letter opt-letter-lg"><?= $decision ? e($decision['key']) : '+' ?></span>
        <div>
            <span class="kicker">Ваше решение</span>
            <h2><?= e($decision['text'] ?? 'Другое решение') ?></h2>
        </div>
    </div>

    <?php if ($reasoning !== ''): ?>
        <blockquote class="your-reason">
            <span class="label-mono">Ваше обоснование</span>
            <?= paragraphs($reasoning) ?>
        </blockquote>
    <?php endif; ?>

    <div class="result-block">
        <h3 class="result-h"><?= icon('zap') ?>Последствия</h3>
        <?php if ($decision && decision_has_consequences($decision)): ?>
            <div class="conseq-grid">
                <?php $i = 0; foreach ($conseqTiles as $field => [$label, $ic]): if (trim($decision[$field] ?? '') === '') continue; ?>
                    <div class="conseq-tile" style="--d: <?= $i++ * 90 ?>ms">
                        <span class="conseq-label"><?= icon($ic) ?><?= e($label) ?></span>
                        <p><?= e($decision[$field]) ?></p>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php elseif (!$decision): ?>
            <p class="muted">Вашего решения нет среди вариантов сценария. Команда рассмотрит его — самые интересные обоснования попадут в игру.</p>
        <?php else: ?>
            <p class="muted">Автор пока не описал последствия этого решения.</p>
        <?php endif; ?>

        <?php if ($effects): ?>
            <div class="deltas">
                <?php foreach (METRICS as $k => $m): if (empty($effects[$k])) continue; $v = (int)$effects[$k]; ?>
                    <span class="delta <?= $v > 0 ? 'up' : 'down' ?>"><?= icon($m['icon']) ?><?= e($m['name']) ?> <b><?= $v > 0 ? '+' . $v * METRIC_STEP : $v * METRIC_STEP ?></b></span>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </div>

    <div class="result-split">
        <div class="result-block">
            <h3 class="result-h"><?= icon('chart') ?>Как решили другие <span class="result-sub"><?= $total ?> <?= plural($total, 'вердикт', 'вердикта', 'вердиктов') ?></span></h3>
            <?php if ($total === 0): ?>
                <p class="muted">По этому делу ещё никто не голосовал.</p>
            <?php endif; ?>
            <ul class="dist">
                <?php foreach ($rows as $r): $pct = $total ? (int)round($r['n'] / $total * 100) : 0; $mine = $r['key'] === $choice; ?>
                    <li class="dist-row<?= $mine ? ' is-mine' : '' ?>">
                        <span class="opt-letter opt-letter-sm"><?= $r['key'] === 'other' ? '+' : e($r['key']) ?></span>
                        <div class="dist-body">
                            <div class="dist-top">
                                <span class="dist-text"><?= e($r['text']) ?><?= $mine ? ' <em>ваш выбор</em>' : '' ?></span>
                                <b><?= $pct ?>%</b>
                            </div>
                            <div class="dist-bar"><i style="--w: <?= $pct ?>%"></i></div>
                        </div>
                    </li>
                <?php endforeach; ?>
            </ul>
        </div>

        <div class="result-block gauge-block">
            <h3 class="result-h"><?= icon('flame') ?>Индекс спорности</h3>
            <div class="gauge gauge-<?= e($contro['level']) ?>">
                <svg viewBox="0 0 120 68" aria-hidden="true">
                    <path class="g-track" d="M10 60 A50 50 0 0 1 110 60" pathLength="100"/>
                    <path class="g-fill" d="M10 60 A50 50 0 0 1 110 60" pathLength="100" style="--v: <?= (int)($contro['value'] ?? 0) ?>"/>
                </svg>
                <div class="gauge-val">
                    <b><?= $contro['value'] === null ? '—' : $contro['value'] . '%' ?></b>
                    <span><?= e($contro['label']) ?></span>
                </div>
            </div>
            <p class="muted small">Чем выше индекс, тем сильнее расходятся мнения игроков. Лучшие дела — те, о которых спорят.</p>
        </div>
    </div>

    <?php if ($amb['conflict'] !== ''): ?>
        <div class="result-block debate">
            <h3 class="result-h"><?= icon('swords') ?>Почему здесь нет правильного ответа</h3>
            <p class="debate-conflict"><?= e($amb['conflict']) ?></p>
            <?php if ($amb['for_one'] !== '' || $amb['for_other'] !== ''): ?>
                <div class="debate-vs">
                    <div class="arg arg-a"><span class="label-mono">Аргумент за одно решение</span><p><?= e($amb['for_one']) ?></p></div>
                    <span class="vs">VS</span>
                    <div class="arg arg-b"><span class="label-mono">Аргумент за другое</span><p><?= e($amb['for_other']) ?></p></div>
                </div>
            <?php endif; ?>
            <?php if ($amb['divide'] !== ''): ?>
                <p class="debate-divide"><?= icon('users') ?><span><b>Что разделяет игроков:</b> <?= e($amb['divide']) ?></span></p>
            <?php endif; ?>
        </div>
    <?php endif; ?>

    <details class="why-all">
        <summary><?= icon('message') ?>Аргументы за каждый вариант<?= icon('chevron-down', 'chev') ?></summary>
        <ul>
            <?php foreach ($s['decisions'] as $d): if (($d['why'] ?? '') === '') continue; ?>
                <li><span class="opt-letter opt-letter-sm"><?= e($d['key']) ?></span><div><b><?= e($d['text']) ?></b><p><?= e($d['why']) ?></p></div></li>
            <?php endforeach; ?>
        </ul>
    </details>

    <?php if (!empty($s['continuation']['possible'])): ?>
        <div class="continuation"><?= icon('branch') ?><div><b>У этого дела будет продолжение</b><p>Ваше решение может вернуться к вам в будущих событиях.</p></div></div>
    <?php endif; ?>

    <?php if (!empty($judge)): ?><?= partial('judge-teaser', ['judge' => $judge]) ?><?php endif; ?>

    <div class="result-actions">
        <?php if ($preview): ?>
            <a class="btn btn-primary" href="view.php?id=<?= $s['id'] ?>"><?= icon('file') ?>Вернуться к досье</a>
        <?php elseif ($next): ?>
            <a class="btn btn-primary" href="case.php?id=<?= $next['id'] ?>">Следующее дело<?= icon('arrow-right') ?></a>
        <?php else: ?>
            <a class="btn btn-primary" href="play.php"><?= icon('archive') ?>Все дела рассмотрены — в архив</a>
        <?php endif; ?>
        <button class="btn" type="button" data-share data-share-text="<?= e($shareText) ?>" data-share-url="case.php?id=<?= $s['id'] ?>"><?= icon('share') ?>Поделиться</button>
        <button class="btn btn-ghost" type="button" data-revisit><?= icon('refresh') ?>Пересмотреть дело</button>
    </div>
</section>
