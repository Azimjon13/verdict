<?php
defined('APP_ROOT') || exit;

/**
 * Полоска о профиле судьи под результатом вердикта.
 * @var array $judge ['profile' => judge_profile(), 'event' => null|'unlocked'|'changed']
 */
$jp = $judge['profile'];
$jtype = $jp['archetype'] !== null ? JUDGE_ARCHETYPES[$jp['archetype']] : null;
$jevent = $judge['event'] ?? null;
?>
<a class="judge-teaser<?= $jevent ? ' is-' . e($jevent) : '' ?><?= $jtype ? '' : ' is-locked' ?>" href="judge.php">
    <span class="jt-icon"><?= icon($jtype ? $jtype['icon'] : 'lock') ?></span>
    <span class="jt-body">
        <?php if ($jtype === null): ?>
            <small>Профиль судьи</small>
            <b>Откроется через <?= $jp['left'] ?> <?= plural($jp['left'], 'вердикт', 'вердикта', 'вердиктов') ?></b>
            <span class="jt-meter" aria-hidden="true"><i style="width: <?= min(100, (int)round($jp['decided'] / JUDGE_MIN_VERDICTS * 100)) ?>%"></i></span>
        <?php elseif ($jevent === 'unlocked'): ?>
            <small>Профиль судьи открыт!</small>
            <b>Вы — «<?= e($jtype['name']) ?>»</b>
        <?php elseif ($jevent === 'changed'): ?>
            <small>Ваш стиль изменился</small>
            <b>Теперь вы — «<?= e($jtype['name']) ?>»</b>
        <?php else: ?>
            <small>Ваш профиль судьи</small>
            <b>«<?= e($jtype['name']) ?>»</b>
        <?php endif; ?>
    </span>
    <?= icon('arrow-right', 'jt-arrow') ?>
</a>
