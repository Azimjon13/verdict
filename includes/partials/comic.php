<?php
defined('APP_ROOT') || exit;

/**
 * Дело в кадрах. Без JS — обычный текст по кадрам; с JS (comic.js) — листаемый комикс с анимацией.
 * @var array  $s       ситуация
 * @var bool   $full    кадры «Кто есть кто», «Улики», «Свидетели», «Ваш вердикт» (быстрый суд)
 * @var string $finish  куда перейти после последнего кадра (CSS-селектор)
 * @var string $finishLabel подпись кнопки на последнем кадре
 */
$cast = comic_cast($s);
$panels = comic_panels($s, $cast, $full);
$uid = 'cm' . (int)($s['id'] ?? 0);
$total = count($panels);
$hue = CATEGORIES[$s['category']]['hue'] ?? 190;

$use = static fn(int $i, string $class = ''): string =>
    '<svg class="' . $class . '" viewBox="0 0 120 140" aria-hidden="true"><use href="#' . $uid . '-' . $i . '"/></svg>';
$name = static fn(int $i): string => '<b class="cm-name" style="--ah:' . $cast[$i]['hue'] . '">' . e($cast[$i]['short']) . '</b>';
$figure = static fn(int $i, int $k): string => '<figure class="cm-fig" data-who="' . $i . '" style="--ah:' . $cast[$i]['hue'] . ';--k:' . $k . '">'
    . $use($i) . '<figcaption>' . e($cast[$i]['short']) . '</figcaption></figure>';
$bubble = static function (?int $who, string $text, string $tag = '', string $note = '') use ($cast, $use, $name): string {
    $av = $who === null ? '<span class="cm-bubble-av cm-voice">' . icon('message') . '</span>' : $use($who, 'cm-bubble-av');
    $label = $who === null ? '<b class="cm-name cm-anon">' . e($tag !== '' ? mb_strtoupper(mb_substr($tag, 0, 1)) . mb_substr($tag, 1) : 'Голос') . '</b>' : $name($who);
    return '<div class="cm-bubble" data-seq' . ($who !== null ? ' data-who="' . $who . '"' : '') . '>' . $av
        . '<div class="cm-bubble-body">' . $label . '<p>«' . e($text) . '»</p>' . ($note !== '' ? '<small>' . e($note) . '</small>' : '') . '</div></div>';
};
$titles = [
    'world'     => 'Мир',
    'story'     => 'Что произошло',
    'cast'      => 'Кто есть кто',
    'evidence'  => 'Что известно',
    'witnesses' => 'Что говорят свидетели',
    'decide'    => 'Ваш вердикт',
];
?>
<section class="comic" data-comic data-finish="<?= e($finish ?? '') ?>" data-finish-label="<?= e($finishLabel ?? 'Дальше') ?>"
         style="--h: <?= (int)$hue ?>" aria-label="Дело в кадрах: <?= e($s['title']) ?>">
    <svg class="cm-sprite" aria-hidden="true" focusable="false">
        <?php foreach ($cast as $i => $c): ?>
            <symbol id="<?= $uid ?>-<?= $i ?>" viewBox="0 0 120 140"><?= comic_avatar_body($c['avatar']) ?></symbol>
        <?php endforeach; ?>
    </svg>

    <div class="cm-top">
        <span class="label-mono"><?= icon('play') ?>Дело в кадрах</span>
        <button type="button" class="link-btn cm-mode" data-cm-mode aria-pressed="false"><?= icon('file') ?><span>Читать текстом</span></button>
    </div>

    <div class="cm-viewport" data-cm-viewport>
        <div class="cm-scene" data-cm-scene aria-hidden="true">
            <svg viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice"><?= comic_scene((string)$s['world']['setting'], (int)$hue) ?></svg>
        </div>
        <div class="cm-shade" aria-hidden="true"></div>
        <?php foreach ($panels as $k => $p): ?>
            <div class="cm-figures cm-figures-<?= $p['kind'] ?>" data-cm-figures="<?= $k ?>" aria-hidden="true"<?= $k ? ' hidden' : '' ?>>
                <?php if ($p['kind'] === 'world'): ?>
                    <div class="cm-titlecard">
                        <span class="cm-case-no"><?= e($s['world']['setting'] !== '' ? $s['world']['setting'] : (CATEGORIES[$s['category']]['name'] ?? '')) ?></span>
                        <strong><?= e($s['title']) ?></strong>
                        <span><?= icon('map-pin') ?><?= e($p['place']) ?></span>
                    </div>
                <?php elseif ($p['kind'] === 'evidence'): ?>
                    <div class="cm-board"><span class="cm-pin ok"><?= icon('check-circle') ?><?= count($p['facts']) ?></span><span class="cm-pin q"><?= icon('help') ?><?= count($p['unknowns']) ?></span></div>
                <?php elseif ($p['kind'] === 'decide'): ?>
                    <div class="cm-gavel"><?= icon('gavel') ?></div>
                <?php else: ?>
                    <?php foreach ($p['present'] as $n => $i): ?><?= $figure($i, $n) ?><?php endforeach; ?>
                <?php endif; ?>
            </div>
        <?php endforeach; ?>
        <div class="cm-hud">
            <span class="cm-count" data-cm-count>1 / <?= $total ?></span>
            <button type="button" class="cm-skip" data-cm-skip><?= e($finishLabel ?? 'Пропустить') ?><?= icon('arrow-right') ?></button>
        </div>
    </div>

    <ol class="cm-panels">
        <?php foreach ($panels as $k => $p): ?>
            <li class="cm-panel cm-<?= $p['kind'] ?>" data-cm-panel="<?= $k ?>" data-cam="<?= comic_camera($k) ?>">
                <h3 class="cm-panel-h"><?= e($titles[$p['kind']]) ?></h3>
                <?php if ($p['kind'] === 'world'): ?>
                    <?php if ($p['role'] !== ''): ?>
                        <p class="cm-role" data-seq><?= icon('user') ?><span>Ваша роль: <b><?= e($p['role']) ?></b></span></p>
                    <?php endif; ?>
                    <p class="cm-place" data-seq><?= icon('globe') ?><span><?= e($p['place']) ?><?= $p['era'] !== '' ? ' · ' . e($p['era']) : '' ?></span></p>
                    <p class="cm-caption" data-seq><?= comic_highlight($p['text'], $cast) ?></p>

                <?php elseif ($p['kind'] === 'story'): ?>
                    <?php foreach ($p['segments'] as $seg): ?>
                        <?php if ($seg['type'] === 'caption'): ?>
                            <p class="cm-caption" data-seq><?= comic_highlight($seg['text'], $cast) ?></p>
                        <?php else: ?>
                            <?= $bubble($seg['who'], $seg['text'], $seg['tag']) ?>
                        <?php endif; ?>
                    <?php endforeach; ?>

                <?php elseif ($p['kind'] === 'cast'): ?>
                    <div class="cm-cards">
                        <?php foreach ($p['people'] as $i): $c = $cast[$i]; ?>
                            <div class="cm-card" data-seq data-who="<?= $i ?>" style="--ah: <?= $c['hue'] ?>">
                                <?= $use($i, 'cm-card-av') ?>
                                <div>
                                    <b><?= e($c['short']) ?><?php if ($c['age'] !== ''): ?> <small><?= e($c['age']) ?></small><?php endif; ?></b>
                                    <?php if ($c['role'] !== ''): ?><span class="cm-card-role"><?= e($c['role']) ?></span><?php endif; ?>
                                    <?php if ($c['relations'] !== ''): ?><span class="cm-card-rel"><?= icon('link') ?><?= comic_highlight($c['relations'], $cast) ?></span><?php endif; ?>
                                </div>
                            </div>
                        <?php endforeach; ?>
                    </div>

                <?php elseif ($p['kind'] === 'evidence'): ?>
                    <div class="cm-evidence">
                        <?php foreach ($p['facts'] as $f): ?>
                            <div class="cm-ev ok" data-seq><?= icon('check-circle') ?><span><?= comic_highlight($f, $cast) ?></span></div>
                        <?php endforeach; ?>
                        <?php foreach ($p['unknowns'] as $u): ?>
                            <div class="cm-ev q" data-seq><?= icon('help') ?><span><?= comic_highlight($u, $cast) ?></span></div>
                        <?php endforeach; ?>
                    </div>
                    <p class="cm-legend"><span class="ok"><?= icon('check-circle') ?>известно точно</span><span class="q"><?= icon('help') ?>под сомнением</span></p>

                <?php elseif ($p['kind'] === 'witnesses'): ?>
                    <p class="cm-caption cm-warn" data-seq><?= icon('alert') ?>Свидетели могут ошибаться, лгать или иметь свой интерес.</p>
                    <?php foreach ($p['people'] as $i): ?>
                        <?= $bubble($i, $cast[$i]['claim'], '', $cast[$i]['trust'] !== '' ? 'Надёжность: ' . $cast[$i]['trust'] : '') ?>
                    <?php endforeach; ?>

                <?php else: /* decide */ ?>
                    <p class="cm-caption cm-final" data-seq>Вы знаете всё, что знают остальные. Правильного ответа нет — есть ваш вердикт.</p>
                    <button type="button" class="btn btn-primary cm-finish" data-seq data-cm-finish><?= icon('gavel') ?>Вынести вердикт</button>
                <?php endif; ?>
            </li>
        <?php endforeach; ?>
    </ol>

    <div class="cm-nav">
        <button type="button" class="btn btn-ghost cm-prev" data-cm-prev aria-label="Предыдущий кадр"><?= icon('arrow-left') ?></button>
        <div class="cm-dots" role="tablist" aria-label="Кадры">
            <?php foreach ($panels as $k => $p): ?>
                <button type="button" class="cm-dot" data-cm-dot="<?= $k ?>" aria-label="Кадр <?= $k + 1 ?>: <?= e($titles[$p['kind']]) ?>"></button>
            <?php endforeach; ?>
        </div>
        <button type="button" class="btn btn-primary cm-next" data-cm-next><span data-cm-next-label>Дальше</span><?= icon('arrow-right') ?></button>
    </div>
    <p class="cm-hint"><?= icon('info') ?>Листайте кадры кнопкой «Дальше», стрелками ← → или свайпом. Нажмите на кадр, чтобы показать весь текст сразу.</p>
</section>
