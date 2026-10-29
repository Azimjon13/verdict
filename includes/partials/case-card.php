<?php
defined('APP_ROOT') || exit;

/** @var array $s @var array $counts @var ?string $myKey */
$cat = CATEGORIES[$s['category']] ?? null;
$type = SITUATION_TYPES[$s['type']] ?? null;
$total = array_sum($counts);
$c = controversy($counts, max(2, count($s['decisions'])));
?>
<a class="card case-card interactive" href="case.php?id=<?= $s['id'] ?>"
   data-cat="<?= e($s['category']) ?>" data-type="<?= e($s['type']) ?>" data-id="<?= $s['id'] ?>"
   data-votes="<?= $total ?>" data-heat="<?= (int)($c['value'] ?? -1) ?>" data-done="<?= empty($myKey) ? 0 : 1 ?>"
   style="<?= e(category_style($s['category'])) ?>">
    <div class="case-card-top">
        <span class="case-no"><?= e(case_number($s['id'])) ?></span>
        <?php if ($type): ?><span class="chip chip-type"><?= icon($type['icon']) ?><?= e($type['name']) ?></span><?php endif; ?>
    </div>
    <div class="case-card-cat"><?= icon($cat['icon'] ?? 'circle') ?><span><?= e($cat['name'] ?? $s['category']) ?></span></div>
    <h3 class="case-card-title"><?= e($s['title']) ?></h3>
    <p class="case-card-setting"><?= icon('map-pin') ?><?= e($s['world']['place']) ?></p>
    <p class="case-card-teaser"><?= e(excerpt($s['story'], 170)) ?></p>
    <div class="case-card-foot">
        <span class="case-stat" title="Вынесено вердиктов"><?= icon('gavel') ?><?= $total ?></span>
        <span class="case-stat heat heat-<?= e($c['level']) ?>" title="Индекс спорности"><?= icon('flame') ?><?= $c['value'] === null ? '—' : $c['value'] . '%' ?></span>
        <?php if (!empty($myKey)): ?>
            <span class="case-done"><?= icon('check') ?>Ваш вердикт: <?= e($myKey === 'other' ? 'своё' : $myKey) ?></span>
        <?php else: ?>
            <span class="case-open">Открыть дело<?= icon('arrow-right') ?></span>
        <?php endif; ?>
    </div>
</a>
