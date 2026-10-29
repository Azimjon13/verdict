<?php
require __DIR__ . '/includes/bootstrap.php';

$id = (int)($_GET['id'] ?? 0);
$s = $id > 0 ? situation_find($id) : null;

if (!$s || !can_view_situation($s)) {
    http_response_code(404);
    page_header('Дело не найдено', 'play', 'page-case', 'calm');
    ?>
    <section class="section">
        <div class="container">
            <div class="empty panel">
                <?= icon('search') ?>
                <h1>Дело не найдено</h1>
                <p>Возможно, его удалили или ссылка указана неверно.</p>
                <a class="btn btn-primary" href="play.php"><?= icon('archive') ?>В архив дел</a>
            </div>
        </div>
    </section>
    <?php
    page_footer();
    exit;
}

$preview = $s['status'] !== 'approved';
$myVote = $preview ? null : vote_find($s['id'], voter_id());
$counts = vote_counts_for($s['id']);
$cat = CATEGORIES[$s['category']] ?? ['name' => $s['category'], 'icon' => 'circle'];
$type = SITUATION_TYPES[$s['type']] ?? ['name' => $s['type'], 'icon' => 'circle'];
$hasWitnesses = $s['witnesses'] !== [];

$sections = [
    'story'    => 'Ситуация',
    'people'   => 'Участники',
    'evidence' => 'Улики',
];
if ($hasWitnesses) {
    $sections['witnesses'] = 'Свидетели';
}
$sections['verdict'] = 'Вердикт';
$num = 0;
$blockNum = static function () use (&$num): string {
    return str_pad((string)++$num, 2, '0', STR_PAD_LEFT);
};

page_header($s['title'], 'play', 'page-case', 'calm');
?>

<section class="case-hero" style="<?= e(category_style($s['category'])) ?>">
    <div class="container">
        <a class="back-link" href="<?= $preview ? 'view.php?id=' . $s['id'] : 'play.php' ?>"><?= icon('arrow-left') ?><?= $preview ? 'К досье' : 'Архив дел' ?></a>
        <div class="case-meta">
            <span class="case-no">Дело <?= e(case_number($s['id'])) ?></span>
            <span class="chip chip-cat"><?= icon($cat['icon']) ?><?= e($cat['name']) ?></span>
            <span class="chip"><?= icon($type['icon']) ?><?= e($type['name']) ?></span>
            <?php if ($preview): ?><span class="chip chip-warn"><?= icon('eye') ?>Предпросмотр</span><?php endif; ?>
        </div>
        <h1 class="case-title glitch-once" data-text="<?= e($s['title']) ?>"><?= e($s['title']) ?></h1>
        <p class="case-setting"><?= icon('map-pin') ?><?= e($s['world']['place']) ?><?php if ($s['world']['era'] !== ''): ?><span class="sep">//</span><?= e($s['world']['era']) ?><?php endif; ?></p>
    </div>
</section>

<div class="container case-layout">
    <article class="dossier">
        <section class="block panel" id="story">
            <header class="block-head"><span class="block-num"><?= $blockNum() ?></span><h2>Мир и ситуация</h2></header>
            <?= partial('comic', ['s' => $s, 'full' => false, 'finish' => '#people', 'finishLabel' => 'К участникам']) ?>
        </section>

        <section class="block panel reveal" id="people">
            <header class="block-head"><span class="block-num"><?= $blockNum() ?></span><h2>Участники</h2></header>
            <div class="people">
                <?php foreach ($s['participants'] as $p): ?>
                    <div class="person">
                        <span class="avatar" style="--ah: <?= name_hue($p['name']) ?>"><?= e(initials($p['name'])) ?></span>
                        <div class="person-body">
                            <h3><?= e($p['name']) ?><?php if ($p['age'] !== ''): ?> <small><?= e($p['age']) ?><?= ctype_digit($p['age']) ? ' ' . plural((int)$p['age'], 'год', 'года', 'лет') : '' ?></small><?php endif; ?></h3>
                            <?php if ($p['role'] !== ''): ?><span class="person-role"><?= e($p['role']) ?></span><?php endif; ?>
                            <?php if ($p['description'] !== ''): ?><p><?= e($p['description']) ?></p><?php endif; ?>
                            <?php if ($p['relations'] !== ''): ?><p class="person-rel"><?= icon('link') ?><?= e($p['relations']) ?></p><?php endif; ?>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="block panel reveal" id="evidence">
            <header class="block-head"><span class="block-num"><?= $blockNum() ?></span><h2>Доказательства и информация</h2></header>
            <div class="evidence">
                <div class="evidence-col">
                    <h3 class="evidence-h facts-h"><?= icon('check-circle') ?>Известно точно</h3>
                    <ul class="evidence-list facts">
                        <?php foreach ($s['facts'] as $i => $f): ?>
                            <li><span class="ev-num">Факт <?= $i + 1 ?></span><?= e($f) ?></li>
                        <?php endforeach; ?>
                    </ul>
                </div>
                <?php if ($s['unknowns']): ?>
                    <div class="evidence-col">
                        <h3 class="evidence-h unknown-h"><?= icon('help') ?>Неизвестно / вызывает сомнение</h3>
                        <ul class="evidence-list unknowns">
                            <?php foreach ($s['unknowns'] as $u): ?>
                                <li><?= e($u) ?></li>
                            <?php endforeach; ?>
                        </ul>
                    </div>
                <?php endif; ?>
            </div>
        </section>

        <?php if ($hasWitnesses): ?>
            <section class="block panel reveal" id="witnesses">
                <header class="block-head"><span class="block-num"><?= $blockNum() ?></span><h2>Показания свидетелей</h2></header>
                <p class="block-note"><?= icon('alert') ?>Свидетели могут ошибаться, лгать, скрывать информацию или иметь собственный интерес.</p>
                <div class="witnesses">
                    <?php foreach ($s['witnesses'] as $i => $w): ?>
                        <div class="witness">
                            <div class="witness-head">
                                <span class="avatar avatar-sm" style="--ah: <?= name_hue($w['name']) ?>"><?= e(initials($w['name'])) ?></span>
                                <div><span class="label-mono">Свидетель <?= $i + 1 ?></span><h3><?= e($w['name']) ?></h3></div>
                            </div>
                            <blockquote><?= icon('quote', 'quote-icon') ?><?= e($w['claim']) ?></blockquote>
                            <dl class="witness-meta">
                                <?php if ($w['trust'] !== ''): ?><div><dt><?= icon('shield') ?>Надёжность</dt><dd><?= e($w['trust']) ?></dd></div><?php endif; ?>
                                <?php if ($w['interest'] !== ''): ?><div><dt><?= icon('target') ?>Личный интерес</dt><dd><?= e($w['interest']) ?></dd></div><?php endif; ?>
                            </dl>
                        </div>
                    <?php endforeach; ?>
                </div>
            </section>
        <?php endif; ?>

        <form class="block panel verdict-form reveal" id="verdict" data-situation="<?= $s['id'] ?>"<?= $myVote ? ' hidden' : '' ?>>
            <header class="block-head"><span class="block-num"><?= $blockNum() ?></span><h2>Ваш вердикт</h2></header>
            <p class="block-lead">Выберите решение. Подумайте, сможете ли вы объяснить его — себе и другим.</p>
            <input type="hidden" name="situation_id" value="<?= $s['id'] ?>">
            <div class="options" role="radiogroup" aria-label="Варианты решения">
                <?php foreach ($s['decisions'] as $d): ?>
                    <label class="option">
                        <input type="radio" name="option" value="<?= e($d['key']) ?>">
                        <span class="opt-letter"><?= e($d['key']) ?></span>
                        <span class="opt-text"><?= e($d['text']) ?></span>
                        <span class="opt-check"><?= icon('check') ?></span>
                    </label>
                <?php endforeach; ?>
                <label class="option option-other">
                    <input type="radio" name="option" value="other">
                    <span class="opt-letter">+</span>
                    <span class="opt-text">Другое решение<small>Предложите своё обоснованное решение</small></span>
                    <span class="opt-check"><?= icon('check') ?></span>
                </label>
            </div>
            <label class="field reasoning">
                <span data-reason-label>Почему вы выбрали это решение? <em>(необязательно)</em></span>
                <textarea name="reasoning" rows="3" maxlength="1000" placeholder="«Я понимаю, почему он так поступил, но всё равно считаю…»"></textarea>
            </label>
            <button type="button" class="hold-btn" disabled aria-describedby="hold-hint">
                <span class="hold-fill"></span>
                <span class="hold-label"><?= icon('gavel') ?><span data-hold-text>Удерживайте, чтобы вынести вердикт</span></span>
            </button>
            <p class="hold-hint" id="hold-hint">Нажмите и удерживайте кнопку (или клавишу Enter) — решение нельзя принять случайно.</p>
            <p class="form-error" role="alert" hidden></p>
        </form>

        <div id="verdict-result">
            <?php if ($myVote): ?>
                <?= partial('result', [
                    's'         => $s,
                    'choice'    => $myVote['option_key'],
                    'reasoning' => $myVote['reasoning'],
                    'counts'    => $counts,
                    'preview'   => false,
                    'next'      => next_case($s['id'], voter_id()),
                    'fresh'     => false,
                    'judge'     => ['profile' => judge_profile(voter_id()), 'event' => null],
                ]) ?>
            <?php endif; ?>
        </div>
    </article>

    <aside class="case-side">
        <nav class="panel case-nav" aria-label="Разделы дела">
            <span class="label-mono">Досье</span>
            <?php $n = 0; foreach ($sections as $anchor => $label): ?>
                <a href="#<?= $anchor ?>"><span><?= str_pad((string)++$n, 2, '0', STR_PAD_LEFT) ?></span><?= e($label) ?></a>
            <?php endforeach; ?>
        </nav>
        <?php if (!$preview): ?>
            <?= partial('world', ['back' => 'case.php?id=' . $s['id']]) ?>
        <?php endif; ?>
        <div class="panel side-tip">
            <?= icon('info') ?>
            <p>Не ищите правильный ответ — его нет. Важно, сможете ли вы объяснить своё решение.</p>
        </div>
    </aside>
</div>

<?php page_footer(['comic.js', 'case.js']); ?>
