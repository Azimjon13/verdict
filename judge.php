<?php
/**
 * Профиль судьи: какой вы судья — по вашим вердиктам (см. includes/judge.php).
 * judge.php?a=<стиль> — карточка стиля, которой поделился другой игрок.
 */
require __DIR__ . '/includes/bootstrap.php';

$voter = voter_id();
$p = judge_profile($voter);
$type = $p['archetype'] !== null ? JUDGE_ARCHETYPES[$p['archetype']] : null;
$_SESSION['judge_archetype'] = $p['archetype']; // уже показали — после следующего вердикта не объявлять «открыт» заново
$shared = isset($_GET['a'], JUDGE_ARCHETYPES[$_GET['a']]) ? (string)$_GET['a'] : null;
$census = judge_archetype_shares();

$pct = static fn(float $x): string => ($x > 0 ? '+' : ($x < 0 ? '−' : '')) . abs((int)round($x * 100)) . '%';
$majorityPct = $p['compared'] >= 3 ? (int)round($p['with_majority'] / $p['compared'] * 100) : null;
$traits = [];
if ($majorityPct !== null) {
    $traits[] = $majorityPct >= 65 ? ['users', 'Голос большинства'] : ($majorityPct <= 35 ? ['flag', 'Особое мнение'] : ['scale', 'Независимый взгляд']);
}
if ($p['median_ms'] !== null) {
    $traits[] = $p['median_ms'] < 30000 ? ['zap', 'Решает быстро'] : ($p['median_ms'] > 120000 ? ['hourglass', 'Взвешивает долго'] : ['clock', 'Обдумывает']);
}
if ($p['own'] > 0) {
    $traits[] = ['sparkles', 'Предлагает свои решения'];
}
if ($p['quick']['guesses'] >= 3 && $p['quick']['score'] / $p['quick']['guesses'] >= 0.6) {
    $traits[] = ['target', 'Чувствует, как решат другие'];
}

page_header($type ? 'Профиль судьи — ' . $type['name'] : 'Профиль судьи', 'judge', 'page-judge', 'calm');
?>

<section class="page-hero page-hero-compact">
    <div class="container judge-container">
        <span class="kicker">Профиль судьи</span>
        <h1>Какой вы <span class="grad-text">судья?</span></h1>
        <p class="lead">Профиль складывается из ваших вердиктов: какие показатели мира вы склонны поднимать, как часто решаете так же, как большинство, и сколько думаете над делом. Он меняется с каждым вердиктом и хранится в этом браузере.</p>
    </div>
</section>

<section class="container judge-container section-top-0 judge-section">
    <?php if ($shared !== null): $st = JUDGE_ARCHETYPES[$shared]; ?>
        <div class="panel judge-shared">
            <span class="jd-emblem jd-emblem-sm"><?= icon($st['icon']) ?></span>
            <div>
                <span class="label-mono">Вам прислали профиль судьи</span>
                <h2>«<?= e($st['name']) ?>»</h2>
                <p><?= e($st['desc']) ?></p>
                <?php if ($type === null): ?><a class="btn btn-primary btn-sm" href="quick.php"><?= icon('play') ?>Узнать, какой судья вы</a><?php endif; ?>
            </div>
        </div>
    <?php endif; ?>

    <?php if ($type === null): ?>
        <div class="panel judge-locked">
            <span class="jd-emblem jd-emblem-locked"><?= icon('lock') ?></span>
            <h2>Профиль откроется после <?= JUDGE_MIN_VERDICTS ?> вердиктов</h2>
            <p class="muted">Осталось <?= $p['left'] ?> <?= plural($p['left'], 'вердикт', 'вердикта', 'вердиктов') ?>. Вариант «Другое решение» не считается: профиль строится по тому, какие варианты вы выбираете.</p>
            <div class="jd-progress" role="progressbar" aria-valuemin="0" aria-valuemax="<?= JUDGE_MIN_VERDICTS ?>" aria-valuenow="<?= min($p['decided'], JUDGE_MIN_VERDICTS) ?>" aria-label="Вердиктов для профиля">
                <i style="width: <?= min(100, (int)round($p['decided'] / JUDGE_MIN_VERDICTS * 100)) ?>%"></i>
            </div>
            <p class="jd-progress-label"><?= min($p['decided'], JUDGE_MIN_VERDICTS) ?> из <?= JUDGE_MIN_VERDICTS ?></p>
            <ul class="jd-preview">
                <li><?= icon('sparkles') ?>Ваш судейский стиль — один из <?= count(JUDGE_ARCHETYPES) ?></li>
                <li><?= icon('chart') ?>Какие показатели мира вы склонны поднимать и опускать</li>
                <li><?= icon('users') ?>Как часто вы решаете так же, как большинство</li>
            </ul>
            <a class="btn btn-primary" href="quick.php"><?= icon('play') ?>Быстрый суд</a>
        </div>
    <?php else: ?>
        <article class="panel judge-card">
            <span class="jd-emblem"><?= icon($type['icon']) ?></span>
            <div class="jd-head">
                <span class="label-mono">Ваш стиль</span>
                <h2><?= e($type['name']) ?></h2>
                <?php if ($census['players'] >= 5): ?>
                    <p class="jd-census"><?= icon('users') ?>Так судят <?= (int)round(($census['shares'][$p['archetype']] ?? 0) * 100) ?>% игроков с открытым профилем</p>
                <?php endif; ?>
            </div>
            <p class="jd-desc"><?= e($type['desc']) ?></p>
            <div class="jd-sides">
                <div><span class="label-mono"><?= icon('check-circle') ?>Сильная сторона</span><p><?= e($type['strength']) ?></p></div>
                <div><span class="label-mono"><?= icon('eye-off') ?>Слепое пятно</span><p><?= e($type['blind']) ?></p></div>
            </div>
            <?php if ($traits): ?>
                <ul class="jd-traits" aria-label="Черты">
                    <?php foreach ($traits as [$ic, $label]): ?><li><?= icon($ic) ?><?= e($label) ?></li><?php endforeach; ?>
                </ul>
            <?php endif; ?>
            <div class="jd-actions">
                <button type="button" class="btn" data-share data-share-url="judge.php?a=<?= e($p['archetype']) ?>"
                        data-share-text="Мой стиль в VERDICT — «<?= e($type['name']) ?>». А какой судья вы?"><?= icon('share') ?><span>Поделиться</span></button>
                <a class="btn btn-primary" href="quick.php"><?= icon('play') ?>Судить дальше</a>
            </div>
        </article>

        <section class="panel jd-chart" aria-labelledby="jd-chart-title">
            <h2 class="jd-chart-title" id="jd-chart-title">Какие показатели мира вы поднимаете</h2>
            <p class="jd-chart-sub">По сравнению с другими вариантами в тех же делах. +100% — вы всегда выбирали вариант, который поднимает показатель сильнее всех; −100% — сильнее всех опускает; 0 — как в среднем.</p>
            <div class="jd-legend" aria-hidden="true"><span class="down"><i></i>опускаете</span><span class="up"><i></i>поднимаете</span></div>
            <div class="jd-rows">
                <?php foreach (METRICS as $m => $meta): $l = $p['leans'][$m]; $w = min(100, abs($l['lean']) * 100); ?>
                    <div class="jd-row" tabindex="0" aria-describedby="jd-tip-<?= $m ?>">
                        <span class="jd-metric"><?= icon($meta['icon']) ?><?= e($meta['name']) ?></span>
                        <span class="jd-track">
                            <span class="jd-zero"></span>
                            <?php if ($l['relevant'] > 0 && $w >= 1): ?>
                                <span class="jd-bar <?= $l['lean'] > 0 ? 'up' : 'down' ?>" style="width: <?= round($w / 2, 1) ?>%"></span>
                            <?php endif; ?>
                        </span>
                        <span class="jd-value"><?= $l['relevant'] > 0 ? $pct($l['lean']) : '—' ?></span>
                        <span class="jd-tip" role="tooltip" id="jd-tip-<?= $m ?>">
                            <?php if ($l['relevant'] > 0): ?>
                                <b><?= $pct($l['lean']) ?></b> <?= e($meta['name']) ?><br>
                                Сильнее других вариантов: <?= $l['more'] ?> из <?= $l['relevant'] ?> · слабее: <?= $l['less'] ?>
                            <?php else: ?>
                                В ваших делах варианты не различались по этому показателю.
                            <?php endif; ?>
                        </span>
                    </div>
                <?php endforeach; ?>
                <div class="jd-axis" aria-hidden="true"><span>−100%</span><span>0</span><span>+100%</span></div>
            </div>
            <details class="jd-table">
                <summary><?= icon('layers') ?>Показать таблицей</summary>
                <table>
                    <thead><tr><th scope="col">Показатель</th><th scope="col">Склонность</th><th scope="col">Сильнее других</th><th scope="col">Слабее других</th><th scope="col">Дел с выбором</th></tr></thead>
                    <tbody>
                        <?php foreach (METRICS as $m => $meta): $l = $p['leans'][$m]; ?>
                            <tr><th scope="row"><?= e($meta['name']) ?></th><td><?= $l['relevant'] > 0 ? $pct($l['lean']) : '—' ?></td><td><?= $l['more'] ?></td><td><?= $l['less'] ?></td><td><?= $l['relevant'] ?></td></tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </details>
        </section>
    <?php endif; ?>

    <?php if ($p['verdicts'] > 0): /* пока нет ни одного вердикта, плитки из прочерков — только шум */ ?>
    <div class="jd-tiles">
        <div class="panel jd-tile"><span class="jd-tile-label">Вердиктов</span><b><?= $p['verdicts'] ?></b><?php if ($p['own']): ?><small>своих решений: <?= $p['own'] ?></small><?php endif; ?></div>
        <div class="panel jd-tile"><span class="jd-tile-label">Решали как большинство</span><b><?= $majorityPct !== null ? $majorityPct . '%' : '—' ?></b><small><?= $majorityPct !== null ? 'в ' . $p['with_majority'] . ' из ' . $p['compared'] . ' дел' : 'пока мало голосов для сравнения' ?></small></div>
        <div class="panel jd-tile"><span class="jd-tile-label">Угадали большинство</span><b><?= $p['quick']['guesses'] ? $p['quick']['score'] . ' из ' . $p['quick']['guesses'] : '—' ?></b><small><?= $p['quick']['guesses'] ? 'в «Быстром суде»' : 'угадывайте в «Быстром суде»' ?></small></div>
        <div class="panel jd-tile"><span class="jd-tile-label">Обычно на решение</span><b><?= $p['median_ms'] !== null ? e(format_duration($p['median_ms'])) : '—' ?></b><small><?= $p['median_ms'] !== null ? 'медиана по вашим делам' : 'нужно хотя бы 3 вердикта' ?></small></div>
    </div>
    <?php endif; ?>

    <?php if ($p['boldest'] !== null || $p['top_category'] !== null): ?>
        <div class="jd-notes">
            <?php if ($p['boldest'] !== null): $b = $p['boldest']; $bp = (int)round($b['share'] * 100); ?>
                <a class="panel jd-note" href="case.php?id=<?= $b['id'] ?>">
                    <?= icon('flag') ?>
                    <span><span class="label-mono">Самое смелое решение</span>
                    <?= $bp === 0 ? 'В деле «' . e($b['title']) . '» никто из ' . $b['others'] . ' игроков не выбрал то же, что вы.' : 'В деле «' . e($b['title']) . '» с вами согласились только ' . $bp . '% игроков.' ?></span>
                    <?= icon('arrow-right') ?>
                </a>
            <?php endif; ?>
            <?php if ($p['top_category'] !== null): $c = CATEGORIES[$p['top_category']] ?? null; ?>
                <a class="panel jd-note" href="play.php?category=<?= e($p['top_category']) ?>" style="<?= e(category_style($p['top_category'])) ?>">
                    <?= icon($c['icon'] ?? 'circle') ?>
                    <span><span class="label-mono">Чаще всего судите</span><?= e($c['name'] ?? $p['top_category']) ?></span>
                    <?= icon('arrow-right') ?>
                </a>
            <?php endif; ?>
        </div>
    <?php endif; ?>

    <p class="jd-footnote"><?= icon('info') ?>Профиль привязан к этому браузеру: в другом браузере или после очистки cookie он начнётся заново.</p>
</section>

<?php page_footer(['judge.js']); ?>
