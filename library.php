<?php
require __DIR__ . '/includes/bootstrap.php';

$uid = current_user_id();
$status = (string)($_GET['status'] ?? 'all');
if ($status !== 'all' && !isset(STATUSES[$status]) && !($status === 'mine' && $uid)) {
    $status = 'all';
}
$category = (string)($_GET['category'] ?? '');
if ($category !== '' && !isset(CATEGORIES[$category])) {
    $category = '';
}

// Черновики видит только их автор (во вкладках «Черновики» и «Мои»).
$all = array_values(array_filter(situations_list(), static fn(array $s): bool =>
    $s['status'] !== 'draft' || ($uid && $s['user_id'] === $uid)));
$counts = vote_counts();
$admin = is_admin();

// Прогресс первого спринта: категории × типы (без черновиков и отклонённых).
$matrix = [];
foreach (array_keys(CATEGORIES) as $c) {
    $matrix[$c] = array_fill_keys(array_keys(SITUATION_TYPES), 0);
}
$tabCounts = ['all' => 0] + array_fill_keys(array_keys(STATUSES), 0) + ['mine' => 0];
foreach ($all as $s) {
    $tabCounts[$s['status']] = ($tabCounts[$s['status']] ?? 0) + 1;
    if ($s['status'] !== 'draft') {
        $tabCounts['all']++;
    }
    if ($uid && $s['user_id'] === $uid) {
        $tabCounts['mine']++;
    }
    if (!in_array($s['status'], ['draft', 'rejected'], true) && isset($matrix[$s['category']][$s['type']])) {
        $matrix[$s['category']][$s['type']]++;
    }
}
$targetPerCategory = array_sum(array_column(SITUATION_TYPES, 'target'));

$list = array_values(array_filter($all, static fn(array $s): bool =>
    (($status === 'all' && $s['status'] !== 'draft') || $s['status'] === $status || ($status === 'mine' && $s['user_id'] === $uid))
    && ($category === '' || $s['category'] === $category)));
$tabs = ['all' => 'Все'] + array_diff_key(STATUSES, ['draft' => true])
    + ($tabCounts['draft'] > 0 ? ['draft' => 'Черновики'] : [])
    + ($uid ? ['mine' => 'Мои'] : []);

// Сортировка списка.
$sorts = [
    'new'   => ['Сначала новые', 'calendar'],
    'old'   => ['Сначала старые', 'clock'],
    'votes' => ['Больше вердиктов', 'gavel'],
    'heat'  => ['Самые спорные', 'flame'],
    'title' => ['По названию, А–Я', 'file'],
];
$sort = (string)($_GET['sort'] ?? 'new');
if (!isset($sorts[$sort])) {
    $sort = 'new';
}
$heat = static fn(array $s): int => controversy($counts[$s['id']] ?? [], max(2, count($s['decisions'])))['value'] ?? -1;
$sorters = [
    'new'   => static fn(array $a, array $b): int => $b['id'] <=> $a['id'],
    'old'   => static fn(array $a, array $b): int => $a['id'] <=> $b['id'],
    'votes' => static fn(array $a, array $b): int => [array_sum($counts[$b['id']] ?? []), $b['id']] <=> [array_sum($counts[$a['id']] ?? []), $a['id']],
    'heat'  => static fn(array $a, array $b): int => [$heat($b), $b['id']] <=> [$heat($a), $a['id']],
    'title' => static fn(array $a, array $b): int => strcmp(mb_strtolower($a['title']), mb_strtolower($b['title'])),
];
usort($list, $sorters[$sort]);

$qs = static fn(array $over): string => 'library.php?' . http_build_query(array_filter(
    array_merge(['status' => $status, 'category' => $category, 'sort' => $sort], $over),
    static fn($v) => $v !== '' && $v !== 'all' && $v !== 'new'
));
$back = $qs([]);

page_header('Отбор контента', 'library', 'page-library', 'calm');
?>

<section class="page-hero page-hero-compact">
    <div class="container page-hero-split">
        <div>
            <span class="kicker">Отбор контента</span>
            <h1>Все ситуации <span class="grad-text">проходят отбор</span></h1>
            <p class="lead">Самые интересные попадут в MVP и будут протестированы на реальных игроках: вовлечённость, completion rate, retention, расхождение мнений и потенциал для обсуждений.</p>
        </div>
        <div class="hero-actions">
            <a class="btn btn-primary" href="create.php"><?= icon('plus') ?>Новая ситуация</a>
            <?php if ($admin): ?>
                <a class="btn" href="api/export.php"><?= icon('download') ?>Экспорт одобренных (JSON)</a>
            <?php else: ?>
                <a class="btn" href="login.php?back=library.php"><?= icon('login') ?>Войти</a>
            <?php endif; ?>
        </div>
    </div>
</section>

<section class="container">
    <details class="panel sprint" open>
        <summary>
            <span class="sprint-title"><?= icon('hourglass') ?>Первый спринт · 7 дней</span>
            <span class="sprint-sub">Цель на категорию: <?= $targetPerCategory ?> ситуаций — <?= e(implode(', ', array_map(static fn(array $t): string => $t['target'] . ' ' . $t['many'], SITUATION_TYPES))) ?></span>
            <?= icon('chevron-down', 'chev') ?>
        </summary>
        <div class="sprint-table" role="table" aria-label="Прогресс спринта">
            <div class="sprint-row sprint-head" role="row">
                <span role="columnheader">Категория</span>
                <?php foreach (SITUATION_TYPES as $t): ?><span role="columnheader"><?= icon($t['icon']) ?><?= e($t['name']) ?></span><?php endforeach; ?>
                <span role="columnheader">Итого</span>
            </div>
            <?php foreach (CATEGORIES as $key => $c): $sum = array_sum($matrix[$key]); ?>
                <div class="sprint-row" role="row" style="<?= e(category_style($key)) ?>">
                    <span class="sprint-cat" role="cell"><?= icon($c['icon']) ?><?= e($c['name']) ?></span>
                    <?php foreach (SITUATION_TYPES as $tk => $t): $v = $matrix[$key][$tk]; ?>
                        <span class="sprint-cell" role="cell">
                            <span class="mini-bar"><i style="width: <?= min(100, round($v / $t['target'] * 100)) ?>%"></i></span>
                            <b><?= $v ?></b>/<?= $t['target'] ?>
                        </span>
                    <?php endforeach; ?>
                    <span class="sprint-cell sprint-total" role="cell"><b><?= $sum ?></b>/<?= $targetPerCategory ?></span>
                </div>
            <?php endforeach; ?>
        </div>
    </details>
</section>

<section class="section section-top-sm">
    <div class="container">
        <div class="lib-toolbar">
            <div class="tabs" role="tablist" aria-label="Статус">
                <?php foreach ($tabs as $key => $label): ?>
                    <a role="tab" href="<?= e($qs(['status' => $key])) ?>" class="tab<?= $status === $key ? ' active' : '' ?>" aria-selected="<?= $status === $key ? 'true' : 'false' ?>">
                        <?= e($label) ?> <span class="tab-count"><?= $tabCounts[$key] ?? 0 ?></span>
                    </a>
                <?php endforeach; ?>
            </div>
            <form method="get" class="lib-filter">
                <?php if ($status !== 'all'): ?><input type="hidden" name="status" value="<?= e($status) ?>"><?php endif; ?>
                <select class="vs" name="category" aria-label="Категория" data-autosubmit>
                    <option value=""<?= option_icon('layers') ?>>Все категории</option>
                    <?php foreach (CATEGORIES as $key => $c): ?>
                        <option value="<?= e($key) ?>"<?= option_icon($c['icon'], $c['hue']) ?><?= $category === $key ? ' selected' : '' ?>><?= e($c['name']) ?></option>
                    <?php endforeach; ?>
                </select>
                <select class="vs" name="sort" aria-label="Сортировка" data-autosubmit data-align="right">
                    <?php foreach ($sorts as $key => [$label, $ic]): ?>
                        <option value="<?= $key ?>"<?= option_icon($ic) ?><?= $sort === $key ? ' selected' : '' ?>><?= e($label) ?></option>
                    <?php endforeach; ?>
                </select>
                <noscript><button class="btn btn-sm">Показать</button></noscript>
            </form>
        </div>

        <?php if (!$list): ?>
            <div class="empty panel">
                <?= icon('archive') ?>
                <h2>Здесь пока пусто</h2>
                <p>Нет ситуаций с выбранными фильтрами.</p>
                <a class="btn btn-primary" href="create.php"><?= icon('plus') ?>Создать ситуацию</a>
            </div>
        <?php else: ?>
            <div class="lib-list">
                <?php foreach ($list as $s):
                    $cat = CATEGORIES[$s['category']] ?? ['name' => $s['category'], 'icon' => 'circle'];
                    $type = SITUATION_TYPES[$s['type']] ?? ['name' => $s['type'], 'icon' => 'circle'];
                    $c = $counts[$s['id']] ?? [];
                    $contro = controversy($c, max(2, count($s['decisions'])));
                ?>
                    <article class="panel lib-row" style="<?= e(category_style($s['category'])) ?>">
                        <div class="lib-main">
                            <div class="lib-meta">
                                <span class="case-no"><?= e(case_number($s['id'])) ?></span>
                                <span class="status status-<?= e($s['status']) ?>"><?= e(STATUSES[$s['status']] ?? $s['status']) ?></span>
                                <?php if ($uid && $s['user_id'] === $uid): ?><span class="chip chip-sm chip-mine"><?= icon('user') ?>Ваша</span><?php endif; ?>
                                <span class="chip chip-cat chip-sm"><?= icon($cat['icon']) ?><?= e($cat['name']) ?></span>
                                <span class="chip chip-sm"><?= icon($type['icon']) ?><?= e($type['name']) ?></span>
                                <?= level_chip(situation_level($s)) ?>
                            </div>
                            <h3><a href="<?= $s['status'] === 'draft' ? 'create.php?edit=' : 'view.php?id=' ?><?= $s['id'] ?>"><?= e($s['title']) ?></a></h3>
                            <p class="lib-sub"><?= icon('user') ?><?= e($s['author'] ?: 'Без автора') ?><span class="sep">·</span><?= icon('calendar') ?><?= e(format_date($s['created_at'])) ?><span class="sep">·</span><?= count($s['decisions']) ?> <?= plural(count($s['decisions']), 'решение', 'решения', 'решений') ?></p>
                        </div>
                        <div class="lib-stats">
                            <span title="Вердиктов"><?= icon('gavel') ?><?= array_sum($c) ?></span>
                            <span class="heat heat-<?= e($contro['level']) ?>" title="Индекс спорности"><?= icon('flame') ?><?= $contro['value'] === null ? '—' : $contro['value'] . '%' ?></span>
                            <span title="Пункты быстрой проверки"><?= icon('clipboard') ?><?= count($s['checklist']) ?>/<?= count(CHECKLIST) ?></span>
                        </div>
                        <div class="lib-actions">
                            <a class="btn btn-sm" href="view.php?id=<?= $s['id'] ?>"><?= icon('file') ?>Досье</a>
                            <a class="btn btn-sm btn-ghost" href="case.php?id=<?= $s['id'] ?>" title="Пройти как игрок"><?= icon('play') ?></a>
                            <?php if ($admin): ?>
                                <?php foreach (['approved' => ['check', 'В игру'], 'rejected' => ['x', 'Отклонить'], 'pending' => ['refresh', 'На отбор']] as $to => [$ic, $label]): if ($s['status'] === $to) continue; ?>
                                    <form method="post" action="action.php" class="inline-form"<?= status_confirm_attrs($to, $s['title']) ?>>
                                        <?= csrf_field() ?>
                                        <input type="hidden" name="id" value="<?= $s['id'] ?>">
                                        <input type="hidden" name="action" value="<?= $to ?>">
                                        <input type="hidden" name="back" value="<?= e($back) ?>">
                                        <button class="btn btn-sm btn-ghost act-<?= $to ?>" type="submit" title="<?= e($label) ?>"><?= icon($ic) ?><span class="act-label"><?= e($label) ?></span></button>
                                    </form>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </div>
                    </article>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </div>
</section>

<?php page_footer(); ?>
