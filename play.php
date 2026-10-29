<?php
require __DIR__ . '/includes/bootstrap.php';

$situations = situations_list(['status' => 'approved', 'order' => 'old']);
$counts = vote_counts();
$mine = votes_of_voter(voter_id());

$presentCats = [];
$open = [];
foreach ($situations as $s) {
    $presentCats[$s['category']] = true;
    if (!isset($mine[$s['id']])) {
        $open[] = $s;
    }
}
$done = count($situations) - count($open);
$random = $open ? $open[array_rand($open)] : null;
$initialCat = isset($_GET['category'], CATEGORIES[$_GET['category']]) ? (string)$_GET['category'] : '';

page_header('Архив дел', 'play', 'page-play', 'high');
?>

<section class="page-hero">
    <div class="container page-hero-grid">
        <div>
            <span class="kicker reveal">Архив дел</span>
            <h1 class="reveal">Выбери дело. <span class="grad-text">Вынеси вердикт.</span></h1>
            <p class="lead reveal">Каждое дело — спорная ситуация в вымышленном мире. Здесь нет подсказок и нет правильного ответа: только факты, сомнения и ваше решение.</p>
            <div class="progress-line reveal">
                <div class="progress-info">
                    <span>Рассмотрено дел</span>
                    <b><?= $done ?> / <?= count($situations) ?></b>
                </div>
                <div class="progress-bar"><i style="width: <?= count($situations) ? round($done / count($situations) * 100) : 0 ?>%"></i></div>
            </div>
            <div class="hero-actions reveal">
                <?php if ($random): ?>
                    <a class="btn btn-primary" href="quick.php"><?= icon('zap') ?>Быстрый суд</a>
                    <a class="btn" href="case.php?id=<?= $random['id'] ?>"><?= icon('dice') ?>Случайное дело</a>
                <?php endif; ?>
                <a class="btn" href="judge.php"><?= icon('user') ?>Профиль судьи</a>
                <a class="btn" href="create.php"><?= icon('plus') ?>Предложить своё дело</a>
            </div>
        </div>
        <aside class="reveal"><?= partial('world', ['back' => 'play.php']) ?></aside>
    </div>
</section>

<section class="section section-top-0">
    <div class="container">
        <?php if (!$situations): ?>
            <div class="empty panel">
                <?= icon('archive') ?>
                <h2>Архив пока пуст</h2>
                <p>Ни одно дело ещё не прошло отбор. Создайте первую ситуацию — команда рассмотрит её.</p>
                <a class="btn btn-primary" href="create.php"><?= icon('edit') ?>Создать ситуацию</a>
            </div>
        <?php else: ?>
            <div class="filters panel" data-filters>
                <div class="filter-group" role="group" aria-label="Категория">
                    <button type="button" class="filter-chip<?= $initialCat === '' ? ' active' : '' ?>" data-filter-cat="">Все категории</button>
                    <?php foreach (CATEGORIES as $key => $c): if (empty($presentCats[$key])) continue; ?>
                        <button type="button" class="filter-chip<?= $initialCat === $key ? ' active' : '' ?>" data-filter-cat="<?= e($key) ?>" style="<?= e(category_style($key)) ?>"><?= icon($c['icon']) ?><?= e($c['name']) ?></button>
                    <?php endforeach; ?>
                </div>
                <div class="filters-row">
                    <div class="segmented" role="group" aria-label="Тип ситуации">
                        <button type="button" class="active" data-filter-type="">Все</button>
                        <?php foreach (SITUATION_TYPES as $key => $t): ?>
                            <button type="button" data-filter-type="<?= e($key) ?>"><?= icon($t['icon']) ?><?= e($t['name']) ?></button>
                        <?php endforeach; ?>
                    </div>
                    <select class="vs" aria-label="Порядок дел" data-sort-select data-align="right">
                        <option value="order"<?= option_icon('archive') ?> data-desc="Как в архиве">По номеру дела</option>
                        <option value="open"<?= option_icon('target') ?> data-desc="Нерешённые — наверху">Сначала нерешённые</option>
                        <option value="heat"<?= option_icon('flame', 320) ?> data-desc="Где мнения расходятся сильнее">Самые спорные</option>
                        <option value="votes"<?= option_icon('gavel') ?> data-desc="Больше всего вердиктов">Популярные</option>
                    </select>
                </div>
            </div>

            <div class="case-grid" data-case-grid data-initial-cat="<?= e($initialCat) ?>">
                <?php foreach ($situations as $s): ?>
                    <?= partial('case-card', ['s' => $s, 'counts' => $counts[$s['id']] ?? [], 'myKey' => $mine[$s['id']] ?? null]) ?>
                <?php endforeach; ?>
            </div>
            <div class="empty panel" data-empty hidden>
                <?= icon('search') ?>
                <h2>Таких дел пока нет</h2>
                <p>В этой категории и формате ещё нет одобренных ситуаций. Может, вы напишете первую?</p>
                <a class="btn" href="create.php"><?= icon('edit') ?>Создать ситуацию</a>
            </div>
        <?php endif; ?>
    </div>
</section>

<?php page_footer(['play.js']); ?>
