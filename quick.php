<?php
/**
 * «Быстрый суд»: одно дело на экране, два касания — вердикт и догадка, как решило большинство.
 * quick.php — случайное нерассмотренное дело; quick.php?id=N — конкретное (если уже решено — сразу результат).
 */
require __DIR__ . '/includes/bootstrap.php';

$voter = voter_id();
$id = (int)($_GET['id'] ?? 0);
if ($id > 0) {
    $s = situation_find($id);
    if (!$s || $s['status'] !== 'approved') {
        // Дела не в игре открываются только как полное досье (предпросмотр для автора и команды).
        redirect($s && can_view_situation($s) ? 'case.php?id=' . $id : 'quick.php');
    }
} else {
    $s = random_open_case($voter);
}

$approvedIds = array_column(situations_list(['status' => 'approved']), 'id');
$doneCount = count(array_intersect_key(votes_of_voter($voter), array_flip($approvedIds)));
$stats = quick_stats($voter);
$myVote = $s ? vote_find($s['id'], $voter) : null;

page_header($s ? 'Быстрый суд — ' . $s['title'] : 'Быстрый суд', 'quick', 'page-quick', 'calm');
?>

<section class="page-hero page-hero-compact quick-hero">
    <div class="container quick-container">
        <span class="kicker">Быстрый суд</span>
        <h1>Вынесите вердикт. <span class="grad-text">Угадайте большинство.</span></h1>
        <div class="quick-stats">
            <span><?= icon('gavel') ?>Рассмотрено <b><?= $doneCount ?></b> из <?= count($approvedIds) ?></span>
            <span title="Сколько раз вы угадали выбор большинства"><?= icon('target') ?>Угадано <b><?= $stats['score'] ?></b> из <?= $stats['guesses'] ?></span>
            <?php if ($stats['streak'] > 1): ?><span class="streak"><?= icon('flame') ?>серия <?= $stats['streak'] ?></span><?php endif; ?>
            <?php $jp = judge_profile($voter); ?>
            <a class="quick-judge" href="judge.php"><?= icon($jp['archetype'] ? JUDGE_ARCHETYPES[$jp['archetype']]['icon'] : 'lock') ?><?= $jp['archetype'] ? 'Вы — «' . e(JUDGE_ARCHETYPES[$jp['archetype']]['name']) . '»' : 'Профиль судьи: ещё ' . $jp['left'] ?><?= icon('arrow-right') ?></a>
        </div>
    </div>
</section>

<section class="container quick-container section-top-0 quick-section">
    <?php if (!$s): ?>
        <div class="empty panel">
            <?= icon('check-circle') ?>
            <h2>Все дела рассмотрены</h2>
            <p>Вы вынесли вердикт по каждому делу в игре<?= $stats['guesses'] ? ' и угадали большинство ' . $stats['score'] . ' ' . plural($stats['score'], 'раз', 'раза', 'раз') . ' из ' . $stats['guesses'] : '' ?>. Новые дела появляются, когда команда одобряет ситуации авторов.</p>
            <div class="hero-actions">
                <a class="btn btn-primary" href="play.php"><?= icon('archive') ?>Архив дел</a>
                <a class="btn" href="create.php"><?= icon('edit') ?>Предложить своё дело</a>
            </div>
        </div>
    <?php else:
        $cat = CATEGORIES[$s['category']] ?? ['name' => $s['category'], 'icon' => 'circle'];
        $type = SITUATION_TYPES[$s['type']] ?? ['name' => $s['type'], 'icon' => 'circle'];
    ?>
        <article class="panel quick-card" style="<?= e(category_style($s['category'])) ?>">
            <div class="case-meta">
                <span class="case-no">Дело <?= e(case_number($s['id'])) ?></span>
                <span class="chip chip-cat chip-sm"><?= icon($cat['icon']) ?><?= e($cat['name']) ?></span>
                <span class="chip chip-sm"><?= icon($type['icon']) ?><?= e($type['name']) ?></span>
            </div>
            <h2 class="quick-title"><?= e($s['title']) ?></h2>

            <?= partial('comic', ['s' => $s, 'full' => true, 'finish' => '[data-quick]:not([hidden]), #quick-result', 'finishLabel' => 'К вердикту']) ?>

            <div class="quick-steps" data-quick data-situation="<?= $s['id'] ?>"<?= $myVote ? ' hidden' : '' ?>>
                <div class="quick-step" data-step="1">
                    <h3 class="quick-step-h"><span class="quick-step-num">1</span>Ваш вердикт</h3>
                    <?php $people = array_filter(comic_cast($s), static fn(array $c): bool => !$c['witness']); ?>
                    <?php if ($people): ?>
                        <div class="quick-cast" aria-label="Кто есть кто">
                            <?php foreach ($people as $i => $c): ?>
                                <span class="qc" style="--ah: <?= $c['hue'] ?>"><svg viewBox="0 0 120 140" aria-hidden="true"><use href="#cm<?= $s['id'] ?>-<?= $i ?>"/></svg><b><?= e($c['short']) ?></b><?php if ($c['role'] !== ''): ?><small><?= e(excerpt($c['role'], 28)) ?></small><?php endif; ?></span>
                            <?php endforeach; ?>
                        </div>
                    <?php endif; ?>
                    <div class="quick-options">
                        <?php foreach ($s['decisions'] as $i => $d): ?>
                            <button type="button" class="option quick-option" data-pick="<?= e($d['key']) ?>">
                                <span class="opt-letter"><?= e($d['key']) ?></span>
                                <span class="opt-text"><?= e($d['text']) ?></span>
                                <kbd><?= $i + 1 ?></kbd>
                            </button>
                        <?php endforeach; ?>
                    </div>
                </div>
                <div class="quick-step" data-step="2" hidden>
                    <h3 class="quick-step-h"><span class="quick-step-num">2</span>Как решило большинство?</h3>
                    <p class="quick-step-lead">Ваш вердикт: <b data-picked-text></b> <button type="button" class="link-btn" data-repick>изменить</button><br>Угадайте самый популярный выбор других игроков — за верную догадку +1 к счёту.</p>
                    <div class="quick-options quick-guesses">
                        <?php foreach ($s['decisions'] as $i => $d): ?>
                            <button type="button" class="option quick-option" data-guess="<?= e($d['key']) ?>">
                                <span class="opt-letter"><?= e($d['key']) ?></span>
                                <span class="opt-text"><?= e($d['text']) ?></span>
                                <kbd><?= $i + 1 ?></kbd>
                            </button>
                        <?php endforeach; ?>
                    </div>
                    <button type="button" class="link-btn quick-skip" data-guess="">Не угадывать — показать результат</button>
                </div>
                <p class="form-error" role="alert" hidden></p>
            </div>

            <div data-quick-result>
                <?php if ($myVote): ?>
                    <?= partial('quick-result', [
                        's'        => $s,
                        'choice'   => $myVote['option_key'],
                        'guess'    => $myVote['guess_key'],
                        'majority' => majority_keys($s['id'], $voter),
                        'correct'  => $myVote['guess_correct'] === null ? null : (int)$myVote['guess_correct'],
                        'counts'   => vote_counts_for($s['id']),
                        'stats'    => $stats,
                        'judge'    => ['profile' => $jp, 'event' => null],
                    ]) ?>
                <?php endif; ?>
            </div>
        </article>
        <p class="quick-alt"><?= icon('info') ?>Хотите разобрать дело подробно, с мотивами и последствиями? <a href="case.php?id=<?= $s['id'] ?>">Откройте полное досье</a>.</p>
    <?php endif; ?>
</section>

<?php page_footer(['comic.js', 'quick.js']); ?>
