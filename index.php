<?php
require __DIR__ . '/includes/bootstrap.php';

$stats = stats_overview();
$approved = situations_list(['status' => 'approved', 'order' => 'old']);
$counts = vote_counts();

$byCategory = array_fill_keys(array_keys(CATEGORIES), 0);
foreach ($approved as $s) {
    if (isset($byCategory[$s['category']])) {
        $byCategory[$s['category']]++;
    }
}

// Самое спорное дело: максимальный индекс спорности, при равенстве — больше голосов.
$featured = null;
$featuredScore = [-1, -1];
foreach ($approved as $s) {
    $c = $counts[$s['id']] ?? [];
    $score = [controversy($c, max(2, count($s['decisions'])))['value'] ?? -1, array_sum($c)];
    if ($score > $featuredScore) {
        $featured = $s;
        $featuredScore = $score;
    }
}
$featuredContro = $featured ? controversy($counts[$featured['id']] ?? [], max(2, count($featured['decisions']))) : null;

page_header('', 'home', 'page-home', 'high');
?>

<section class="hero">
    <div class="container hero-grid">
        <div class="hero-copy">
            <span class="kicker reveal">Симулятор решений и суждений · MVP</span>
            <h1 class="hero-title reveal">
                Нет правильного ответа.<br>
                Есть только твой <span class="glitch grad-text" data-text="вердикт">вердикт</span>.
            </h1>
            <p class="lead reveal">Вымышленные миры, спорные поступки и свидетели, которые могут лгать. Оцени обстоятельства, прими решение — и столкнись с его последствиями.</p>

            <div class="terminal reveal" aria-hidden="true">
                <span class="t-dot"></span><span class="t-dot"></span><span class="t-dot"></span>
                <code><span class="t-prompt">&gt;</span> обвиняемый признан: <span class="t-word" data-words='["ВИНОВЕН","ОПРАВДАН","ПРОЩЁН","ИЗГНАН","ЧАСТИЧНО ОТВЕТСТВЕНЕН","???"]'>ВИНОВЕН</span><span class="t-caret"></span></code>
            </div>

            <div class="hero-actions reveal">
                <a class="btn btn-primary btn-lg" href="quick.php"><?= icon('play') ?>Начать игру</a>
                <a class="btn btn-lg" href="create.php"><?= icon('edit') ?>Стать автором</a>
            </div>

            <div class="stats reveal">
                <div class="stat"><b data-count="<?= $stats['approved'] ?>"><?= $stats['approved'] ?></b><span>дел в игре</span></div>
                <div class="stat"><b data-count="<?= count(CATEGORIES) ?>"><?= count(CATEGORIES) ?></b><span>категорий</span></div>
                <div class="stat"><b data-count="<?= count(WORLDS) ?>"><?= count(WORLDS) ?></b><span>типов миров</span></div>
                <div class="stat"><b data-count="<?= $stats['votes'] ?>"><?= $stats['votes'] ?></b><span>вердиктов</span></div>
            </div>
        </div>

        <div class="hero-visual reveal" aria-hidden="true">
            <div class="core">
                <div class="core-halo"></div>
                <div class="ring ring-1"></div>
                <div class="ring ring-2"></div>
                <div class="ring ring-3"></div>
                <svg class="ring-ticks" viewBox="0 0 100 100"><circle cx="50" cy="50" r="47"/></svg>
                <svg class="ring-arc" viewBox="0 0 100 100"><circle cx="50" cy="50" r="41"/></svg>
                <div class="ring ring-core"></div>
                <div class="core-icon"><?= icon('scale') ?></div>
                <span class="orbit-tag t1">ВИНОВЕН</span>
                <span class="orbit-tag t2">ОПРАВДАН</span>
                <span class="orbit-tag t3">ИЗГНАН</span>
                <span class="orbit-tag t4">ПРОЩЁН</span>
                <span class="orbit-tag t5">КОМПЕНСАЦИЯ</span>
                <span class="core-readout r1">ДОВЕРИЕ <b>+12</b></span>
                <span class="core-readout r2">АВТОРИТЕТ <b class="neg">−8</b></span>
            </div>
        </div>
    </div>
    <a class="scroll-cue" href="#how" aria-label="Листать вниз"><span></span></a>
</section>

<section class="section" id="how">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">01 // Как это работает</span>
            <h2>Четыре шага до приговора</h2>
            <p class="lead">Хорошее дело заставляет остановиться и подумать. Здесь сложно сразу понять, кто прав, кто виноват и какое решение верное.</p>
        </div>
        <div class="steps">
            <?php
            $steps = [
                ['globe', 'Изучи мир', 'Постапокалипсис, древнее царство или космическая колония: законы каждого мира меняют цену решения.'],
                ['search', 'Взвесь улики', 'Отдели факты от догадок. Свидетели могут ошибаться, лгать или преследовать свой интерес.'],
                ['gavel', 'Вынеси вердикт', 'Виновен, оправдан, изгнан, прощён — или собственное обоснованное решение.'],
                ['activity', 'Живи с последствиями', 'Репутация, авторитет, ресурсы и доверие меняются. Мир помнит твои решения.'],
            ];
            foreach ($steps as $i => [$ic, $title, $text]): ?>
                <div class="card step reveal" style="--delay: <?= $i * 80 ?>ms">
                    <span class="step-num">0<?= $i + 1 ?></span>
                    <span class="step-icon"><?= icon($ic) ?></span>
                    <h3><?= e($title) ?></h3>
                    <p><?= e($text) ?></p>
                </div>
            <?php endforeach; ?>
        </div>
    </div>
</section>

<section class="section">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">02 // Форматы дел</span>
            <h2>Наедине с собой — или на глазах у толпы</h2>
        </div>
        <div class="types">
            <?php $tIndex = 0; foreach (SITUATION_TYPES as $key => $t): ?>
                <div class="card type-card reveal type-<?= e($key) ?>" style="--delay: <?= $tIndex++ * 90 ?>ms">
                    <div class="type-visual" aria-hidden="true">
                        <?php $dots = ['private' => 1, 'witness' => 4, 'public' => 14][$key]; ?>
                        <?php for ($i = 0; $i < $dots; $i++): ?><i style="--i: <?= $i ?>"></i><?php endfor; ?>
                    </div>
                    <span class="type-icon"><?= icon($t['icon']) ?></span>
                    <h3><?= e($t['name']) ?></h3>
                    <p><?= e($t['desc']) ?></p>
                </div>
            <?php endforeach; ?>
        </div>
    </div>
</section>

<section class="section" id="categories">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">03 // Категории</span>
            <h2>Десять арен для твоей совести</h2>
        </div>
        <div class="cat-grid">
            <?php $ci = 0; foreach (CATEGORIES as $key => $c): $n = $byCategory[$key]; ?>
                <a class="card cat-card interactive reveal" href="play.php?category=<?= e($key) ?>" style="<?= e(category_style($key)) ?>; --delay: <?= ($ci++ % 5) * 60 ?>ms">
                    <span class="cat-icon"><?= icon($c['icon']) ?></span>
                    <h3><?= e($c['name']) ?></h3>
                    <p><?= e($c['desc']) ?></p>
                    <span class="cat-count"><?= $n ? $n . ' ' . plural($n, 'дело', 'дела', 'дел') : 'Скоро' ?></span>
                </a>
            <?php endforeach; ?>
        </div>
    </div>
</section>

<section class="section section-tight">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">04 // Миры</span>
            <h2>Полностью вымышленные миры</h2>
            <p class="lead">Ни одной реальной страны, современной политики или действующих законов. Решение зависит от обстоятельств конкретного мира.</p>
        </div>
    </div>
    <div class="marquee reveal" aria-label="Сеттинги">
        <div class="marquee-track">
            <?php for ($k = 0; $k < 2; $k++): foreach (WORLDS as $w): ?>
                <span class="world-chip"<?= $k ? ' aria-hidden="true"' : '' ?>><?= icon($w['icon']) ?><?= e($w['name']) ?></span>
            <?php endforeach; endfor; ?>
        </div>
    </div>
</section>

<?php if ($featured): $fc = CATEGORIES[$featured['category']] ?? null; ?>
<section class="section">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">05 // <?= $featuredContro['value'] !== null ? 'Самое спорное дело' : 'Дело дня' ?></span>
            <h2>Игроки не могут договориться</h2>
        </div>
        <article class="panel featured reveal hud" style="<?= e(category_style($featured['category'])) ?>">
            <div class="featured-main">
                <div class="featured-meta">
                    <span class="case-no"><?= e(case_number($featured['id'])) ?></span>
                    <span class="chip chip-cat"><?= icon($fc['icon'] ?? 'circle') ?><?= e($fc['name'] ?? '') ?></span>
                    <span class="chip"><?= icon(SITUATION_TYPES[$featured['type']]['icon'] ?? 'circle') ?><?= e(SITUATION_TYPES[$featured['type']]['name'] ?? '') ?></span>
                </div>
                <h3 class="featured-title"><?= e($featured['title']) ?></h3>
                <p class="featured-setting"><?= icon('map-pin') ?><?= e($featured['world']['place']) ?> · <?= e($featured['world']['era']) ?></p>
                <p class="featured-teaser"><?= e(excerpt($featured['story'], 320)) ?></p>
                <?php if ($featured['ambiguity']['conflict'] !== ''): ?>
                    <p class="featured-conflict"><?= icon('swords') ?><?= e($featured['ambiguity']['conflict']) ?></p>
                <?php endif; ?>
                <a class="btn btn-primary" href="case.php?id=<?= $featured['id'] ?>">Открыть дело<?= icon('arrow-right') ?></a>
            </div>
            <div class="featured-side">
                <div class="featured-heat">
                    <span class="label-mono">Индекс спорности</span>
                    <b><?= $featuredContro['value'] === null ? '—' : $featuredContro['value'] . '%' ?></b>
                    <span><?= e($featuredContro['label']) ?></span>
                </div>
                <ul class="featured-options">
                    <?php foreach (array_slice($featured['decisions'], 0, 4) as $d): ?>
                        <li><span class="opt-letter opt-letter-sm"><?= e($d['key']) ?></span><?= e(excerpt($d['text'], 60)) ?></li>
                    <?php endforeach; ?>
                    <?php if (count($featured['decisions']) > 4): ?><li class="more">+ ещё <?= count($featured['decisions']) - 4 ?> и «своё решение»</li><?php endif; ?>
                </ul>
            </div>
        </article>
    </div>
</section>
<?php endif; ?>

<section class="section">
    <div class="container">
        <div class="section-head reveal">
            <span class="kicker">06 // Путь проекта</span>
            <h2>Мы в самом начале</h2>
            <p class="lead">Free-to-play с рекламой и premium-функциями. Сейчас формируем первый массив игрового контента для MVP.</p>
        </div>
        <ol class="roadmap reveal">
            <?php foreach (ROADMAP as $i => $step): ?>
                <li class="<?= $i === 0 ? 'now' : '' ?>">
                    <span class="road-dot"></span>
                    <span class="road-step">Этап 0<?= $i + 1 ?></span>
                    <b><?= e($step) ?></b>
                    <?php if ($i === 0): ?><span class="road-now">Вы здесь</span><?php endif; ?>
                </li>
            <?php endforeach; ?>
        </ol>
    </div>
</section>

<section class="section">
    <div class="container">
        <div class="cta panel reveal">
            <div class="cta-copy">
                <span class="kicker">Для авторов контента</span>
                <h2>Создай дело, о котором будут спорить</h2>
                <p class="lead">Если после прохождения два игрока начинают спорить — «Я бы его оправдал» / «Нет, он был угрозой для всех» — это лучший результат. Участие в долгосрочной программе вознаграждения авторов.</p>
                <div class="hero-actions">
                    <a class="btn btn-primary btn-lg" href="create.php"><?= icon('edit') ?>Создать ситуацию</a>
                    <a class="btn btn-lg" href="brief.php"><?= icon('file') ?>Прочитать бриф</a>
                </div>
            </div>
            <div class="cta-quotes" aria-hidden="true">
                <div class="bubble bubble-a">«Я бы его оправдал».</div>
                <div class="bubble bubble-b">«Нет, он представлял угрозу для всех».</div>
                <div class="bubble bubble-c">«По закону он виновен, но если учитывать обстоятельства…»</div>
            </div>
        </div>
    </div>
</section>

<?php page_footer(); ?>
