<?php
require __DIR__ . '/includes/bootstrap.php';

$s = situation_find((int)($_GET['id'] ?? 0));
if (!$s || !can_view_situation($s)) {
    flash('error', 'Ситуация не найдена.');
    redirect('library.php');
}

$admin = is_admin();
$cat = CATEGORIES[$s['category']] ?? ['name' => $s['category'], 'icon' => 'circle'];
$type = SITUATION_TYPES[$s['type']] ?? ['name' => $s['type'], 'icon' => 'circle'];
$counts = vote_counts_for($s['id']);
$total = array_sum($counts);
$contro = controversy($counts, max(2, count($s['decisions'])));
$back = 'view.php?id=' . $s['id'];

$row = static function (string $label, string $value): string {
    return $value === '' ? '' : '<div class="kv"><dt>' . e($label) . '</dt><dd>' . nl2br(e($value)) . '</dd></div>';
};

page_header($s['title'] . ' — досье', 'library', 'page-view', 'calm');
?>

<section class="case-hero" style="<?= e(category_style($s['category'])) ?>">
    <div class="container">
        <a class="back-link" href="library.php"><?= icon('arrow-left') ?>Отбор контента</a>
        <div class="case-meta">
            <span class="case-no">Досье <?= e(case_number($s['id'])) ?></span>
            <span class="status status-<?= e($s['status']) ?>"><?= e(STATUSES[$s['status']] ?? $s['status']) ?></span>
            <?php if (owns_situation($s)): ?><span class="chip chip-mine"><?= icon('user') ?>Ваша ситуация</span><?php endif; ?>
            <span class="chip chip-cat"><?= icon($cat['icon']) ?><?= e($cat['name']) ?></span>
            <span class="chip"><?= icon($type['icon']) ?><?= e($type['name']) ?></span>
            <?= level_chip(situation_level($s), '') ?>
        </div>
        <h1 class="case-title"><?= e($s['title']) ?></h1>
        <p class="case-setting"><?= icon('user') ?><?= e($s['author'] ?: 'Без автора') ?><span class="sep">//</span><?= icon('calendar') ?><?= e(format_date($s['created_at'])) ?></p>
    </div>
</section>

<div class="container case-layout">
    <article class="dossier dossier-full">
        <section class="block panel">
            <header class="block-head"><span class="block-num">01</span><h2>Основная информация</h2></header>
            <dl class="kv-list">
                <?= $row('Категория', $cat['name']) ?>
                <?= $row('Тип ситуации', $type['name']) ?>
                <?= $row('Название', $s['title']) ?>
                <?= $row('Автор', $s['author']) ?>
            </dl>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">02</span><h2>Мир / Сеттинг</h2></header>
            <dl class="kv-list">
                <?= $row('Тип мира', $s['world']['setting']) ?>
                <?= $row('Место', $s['world']['place']) ?>
                <?= $row('Время / эпоха', $s['world']['era']) ?>
                <?= $row('Обстоятельства', $s['world']['circumstances']) ?>
            </dl>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">03</span><h2>Ситуация</h2><span class="chip chip-sm"><?= word_count($s['story']) ?> слов</span></header>
            <div class="prose story"><?= paragraphs($s['story']) ?></div>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">04</span><h2>Участники</h2></header>
            <div class="people">
                <?php foreach ($s['participants'] as $i => $p): ?>
                    <div class="person">
                        <span class="avatar" style="--ah: <?= name_hue($p['name']) ?>"><?= e(initials($p['name'])) ?></span>
                        <div class="person-body">
                            <span class="label-mono">Участник <?= $i + 1 ?></span>
                            <h3><?= e($p['name']) ?><?php if ($p['age'] !== ''): ?> <small><?= e($p['age']) ?></small><?php endif; ?></h3>
                            <dl class="kv-list kv-compact">
                                <?= $row('Роль', $p['role']) ?>
                                <?= $row('Отношение к другим', $p['relations']) ?>
                                <?= $row('Краткое описание', $p['description']) ?>
                            </dl>
                        </div>
                    </div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">05</span><h2>Доказательства и доступная информация</h2></header>
            <div class="evidence">
                <div class="evidence-col">
                    <h3 class="evidence-h facts-h"><?= icon('check-circle') ?>Факты</h3>
                    <ul class="evidence-list facts">
                        <?php foreach ($s['facts'] as $i => $f): ?><li><span class="ev-num">Факт <?= $i + 1 ?></span><?= e($f) ?></li><?php endforeach; ?>
                    </ul>
                </div>
                <div class="evidence-col">
                    <h3 class="evidence-h unknown-h"><?= icon('help') ?>Неизвестно / вызывает сомнение</h3>
                    <?php if ($s['unknowns']): ?>
                        <ul class="evidence-list unknowns"><?php foreach ($s['unknowns'] as $u): ?><li><?= e($u) ?></li><?php endforeach; ?></ul>
                    <?php else: ?><p class="muted">Не указано.</p><?php endif; ?>
                </div>
            </div>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">06</span><h2>Свидетели</h2></header>
            <?php if ($s['witnesses']): ?>
                <div class="witnesses">
                    <?php foreach ($s['witnesses'] as $i => $w): ?>
                        <div class="witness">
                            <div class="witness-head">
                                <span class="avatar avatar-sm" style="--ah: <?= name_hue($w['name']) ?>"><?= e(initials($w['name'])) ?></span>
                                <div><span class="label-mono">Свидетель <?= $i + 1 ?></span><h3><?= e($w['name']) ?></h3></div>
                            </div>
                            <blockquote><?= icon('quote', 'quote-icon') ?><?= e($w['claim']) ?></blockquote>
                            <dl class="witness-meta">
                                <?php if ($w['trust'] !== ''): ?><div><dt><?= icon('shield') ?>Насколько можно доверять</dt><dd><?= e($w['trust']) ?></dd></div><?php endif; ?>
                                <?php if ($w['interest'] !== ''): ?><div><dt><?= icon('target') ?>Личный интерес</dt><dd><?= e($w['interest']) ?></dd></div><?php endif; ?>
                            </dl>
                        </div>
                    <?php endforeach; ?>
                </div>
            <?php else: ?>
                <p class="muted">Частная ситуация — свидетелей нет.</p>
            <?php endif; ?>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">07–08</span><h2>Решения и последствия</h2></header>
            <div class="decisions-full">
                <?php foreach ($s['decisions'] as $d): $n = $counts[$d['key']] ?? 0; ?>
                    <div class="decision-full">
                        <div class="decision-top">
                            <span class="opt-letter"><?= e($d['key']) ?></span>
                            <div>
                                <h3><?= e($d['text']) ?></h3>
                                <?php if ($d['why'] !== ''): ?><p class="muted"><b>Почему могут выбрать:</b> <?= e($d['why']) ?></p><?php endif; ?>
                            </div>
                            <span class="decision-votes" title="Голосов"><?= $n ?><small><?= $total ? round($n / $total * 100) : 0 ?>%</small></span>
                        </div>
                        <?php if (decision_has_consequences($d)): ?>
                            <dl class="kv-list kv-grid">
                                <?= $row('Немедленное последствие', $d['immediate']) ?>
                                <?= $row('Долгосрочное последствие', $d['longterm']) ?>
                                <?= $row('Влияние на персонажей', $d['characters']) ?>
                                <?= $row('Влияние на общество / мир', $d['world']) ?>
                            </dl>
                        <?php endif; ?>
                        <?php if (array_filter($d['effects'] ?? [])): ?>
                            <div class="deltas">
                                <?php foreach (METRICS as $k => $m): if (empty($d['effects'][$k])) continue; $v = (int)$d['effects'][$k]; ?>
                                    <span class="delta <?= $v > 0 ? 'up' : 'down' ?>"><?= icon($m['icon']) ?><?= e($m['name']) ?> <b><?= $v > 0 ? '+' . $v : $v ?></b></span>
                                <?php endforeach; ?>
                            </div>
                        <?php endif; ?>
                    </div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="block panel section-secret">
            <header class="block-head"><span class="block-num">09</span><h2>Скрытая информация</h2><span class="chip chip-warn"><?= icon('eye-off') ?>Команде и автору</span></header>
            <?php if (can_see_hidden($s)): ?>
                <?= $s['hidden'] !== '' ? '<div class="prose">' . paragraphs($s['hidden']) . '</div>' : '<p class="muted">Автор не заполнил этот раздел.</p>' ?>
            <?php else: ?>
                <div class="classified">
                    <?= icon('lock') ?>
                    <div>
                        <b>Засекречено</b>
                        <p><?= $s['hidden'] !== '' ? 'Раздел заполнен автором и доступен только команде и самому автору.' : 'Автор не заполнил этот раздел.' ?></p>
                    </div>
                    <?php if (!is_logged_in()): ?><a class="btn btn-sm" href="login.php?back=<?= e(urlencode($back)) ?>"><?= icon('login') ?>Войти</a><?php endif; ?>
                </div>
            <?php endif; ?>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">10</span><h2>Почему ситуация неоднозначная</h2></header>
            <dl class="kv-list">
                <?= $row('Главный конфликт', $s['ambiguity']['conflict']) ?>
                <?= $row('Аргумент в пользу одного решения', $s['ambiguity']['for_one']) ?>
                <?= $row('Аргумент в пользу другого решения', $s['ambiguity']['for_other']) ?>
                <?= $row('Что может разделить мнение игроков', $s['ambiguity']['divide']) ?>
            </dl>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">11</span><h2>Потенциал для продолжения</h2><span class="chip chip-sm"><?= $s['continuation']['possible'] ? 'Да' : 'Нет' ?></span></header>
            <?= $s['continuation']['possible'] && $s['continuation']['text'] !== '' ? '<div class="prose">' . paragraphs($s['continuation']['text']) . '</div>' : '<p class="muted">Продолжение не предусмотрено.</p>' ?>
        </section>

        <section class="block panel">
            <header class="block-head"><span class="block-num">12</span><h2>Дополнительные заметки автора</h2></header>
            <?= $s['notes'] !== '' ? '<div class="prose">' . paragraphs($s['notes']) . '</div>' : '<p class="muted">Заметок нет.</p>' ?>
        </section>
    </article>

    <aside class="case-side">
        <div class="panel side-card">
            <span class="label-mono">Действия</span>
            <a class="btn btn-primary btn-block" href="case.php?id=<?= $s['id'] ?>"><?= icon('play') ?>Пройти как игрок</a>
            <?php if (can_edit_situation($s)): ?>
                <a class="btn btn-block" href="create.php?edit=<?= $s['id'] ?>"><?= icon('edit') ?><?= $s['status'] === 'draft' ? 'Продолжить черновик' : 'Редактировать' ?></a>
            <?php endif; ?>
            <?php if ($admin): ?>
                <a class="btn btn-block" href="api/export.php?id=<?= $s['id'] ?>"><?= icon('download') ?>Экспорт JSON</a>
                <div class="side-actions">
                    <?php foreach (['approved' => ['check', 'В игру'], 'rejected' => ['x', 'Отклонить'], 'pending' => ['refresh', 'На отбор']] as $to => [$ic, $label]): if ($s['status'] === $to) continue; ?>
                        <form method="post" action="action.php"<?= status_confirm_attrs($to, $s['title']) ?>>
                            <?= csrf_field() ?>
                            <input type="hidden" name="id" value="<?= $s['id'] ?>">
                            <input type="hidden" name="action" value="<?= $to ?>">
                            <input type="hidden" name="back" value="<?= e($back) ?>">
                            <button class="btn btn-sm btn-block act-<?= $to ?>" type="submit"><?= icon($ic) ?><?= e($label) ?></button>
                        </form>
                    <?php endforeach; ?>
                    <form method="post" action="action.php" data-confirm="Ситуация «<?= e($s['title']) ?>» и все голоса по ней будут удалены навсегда. Это действие нельзя отменить." data-confirm-title="Удалить ситуацию?" data-confirm-ok="Удалить навсегда" data-confirm-tone="danger">
                        <?= csrf_field() ?>
                        <input type="hidden" name="id" value="<?= $s['id'] ?>">
                        <input type="hidden" name="action" value="delete">
                        <button class="btn btn-sm btn-block btn-danger" type="submit"><?= icon('trash') ?>Удалить</button>
                    </form>
                </div>
            <?php elseif (!is_logged_in()): ?>
                <p class="muted small">Одобрять и экспортировать ситуации может команда. <a href="login.php?back=<?= e(urlencode($back)) ?>">Войти</a></p>
            <?php elseif (owns_situation($s) && $s['status'] === 'draft'): ?>
                <p class="muted small">Это ваш черновик — его видите только вы. Допишите и отправьте на отбор, когда будете готовы.</p>
                <form method="post" action="action.php" data-confirm="Черновик «<?= e($s['title']) ?>» будет удалён навсегда." data-confirm-title="Удалить черновик?" data-confirm-ok="Удалить" data-confirm-tone="danger">
                    <?= csrf_field() ?>
                    <input type="hidden" name="id" value="<?= $s['id'] ?>">
                    <input type="hidden" name="action" value="delete">
                    <button class="btn btn-sm btn-block btn-danger" type="submit"><?= icon('trash') ?>Удалить черновик</button>
                </form>
            <?php elseif (owns_situation($s)): ?>
                <p class="muted small"><?= $s['status'] === 'pending' ? 'Это ваша ситуация. Пока она на отборе, её можно редактировать.' : 'Это ваша ситуация. Она уже прошла отбор — изменения вносит команда.' ?></p>
            <?php endif; ?>
        </div>

        <div class="panel side-card">
            <span class="label-mono">Статистика</span>
            <div class="side-stats">
                <div><b><?= $total ?></b><span><?= plural($total, 'вердикт', 'вердикта', 'вердиктов') ?></span></div>
                <div class="heat heat-<?= e($contro['level']) ?>"><b><?= $contro['value'] === null ? '—' : $contro['value'] . '%' ?></b><span><?= e($contro['label']) ?></span></div>
            </div>
            <?php if (($counts['other'] ?? 0) > 0): ?>
                <p class="muted small"><?= icon('message') ?> Своё решение предложили: <?= (int)$counts['other'] ?></p>
            <?php endif; ?>
            <?php $timing = vote_duration_stats($s['id']); if ($timing['avg_ms'] !== null): ?>
                <p class="muted small" title="От открытия дела до вердикта, по <?= $timing['n'] ?> <?= plural($timing['n'], 'игроку', 'игрокам', 'игрокам') ?>"><?= icon('clock') ?> Среднее время на решение: <?= e(format_duration($timing['avg_ms'])) ?></p>
            <?php endif; ?>
        </div>

        <div class="panel side-card">
            <span class="label-mono">Быстрая проверка · <?= count($s['checklist']) ?>/<?= count(CHECKLIST) ?></span>
            <ul class="check-summary">
                <?php foreach (CHECKLIST as $i => $item): $ok = in_array($i, $s['checklist'], true); ?>
                    <li class="<?= $ok ? 'ok' : 'no' ?>"><?= icon($ok ? 'check' : 'x') ?><?= e($item) ?></li>
                <?php endforeach; ?>
            </ul>
        </div>
    </aside>
</div>

<?php page_footer(); ?>
