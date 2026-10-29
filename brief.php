<?php
require __DIR__ . '/includes/bootstrap.php';

// Пример из брифа есть среди демо-дел — дадим ссылку, если оно в игре.
$exampleId = null;
foreach (situations_list(['status' => 'approved', 'order' => 'old']) as $s) {
    if ($s['title'] === 'Три ампулы') {
        $exampleId = $s['id'];
        break;
    }
}

$toc = [
    'about'    => 'О проекте',
    'idea'     => 'Основная идея',
    'formats'  => 'Форматы ситуаций',
    'cats'     => 'Категории',
    'contents' => 'Что содержит ситуация',
    'good'     => 'Хорошая ситуация',
    'example'  => 'Пример',
    'review'   => 'Отбор и метрики',
    'rewards'  => 'Участие и вознаграждение',
    'sprint'   => 'Первый спринт',
];

page_header('Бриф для авторов', 'brief', 'page-brief', 'calm');
?>

<section class="page-hero">
    <div class="container">
        <span class="kicker reveal">Content Creator Brief</span>
        <h1 class="reveal">Бриф для <span class="grad-text">авторов контента</span></h1>
        <p class="lead reveal">Мы разрабатываем мобильную игру в формате симулятора решений и суждений. Игрок оценивает обстоятельства, принимает решение и сталкивается с последствиями своего выбора. Сейчас мы формируем первый массив игрового контента для MVP.</p>
        <div class="hero-actions reveal">
            <a class="btn btn-primary btn-lg" href="create.php"><?= icon('edit') ?>Создать ситуацию</a>
            <a class="btn btn-lg" href="#sprint"><?= icon('hourglass') ?>Первый спринт</a>
        </div>
    </div>
</section>

<div class="container brief-layout">
    <aside class="brief-toc">
        <nav class="panel" aria-label="Содержание брифа">
            <span class="label-mono">Содержание</span>
            <?php $i = 0; foreach ($toc as $anchor => $label): ?>
                <a href="#<?= $anchor ?>" data-nav="<?= $anchor ?>"><span class="nav-num"><?= str_pad((string)++$i, 2, '0', STR_PAD_LEFT) ?></span><?= e($label) ?></a>
            <?php endforeach; ?>
        </nav>
    </aside>

    <div class="brief-body">
        <section class="panel brief-block reveal" id="about" data-section>
            <header class="block-head"><span class="block-num">01</span><h2>О проекте</h2></header>
            <p>Мы разрабатываем мобильную игру в формате <b>симулятора решений и суждений</b>. Основная идея — поставить игрока в различные ситуации, где ему необходимо оценить обстоятельства, принять решение и столкнуться с последствиями своего выбора.</p>
            <p>Проект находится на ранней стадии. Модель игры — <b>free-to-play</b> с рекламой, premium-функциями и другими способами монетизации.</p>
            <ol class="roadmap roadmap-compact">
                <?php foreach (ROADMAP as $i => $step): ?>
                    <li class="<?= $i === 0 ? 'now' : '' ?>"><span class="road-dot"></span><span class="road-step">Этап 0<?= $i + 1 ?></span><b><?= e($step) ?></b></li>
                <?php endforeach; ?>
            </ol>
        </section>

        <section class="panel brief-block reveal" id="idea" data-section>
            <header class="block-head"><span class="block-num">02</span><h2>Основная идея контента</h2></header>
            <blockquote class="big-quote">Игрок должен не просто выбрать правильный ответ. Главная задача ситуации — <span class="grad-text">заставить его думать и сомневаться.</span></blockquote>
            <p>В хорошей ситуации должно быть сложно сразу понять, кто прав, кто виноват и какое решение является правильным. Игрок должен иметь возможность выбрать разные варианты и самостоятельно объяснить для себя, почему он принял именно такое решение.</p>
            <p>Миры игры <b>полностью вымышленные</b>. Они не привязаны к реальным странам, регионам, современной политике или действующим законам. Поэтому решение должно зависеть от обстоятельств конкретного мира.</p>
            <div class="world-grid">
                <?php foreach (WORLDS as $w): ?>
                    <span class="world-chip"><?= icon($w['icon']) ?><?= e($w['name']) ?></span>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="panel brief-block reveal" id="formats" data-section>
            <header class="block-head"><span class="block-num">03</span><h2>Форматы ситуаций</h2></header>
            <div class="types types-compact">
                <?php foreach (SITUATION_TYPES as $key => $t): ?>
                    <div class="card type-card type-<?= e($key) ?>">
                        <span class="type-icon"><?= icon($t['icon']) ?></span>
                        <h3><?= e($t['name']) ?></h3>
                        <p><?= e($t['desc']) ?></p>
                        <span class="type-target"><b><?= $t['target'] ?></b> на категорию в первом спринте</span>
                    </div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="panel brief-block reveal" id="cats" data-section>
            <header class="block-head"><span class="block-num">04</span><h2>Категории</h2></header>
            <p>На первом этапе работаем со следующими категориями:</p>
            <div class="cat-list">
                <?php $i = 0; foreach (CATEGORIES as $key => $c): ?>
                    <div class="cat-line" style="<?= e(category_style($key)) ?>">
                        <span class="cat-icon cat-icon-sm"><?= icon($c['icon']) ?></span>
                        <div><b><?= e($c['name']) ?></b><p><?= e($c['desc']) ?></p></div>
                        <span class="cat-idx"><?= str_pad((string)++$i, 2, '0', STR_PAD_LEFT) ?></span>
                    </div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="panel brief-block reveal" id="contents" data-section>
            <header class="block-head"><span class="block-num">05</span><h2>Что должна содержать каждая ситуация</h2></header>
            <ol class="anatomy">
                <li><b>Мир / сеттинг</b><span>Где происходит ситуация и какие условия существуют в этом мире.</span></li>
                <li><b>Ситуация</b><span>Что произошло. Описание достаточно понятное, чтобы игрок разобрался в конфликте, но не даёт сразу ответ.</span></li>
                <li><b>Участники</b><span>Кто участвует в ситуации и какие между ними отношения.</span></li>
                <li><b>Доказательства / информация</b><span>Что известно игроку. Противоречия, неизвестные факты и сомнительные обстоятельства тоже указываются.</span></li>
                <li><b>Свидетели</b><span>Если предусмотрены — каждый свидетель и его показания. Показания могут противоречить друг другу.</span></li>
                <li><b>Решение / вердикт</b><span>Несколько возможных решений. Варианты ниже — только примеры.</span></li>
                <li><b>Последствия</b><span>Решение не просто завершает ситуацию, а может менять дальнейшее развитие игрового мира.</span></li>
            </ol>
            <div class="two-col">
                <div>
                    <span class="label-mono">Примеры вердиктов</span>
                    <div class="chips">
                        <?php foreach (['невиновен', 'виновен', 'частично ответственен', 'наказание', 'компенсация', 'изгнание', 'заключение', 'прощение', 'казнь', 'предупреждение', 'отсутствие наказания', 'другое обоснованное решение'] as $v): ?>
                            <span class="chip chip-sm"><?= e($v) ?></span>
                        <?php endforeach; ?>
                    </div>
                </div>
                <div>
                    <span class="label-mono">Последствия могут влиять на</span>
                    <div class="chips">
                        <?php foreach (['репутацию', 'отношения', 'авторитет', 'ресурсы', 'стабильность', 'других персонажей', 'будущие события'] as $v): ?>
                            <span class="chip chip-sm chip-accent"><?= e($v) ?></span>
                        <?php endforeach; ?>
                    </div>
                </div>
            </div>
        </section>

        <section class="panel brief-block reveal" id="good" data-section>
            <header class="block-head"><span class="block-num">06</span><h2>Какими должны быть хорошие ситуации</h2></header>
            <div class="rule">
                <span class="label-mono">Самое главное правило</span>
                <p>Не должно быть очевидного правильного ответа.</p>
            </div>
            <p>Хорошая ситуация должна заставлять игрока остановиться и подумать. Например:</p>
            <div class="thoughts">
                <blockquote>«Я понимаю, почему он так поступил, но всё равно считаю, что он должен понести наказание».</blockquote>
                <blockquote>«По закону он виновен, но если учитывать обстоятельства, я бы его оправдал».</blockquote>
            </div>
            <p>Особенно ценны ситуации, в которых игроки будут сильно расходиться во мнениях. Если после прохождения два игрока начинают спорить — это хороший результат для такого типа игры:</p>
            <div class="chat">
                <div class="bubble bubble-a">«Я бы его оправдал».</div>
                <div class="bubble bubble-b">«Нет, он представлял угрозу для всех».</div>
            </div>
        </section>

        <section class="panel brief-block reveal" id="example" data-section>
            <header class="block-head"><span class="block-num">07</span><h2>Пример</h2><span class="chip chip-sm"><?= icon('flame') ?>Поселение после апокалипсиса</span></header>
            <p class="example-story">Мужчина тайно забирает лекарства из центрального хранилища и отдаёт их своей больной дочери. При этом лекарства были зарезервированы для охраны поселения, поскольку на следующий день ожидается нападение. Игрок должен решить, как оценить его поступок.</p>
            <ul class="example-options">
                <?php foreach ([
                    'A' => 'Виновен — наказать за кражу.',
                    'B' => 'Оправдан — он действовал из необходимости.',
                    'C' => 'Частично ответственен — понять его мотив, но привлечь к ответственности.',
                    'D' => 'Угроза обществу — его действия могли поставить поселение под угрозу.',
                    'E' => 'Простить — не наказывать с учётом обстоятельств.',
                    'F' => 'Компенсация — обязать вернуть или заменить лекарства.',
                    'G' => 'Изгнание — его действия создали серьёзную угрозу.',
                    'H' => 'Другое обоснованное решение.',
                ] as $k => $v): ?>
                    <li><span class="opt-letter opt-letter-sm"><?= $k ?></span><?= e($v) ?></li>
                <?php endforeach; ?>
            </ul>
            <p><b>После выбора должны наступать последствия.</b></p>
            <div class="conseq-grid">
                <div class="conseq-tile"><span class="conseq-label"><?= icon('heart') ?>Простил</span><p>Часть жителей может посчитать решение несправедливым.</p></div>
                <div class="conseq-tile"><span class="conseq-label"><?= icon('gavel') ?>Наказал</span><p>Семья может потерять доверие к власти.</p></div>
                <div class="conseq-tile"><span class="conseq-label"><?= icon('coins') ?>Потребовал компенсацию</span><p>Это может сохранить авторитет, но создать новые проблемы для семьи.</p></div>
            </div>
            <?php if ($exampleId): ?>
                <a class="btn btn-primary" href="case.php?id=<?= $exampleId ?>"><?= icon('play') ?>Сыграть это дело</a>
            <?php endif; ?>
        </section>

        <section class="panel brief-block reveal" id="review" data-section>
            <header class="block-head"><span class="block-num">08</span><h2>Что будет происходить с контентом</h2></header>
            <p>Все созданные ситуации проходят отбор. Наиболее интересные попадут в MVP и будут протестированы на реальных игроках. По результатам тестирования лучшие типы ситуаций будут использоваться для дальнейшего создания контента.</p>
            <div class="metric-grid">
                <?php foreach ([
                    ['activity', 'Вовлечённость'], ['check-circle', 'Completion rate'], ['refresh', 'Retention'], ['dice', 'Повторные игры'],
                    ['swords', 'Расхождение мнений'], ['message', 'Количество обсуждений'], ['share', 'Потенциал для sharing'], ['flame', 'Эмоциональная реакция'],
                ] as [$ic, $label]): ?>
                    <div class="metric-chip"><?= icon($ic) ?><span><?= e($label) ?></span></div>
                <?php endforeach; ?>
            </div>
        </section>

        <section class="panel brief-block reveal" id="rewards" data-section>
            <header class="block-head"><span class="block-num">09</span><h2>Участие и система вознаграждения</h2></header>
            <div class="reward-tiles">
                <div class="reward"><b>0,2%</b><span>доля в пуле участия контент-креаторов при достижении проектом <b>10K MAU</b></span></div>
                <div class="reward"><b>до 1%</b><span>дополнительная доля за отдельные крупные задачи или контентные направления</span></div>
                <div class="reward"><b>Net</b><span>все расчёты — от чистой прибыли проекта, а не от выручки или оборота</span></div>
            </div>
            <p>Первый этап проекта является <b>pre-revenue</b> этапом, поэтому создание первого контента не предполагает гарантированной фиксированной оплаты. Участие контент-креаторов рассматривается как долгосрочный вклад в развитие проекта и предусматривает участие в его финансовом результате.</p>
            <p>Доля является частью долгосрочной системы участия в успехе проекта и даёт право на соответствующую часть распределяемого финансового результата в соответствии с условиями программы. По мере развития проекта участники могут получать дополнительные доли за значимый вклад в следующие этапы.</p>
            <p>Участие не ограничивается первым семидневным спринтом: размер участия связан с вкладом в проект, поэтому система рассчитана на долгосрочное сотрудничество, а не на разовую работу.</p>
        </section>

        <section class="panel brief-block reveal" id="sprint" data-section>
            <header class="block-head"><span class="block-num">10</span><h2>Первый спринт</h2></header>
            <div class="sprint-hero">
                <div class="sprint-stat"><b>7</b><span>дней</span></div>
                <div class="sprint-stat"><b>40</b><span>ситуаций на категорию</span></div>
                <div class="sprint-split">
                    <?php foreach (SITUATION_TYPES as $key => $t): ?>
                        <div class="split-seg split-<?= e($key) ?>" style="flex: <?= $t['target'] ?>">
                            <b><?= $t['target'] ?></b><span><?= e($t['many']) ?></span>
                        </div>
                    <?php endforeach; ?>
                </div>
            </div>
            <p>Главная цель первого спринта — создать не просто большое количество текстов, а ситуации, которые игроку действительно будет интересно читать, обсуждать и решать.</p>
            <a class="btn btn-primary btn-lg" href="create.php"><?= icon('edit') ?>Создать первую ситуацию</a>
        </section>
    </div>
</div>

<?php page_footer(); ?>
