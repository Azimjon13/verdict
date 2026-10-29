<?php
defined('APP_ROOT') || exit;

$metrics = world_metrics();
$verdicts = world_count();
$back = $back ?? 'play.php';
?>
<div class="panel world-panel" data-world>
    <div class="world-head">
        <span class="kicker">Состояние мира</span>
        <span class="world-count mono"><b data-world-count><?= $verdicts ?></b> <span data-world-word><?= plural($verdicts, 'вердикт', 'вердикта', 'вердиктов') ?></span></span>
    </div>
    <?php foreach (METRICS as $key => $m): $v = $metrics[$key]; ?>
        <div class="meter" data-metric="<?= e($key) ?>">
            <div class="meter-top">
                <span class="meter-name"><?= icon($m['icon']) ?><?= e($m['name']) ?></span>
                <span class="meter-delta" data-delta></span>
                <b class="meter-value" data-value><?= $v ?></b>
            </div>
            <div class="meter-bar"><i style="width: <?= $v ?>%"></i><span class="meter-mid"></span></div>
        </div>
    <?php endforeach; ?>
    <p class="world-hint">Каждое решение меняет мир. Последствия накапливаются от дела к делу.</p>
    <?php if ($verdicts > 0): ?>
        <form method="post" action="api/world.php" class="world-reset" data-confirm="Все показатели мира вернутся к исходным 50. Ваши голоса в общей статистике сохранятся." data-confirm-title="Начать мир заново?" data-confirm-ok="Сбросить мир" data-confirm-tone="warn">
            <?= csrf_field() ?>
            <input type="hidden" name="back" value="<?= e($back) ?>">
            <button type="submit" class="link-btn"><?= icon('refresh') ?>Начать мир заново</button>
        </form>
    <?php endif; ?>
</div>
