<?php
require __DIR__ . '/includes/bootstrap.php';

$editId = (int)($_GET['edit'] ?? 0);
$self = 'create.php' . ($editId ? '?edit=' . $editId : '');
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !is_logged_in()) {
    // Сессия закончилась, пока автор писал: не теряем текст — вернём его в форму после входа.
    $_SESSION['create_stash'] = ['edit' => $editId, 'form' => situation_from_input($_POST)];
    require_login($self, 'Сессия завершилась. Войдите снова — ваш текст сохранён и вернётся в форму.');
}
require_login($self, 'Войдите или зарегистрируйтесь, чтобы добавлять ситуации.');
$me = current_user();

$editing = $editId ? situation_find($editId) : null;
if ($editId && !$editing) {
    flash('error', 'Ситуация для редактирования не найдена.');
    redirect('library.php');
}
if ($editing && !can_edit_situation($editing)) {
    flash('error', 'Редактировать ситуацию может команда или автор, пока ситуация на отборе.');
    redirect('view.php?id=' . $editing['id']);
}

$canDraft = can_save_draft($editing);
$isDraft = $editing && $editing['status'] === 'draft';
$autosaveKey = autosave_key($editing['id'] ?? null);

$errors = [];
$restored = false;
$asDraft = false;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $form = situation_from_input($_POST);
    $asDraft = $canDraft && ($_POST['intent'] ?? '') === 'draft';
    // Автор — владелец аккаунта; при редактировании подпись не меняется.
    $form['author'] = $editing ? $editing['author'] : (string)$me['display_name'];
    if ($asDraft) {
        // В черновике категория и тип могут быть ещё не выбраны.
        $form['category'] = isset(CATEGORIES[$form['category']]) ? $form['category'] : '';
        $form['type'] = isset(SITUATION_TYPES[$form['type']]) ? $form['type'] : 'private';
    }
    if (!csrf_valid()) {
        $errors['_csrf'] = 'Сессия устарела. Проверьте данные и отправьте форму ещё раз.';
    } else {
        $errors = $asDraft ? situation_validate_draft($form) : situation_validate($form);
    }
    if (!$errors) {
        autosave_clear($autosaveKey);
        if ($asDraft) {
            if ($editing) {
                situation_update($editing['id'], $form, 'draft');
                $id = $editing['id'];
            } else {
                $id = situation_insert(db(), $form, 'draft', (int)$me['id']);
            }
            $level = situation_level($form);
            flash('success', 'Черновик «' . $form['title'] . '» сохранён'
                . ($level > 0 ? ' — готов уровень ' . $level . ' из 3 («' . LEVELS[$level]['name'] . '»)' : '')
                . '. Его видите только вы — вернитесь к нему в любой момент из профиля.');
            redirect('create.php?edit=' . $id);
        }
        if ($editing) {
            $remap = situation_update($editing['id'], $form, $isDraft ? 'pending' : null);
            $note = '';
            if ($remap['moved'] > 0) {
                $note .= ' Голоса за варианты, сменившие букву, перенесены вместе с ними (' . $remap['moved'] . ').';
            }
            if ($remap['deleted'] > 0) {
                $note .= ' Удалено голосов за убранные варианты: ' . $remap['deleted'] . '.';
            }
            flash('success', ($isDraft
                ? 'Ситуация «' . $form['title'] . '» отправлена на отбор. Спасибо за вклад!'
                : 'Изменения в ситуации «' . $form['title'] . '» сохранены.') . $note);
            redirect('view.php?id=' . $editing['id']);
        }
        $newId = situation_insert(db(), $form, 'pending', (int)$me['id']);
        flash('success', 'Ситуация «' . $form['title'] . '» отправлена на отбор. Спасибо за вклад!');
        redirect('view.php?id=' . $newId);
    }
    $form = situation_form_pad($form);
} elseif (($_SESSION['create_stash']['edit'] ?? null) === $editId) {
    // Текст, отправленный до того, как закончилась сессия.
    $form = situation_form_pad($_SESSION['create_stash']['form']);
    $form['author'] = $editing ? $editing['author'] : (string)$me['display_name'];
    unset($_SESSION['create_stash']);
    $restored = true;
} else {
    $form = $editing ? situation_form_pad($editing) : situation_form_defaults();
}

// Какой уровень формы показать: следующий после достигнутого, чтобы автор сразу видел, что дописать.
// После неудачной отправки на отбор — не ниже «Дела», иначе часть ошибок окажется в скрытых разделах.
// Сколько голосов у каждого варианта (по uid — буквы в форме могут уже сдвинуться).
if ($editing) {
    $voteCounts = vote_counts_for($editing['id']);
    $votesByUid = [];
    foreach ($editing['decisions'] as $d) {
        $votesByUid[$d['uid']] = $voteCounts[$d['key']] ?? 0;
    }
    foreach ($form['decisions'] as $k => $d) {
        $form['decisions'][$k]['votes'] = $votesByUid[$d['uid'] ?? ''] ?? 0;
    }
}

$achieved = situation_level($form);
$viewLevel = max(1, min(3, $achieved + 1));
if ($errors && !$asDraft && !isset($errors['_csrf'])) {
    $viewLevel = max($viewLevel, 2);
}

// Раздел шаблона => [номер, название, с какого уровня показывается].
$nav = [
    's1'  => ['01', 'Основная информация', 1],
    's2'  => ['02', 'Мир / сеттинг', 2],
    's3'  => ['03', 'Ситуация', 1],
    's4'  => ['04', 'Участники', 2],
    's5'  => ['05', 'Доказательства', 2],
    's6'  => ['06', 'Свидетели', 2],
    's7'  => ['07–08', 'Решения и последствия', 1],
    's9'  => ['09', 'Скрытая информация', 3],
    's10' => ['10', 'Неоднозначность', 2],
    's11' => ['11', 'Продолжение', 3],
    's12' => ['12', 'Заметки автора', 3],
    'sc'  => ['✓', 'Быстрая проверка', 3],
];
$lvl = static fn(string $section): string => $nav[$section][2] > 1 ? ' data-lvl="' . $nav[$section][2] . '"' : '';
$errAnchors = [
    'author' => 's1', 'category' => 's1', 'type' => 's1', 'title' => 's1',
    'world_place' => 's2', 'world_circumstances' => 's2', 'story' => 's3',
    'participants' => 's4', 'facts' => 's5', 'witnesses' => 's6', 'decisions' => 's7', 'ambiguity' => 's10',
];
$isPrivate = $form['type'] === 'private';
$storyWords = word_count($form['story']);

page_header($editing ? 'Редактирование ситуации' : 'Создать ситуацию', 'create', 'page-create', 'calm');
?>

<section class="page-hero page-hero-compact">
    <div class="container">
        <span class="kicker">Шаблон игровой ситуации</span>
        <h1><?= $editing ? ($isDraft ? 'Черновик: ' : 'Редактирование: ') . e($editing['title']) : 'Создать <span class="grad-text">ситуацию</span>' ?></h1>
        <p class="lead">Главное правило — не должно быть очевидного правильного ответа. Хорошая ситуация заставляет игрока остановиться, подумать и сомневаться. <a href="brief.php">Прочитать бриф</a></p>
    </div>
</section>

<div class="container create-layout" data-level="<?= $viewLevel ?>">
    <aside class="create-nav">
        <nav class="panel" aria-label="Разделы шаблона">
            <span class="label-mono">Разделы шаблона</span>
            <?php foreach ($nav as $anchor => [$n, $label, $from]): ?>
                <a href="#<?= $anchor ?>" data-nav="<?= $anchor ?>"<?= $lvl($anchor) ?>><span class="nav-num"><?= $n ?></span><?= e($label) ?><i class="nav-dot"></i></a>
            <?php endforeach; ?>
        </nav>
    </aside>

    <form class="create-form" method="post" action="create.php<?= $editing ? '?edit=' . $editing['id'] : '' ?>" novalidate data-create-form
          data-autosave="<?= e($autosaveKey) ?>" data-saved-at="<?= $editing ? strtotime($editing['updated_at']) * 1000 : 0 ?>"<?= $errors || $restored ? ' data-fresh-input' : '' ?>>
        <?= csrf_field() ?>
        <input type="hidden" name="intent" value="submit" data-intent>

        <div class="panel level-bar">
            <div class="level-bar-head">
                <span class="label-mono"><?= icon('layers') ?>Уровень заполнения</span>
                <span class="level-bar-note"><?= $canDraft
                    ? 'Остановитесь на любом уровне и сохраните черновик — текст также хранится в этом браузере. На отбор отправляется уровень 2.'
                    : 'Уровень меняет только набор видимых разделов — заполненные поля не теряются.' ?></span>
            </div>
            <div class="level-steps">
                <?php foreach (LEVELS as $n => $l): ?>
                    <button type="button" class="level-step<?= $achieved >= $n ? ' is-done' : '' ?>" data-level-tab="<?= $n ?>" data-desc="<?= e($l['desc']) ?>" aria-pressed="<?= $viewLevel === $n ? 'true' : 'false' ?>">
                        <span class="level-num"><?= $n ?></span>
                        <span class="level-body"><b><?= e($l['name']) ?></b><small><?= e($l['time']) ?></small></span>
                        <span class="level-state" data-level-state><?= $achieved >= $n ? icon('check') . 'Готово' : '' ?></span>
                    </button>
                <?php endforeach; ?>
            </div>
            <p class="level-desc" data-level-desc><?= e(LEVELS[$viewLevel]['desc']) ?></p>
        </div>

        <?php if ($restored): ?>
            <div class="panel notice notice-warn" role="status"><?= icon('refresh') ?><span>Мы вернули текст, который вы отправляли, когда сессия уже закончилась. Проверьте его и сохраните ещё раз.</span></div>
        <?php endif; ?>

        <?php if ($errors): ?>
            <div class="panel error-summary" role="alert" tabindex="-1" data-error-summary>
                <h2><?= icon('alert') ?>Проверьте, пожалуйста, форму</h2>
                <ul>
                    <?php foreach ($errors as $key => $msg): ?>
                        <li><a href="#<?= $errAnchors[$key] ?? 's1' ?>"><?= e($msg) ?></a></li>
                    <?php endforeach; ?>
                </ul>
            </div>
        <?php endif; ?>

        <!-- 1. Основная информация -->
        <section class="panel form-section" id="s1" data-section<?= $lvl('s1') ?>>
            <header class="block-head"><span class="block-num">01</span><h2>Основная информация</h2></header>

            <div class="author-line">
                <span class="avatar avatar-xs" style="--ah: <?= name_hue($form['author']) ?>"><?= e(initials($form['author'])) ?></span>
                <span>Автор: <b><?= e($form['author']) ?></b></span>
                <?php if (!$editing): ?><a href="account.php" class="author-change">изменить имя в профиле</a><?php endif; ?>
            </div>

            <fieldset class="field<?= isset($errors['category']) ? ' has-error' : '' ?>">
                <legend>Категория</legend>
                <div class="choice-grid">
                    <?php foreach (CATEGORIES as $key => $c): ?>
                        <label class="choice" style="<?= e(category_style($key)) ?>">
                            <input type="radio" name="category" value="<?= e($key) ?>"<?= $form['category'] === $key ? ' checked' : '' ?> required>
                            <span class="choice-body"><?= icon($c['icon']) ?><span><?= e($c['name']) ?></span></span>
                        </label>
                    <?php endforeach; ?>
                </div>
                <?= field_error($errors, 'category') ?>
            </fieldset>

            <fieldset class="field<?= isset($errors['type']) ? ' has-error' : '' ?>">
                <legend>Тип ситуации</legend>
                <div class="type-choices">
                    <?php foreach (SITUATION_TYPES as $key => $t): ?>
                        <label class="choice choice-type">
                            <input type="radio" name="type" value="<?= e($key) ?>"<?= $form['type'] === $key ? ' checked' : '' ?> data-type-input>
                            <span class="choice-body">
                                <span class="choice-icon"><?= icon($t['icon']) ?></span>
                                <b><?= e($t['name']) ?></b>
                                <small><?= e($t['desc']) ?></small>
                            </span>
                        </label>
                    <?php endforeach; ?>
                </div>
                <?= field_error($errors, 'type') ?>
            </fieldset>

            <label class="field<?= isset($errors['title']) ? ' has-error' : '' ?>">
                <span>Название</span>
                <input type="text" name="title" value="<?= e($form['title']) ?>" maxlength="120" required placeholder="Короткое и интригующее">
                <small>Короткое название ситуации. Не должно раскрывать правильный ответ.</small>
                <?= field_error($errors, 'title') ?>
            </label>
        </section>

        <!-- 2. Мир / Сеттинг -->
        <section class="panel form-section" id="s2" data-section<?= $lvl('s2') ?>>
            <header class="block-head"><span class="block-num">02</span><h2>Мир / Сеттинг</h2></header>
            <div class="field">
                <label for="world-setting">Тип мира <em>— из списка сеттингов брифа</em></label>
                <select class="vs" id="world-setting" name="world[setting]">
                    <option value="" data-placeholder<?= option_icon('globe') ?>>Не выбран</option>
                    <?php foreach (WORLDS as $w): ?>
                        <option value="<?= e($w['name']) ?>"<?= option_icon($w['icon']) ?><?= $form['world']['setting'] === $w['name'] ? ' selected' : '' ?>><?= e($w['name']) ?></option>
                    <?php endforeach; ?>
                </select>
                <small>Помогает отбору: видно, каких миров в спринте мало.</small>
            </div>
            <div class="grid grid-2">
                <label class="field<?= isset($errors['world_place']) ? ' has-error' : '' ?>">
                    <span>Место</span>
                    <input type="text" name="world[place]" value="<?= e($form['world']['place']) ?>" maxlength="160" placeholder="Где происходит ситуация?">
                    <?= field_error($errors, 'world_place') ?>
                </label>
                <label class="field">
                    <span>Время / эпоха</span>
                    <input type="text" name="world[era]" value="<?= e($form['world']['era']) ?>" maxlength="160" list="worlds-list" placeholder="Средневековье, постапокалипсис, далёкое будущее…">
                    <datalist id="worlds-list">
                        <?php foreach (WORLDS as $w): ?><option value="<?= e($w['name']) ?>"><?php endforeach; ?>
                    </datalist>
                </label>
            </div>
            <label class="field<?= isset($errors['world_circumstances']) ? ' has-error' : '' ?>">
                <span>Обстоятельства <em>— что происходит в этом мире и почему эта ситуация возможна?</em></span>
                <textarea name="world[circumstances]" rows="4" maxlength="2000" data-counter="sentences" data-min="2" data-max="5"><?= e($form['world']['circumstances']) ?></textarea>
                <small class="counter" data-counter-out>Рекомендуемый объём: 2–5 предложений.</small>
                <?= field_error($errors, 'world_circumstances') ?>
            </label>
        </section>

        <!-- 3. Ситуация -->
        <section class="panel form-section" id="s3" data-section<?= $lvl('s3') ?>>
            <header class="block-head"><span class="block-num">03</span><h2>Ситуация</h2></header>
            <div class="hint-box">
                <p><b>Опишите событие с точки зрения игрока.</b> Игрок должен понимать:</p>
                <ul class="hint-list">
                    <li>что произошло;</li><li>кто оказался вовлечён;</li><li>в чём заключается проблема;</li><li>почему игрок должен принять решение.</li>
                </ul>
                <p class="hint-warn"><?= icon('alert') ?>Не объясняйте игроку, какое решение является правильным.</p>
            </div>
            <label class="field<?= isset($errors['story']) ? ' has-error' : '' ?>">
                <span>Что произошло?</span>
                <textarea name="story" rows="11" maxlength="6000" data-counter="words" data-min="100" data-max="250" data-range-idea="<?= IDEA_MIN_WORDS ?>-80"><?= e($form['story']) ?></textarea>
                <div class="counter-bar" aria-hidden="true"><i></i></div>
                <small class="counter" data-counter-out><?= $storyWords ?> слов · рекомендуемый объём: 100–250 слов.</small>
                <?= field_error($errors, 'story') ?>
            </label>
        </section>

        <!-- 4. Участники -->
        <section class="panel form-section" id="s4" data-section<?= $lvl('s4') ?>>
            <header class="block-head"><span class="block-num">04</span><h2>Участники</h2></header>
            <p class="block-lead">Кто участвует в ситуации и какие между ними отношения. Добавьте или удалите участников при необходимости.</p>
            <?= field_error($errors, 'participants') ?>
            <?= render_repeater('participants', $form['participants'], 'render_participant', 'Добавить участника', 1, 12) ?>
        </section>

        <!-- 5. Доказательства -->
        <section class="panel form-section" id="s5" data-section<?= $lvl('s5') ?>>
            <header class="block-head"><span class="block-num">05</span><h2>Доказательства и доступная информация</h2></header>
            <p class="block-lead">Укажите, что игрок знает на момент принятия решения. <b>Важно разделять факты и предположения.</b></p>
            <?= field_error($errors, 'facts') ?>
            <div class="grid grid-2 evidence-form">
                <div>
                    <h3 class="sub-h facts-h"><?= icon('check-circle') ?>Факты</h3>
                    <?= render_repeater('facts', $form['facts'], static fn(string $i, $v, int $n): string => render_line('facts', $i, is_string($v) ? $v : '', $n, 'Факт', 'То, что игрок знает наверняка'), 'Добавить факт', 1, 20) ?>
                </div>
                <div>
                    <h3 class="sub-h unknown-h"><?= icon('help') ?>Неизвестно / вызывает сомнение</h3>
                    <?= render_repeater('unknowns', $form['unknowns'], static fn(string $i, $v, int $n): string => render_line('unknowns', $i, is_string($v) ? $v : '', $n, 'Сомнение', 'Противоречия, неизвестные факты, сомнительные обстоятельства'), 'Добавить сомнение', 0, 20) ?>
                </div>
            </div>
        </section>

        <!-- 6. Свидетели -->
        <section class="panel form-section<?= $isPrivate ? ' is-disabled' : '' ?>" id="s6" data-section<?= $lvl('s6') ?> data-witness-section>
            <header class="block-head"><span class="block-num">06</span><h2>Свидетели</h2></header>
            <p class="disabled-note"><?= icon('lock') ?>В частной ситуации свидетелей нет — игрок располагает только доступной ему информацией. Чтобы добавить свидетелей, выберите другой тип ситуации.</p>
            <div class="witness-fields">
                <p class="block-lead">Заполняется для ситуаций со свидетелями (1–5) и публичных ситуаций. <b>Свидетели не обязательно должны говорить правду.</b></p>
                <?= field_error($errors, 'witnesses') ?>
                <?= render_repeater('witnesses', $form['witnesses'], 'render_witness', 'Добавить свидетеля', 1, 8) ?>
            </div>
        </section>

        <!-- 7–8. Решения и последствия -->
        <section class="panel form-section" id="s7" data-section<?= $lvl('s7') ?>>
            <header class="block-head"><span class="block-num">07–08</span><h2>Решения и последствия</h2></header>
            <p class="block-lead" data-lvl-only="1">Для идеи хватит 2–3 коротких вариантов решения. Остальные варианты, их обоснование и последствия добавите на следующих уровнях.</p>
            <p class="block-lead" data-lvl-only="2">Предложите минимум 4–6 возможных решений и коротко объясните, почему игрок может выбрать каждое. Последствия раскроете на уровне 3.</p>
            <p class="block-lead" data-lvl="3">Предложите минимум 4–6 возможных решений. Для основных решений раскройте последствия: что произойдёт сразу, в будущем, с персонажами и с миром. Не обязательно прописывать последствия абсолютно для каждого варианта.</p>
            <div class="examples">
                <span class="label-mono">Примеры вердиктов</span>
                <?php foreach (['невиновен', 'виновен', 'частично ответственен', 'наказание', 'компенсация', 'изгнание', 'заключение', 'прощение', 'казнь', 'предупреждение', 'отсутствие наказания'] as $ex): ?>
                    <span class="chip chip-sm"><?= e($ex) ?></span>
                <?php endforeach; ?>
            </div>
            <?= field_error($errors, 'decisions') ?>
            <?= render_repeater('decisions', $form['decisions'], 'render_decision', 'Добавить вариант решения', 2, MAX_DECISIONS) ?>
            <p class="info-line"><?= icon('info') ?>Вариант «Другое решение» добавляется в игру автоматически — игрок всегда может предложить своё.</p>
        </section>

        <!-- 9. Скрытая информация -->
        <section class="panel form-section section-secret" id="s9" data-section<?= $lvl('s9') ?>>
            <header class="block-head"><span class="block-num">09</span><h2>Скрытая информация</h2><span class="chip chip-warn"><?= icon('eye-off') ?>Только для команды</span></header>
            <p class="block-lead">Что на самом деле произошло? Этот раздел не показывается игроку напрямую. Укажите: кто говорит правду, кто лжёт, что скрывается, какие факты игрок не знает, что произойдёт дальше и какие детали могут быть раскрыты позже.</p>
            <label class="field">
                <span class="visually-hidden">Скрытая информация</span>
                <textarea name="hidden" rows="5" maxlength="4000"><?= e($form['hidden']) ?></textarea>
            </label>
        </section>

        <!-- 10. Почему ситуация неоднозначная -->
        <section class="panel form-section" id="s10" data-section<?= $lvl('s10') ?>>
            <header class="block-head"><span class="block-num">10</span><h2>Почему ситуация неоднозначная</h2></header>
            <p class="block-lead">Кратко объясните, почему здесь нет очевидного правильного ответа. Игрок увидит это после вердикта — это топливо для споров.</p>
            <label class="field<?= isset($errors['ambiguity']) ? ' has-error' : '' ?>">
                <span>Главный конфликт</span>
                <input type="text" name="ambiguity[conflict]" value="<?= e($form['ambiguity']['conflict']) ?>" maxlength="600" placeholder="Жизнь одного ребёнка против безопасности всего поселения">
                <?= field_error($errors, 'ambiguity') ?>
            </label>
            <div class="grid grid-2" data-lvl="3">
                <label class="field"><span>Аргумент в пользу одного решения</span><textarea name="ambiguity[for_one]" rows="3" maxlength="1000"><?= e($form['ambiguity']['for_one']) ?></textarea></label>
                <label class="field"><span>Аргумент в пользу другого решения</span><textarea name="ambiguity[for_other]" rows="3" maxlength="1000"><?= e($form['ambiguity']['for_other']) ?></textarea></label>
            </div>
            <label class="field" data-lvl="3"><span>Что может разделить мнение игроков</span><textarea name="ambiguity[divide]" rows="2" maxlength="1000"><?= e($form['ambiguity']['divide']) ?></textarea></label>
        </section>

        <!-- 11. Потенциал для продолжения -->
        <section class="panel form-section" id="s11" data-section<?= $lvl('s11') ?>>
            <header class="block-head"><span class="block-num">11</span><h2>Потенциал для продолжения</h2></header>
            <fieldset class="field">
                <legend>Можно ли использовать эту ситуацию для дальнейших событий?</legend>
                <div class="segmented segmented-form">
                    <label><input type="radio" name="continuation_possible" value="yes"<?= $form['continuation']['possible'] ? ' checked' : '' ?> data-cont-input><span>Да</span></label>
                    <label><input type="radio" name="continuation_possible" value="no"<?= !$form['continuation']['possible'] ? ' checked' : '' ?> data-cont-input><span>Нет</span></label>
                </div>
            </fieldset>
            <label class="field" data-cont-text<?= $form['continuation']['possible'] ? '' : ' hidden' ?>>
                <span>Опишите возможное продолжение</span>
                <textarea name="continuation_text" rows="3" maxlength="2000"><?= e($form['continuation']['text']) ?></textarea>
            </label>
        </section>

        <!-- 12. Дополнительные заметки -->
        <section class="panel form-section" id="s12" data-section<?= $lvl('s12') ?>>
            <header class="block-head"><span class="block-num">12</span><h2>Дополнительные заметки автора</h2></header>
            <p class="block-lead">Альтернативные варианты, интересные детали, возможные сюжетные повороты, идеи для визуала и будущих ситуаций, связанные персонажи или события.</p>
            <label class="field">
                <span class="visually-hidden">Заметки автора</span>
                <textarea name="notes" rows="4" maxlength="4000"><?= e($form['notes']) ?></textarea>
            </label>
        </section>

        <!-- Быстрая проверка -->
        <section class="panel form-section checklist-section" id="sc" data-section<?= $lvl('sc') ?>>
            <header class="block-head"><span class="block-num">✓</span><h2>Быстрая проверка перед отправкой</h2></header>
            <div class="checklist-wrap">
                <div class="checklist">
                    <?php foreach (CHECKLIST as $i => $item): ?>
                        <label class="check">
                            <input type="checkbox" name="checklist[]" value="<?= $i ?>"<?= in_array($i, $form['checklist'], true) ? ' checked' : '' ?>>
                            <span class="check-box"><?= icon('check') ?></span>
                            <span><?= e($item) ?></span>
                        </label>
                    <?php endforeach; ?>
                </div>
                <div class="check-ring" data-check-ring aria-hidden="true">
                    <svg viewBox="0 0 120 120"><circle class="ring-track" cx="60" cy="60" r="52"/><circle class="ring-fill" cx="60" cy="60" r="52" pathLength="100"/></svg>
                    <div><b data-check-count>0</b><span>из <?= count(CHECKLIST) ?></span></div>
                </div>
            </div>
        </section>

        <?php $sendsToReview = !$editing || $isDraft; ?>
        <div class="submit-bar panel">
            <p><?= icon('info') ?><span>
                <?php if ($canDraft): ?><span data-lvl-only="1">Сохраните идею черновиком и вернитесь к ней позже — или переходите к уровню 2, чтобы сделать из неё дело.</span><?php endif; ?>
                <span<?= $canDraft ? ' data-lvl="2"' : '' ?>><?= $sendsToReview ? 'После отправки ситуация попадёт на отбор. Лучшие войдут в MVP и будут протестированы на реальных игроках.' : 'Изменения сразу появятся в досье и в игре.' ?></span>
                <small class="autosave-status" data-autosave-status aria-live="polite"></small>
            </span></p>
            <div class="submit-actions">
                <?php if ($canDraft): ?>
                    <!-- Первая кнопка в форме: Enter в поле сохраняет черновик, а не отправляет на отбор. -->
                    <button type="submit" name="intent" value="draft" class="btn btn-lg" data-intent-value="draft"><?= icon('file') ?><?= $editing && !$isDraft ? 'Вернуть в черновики' : 'Сохранить черновик' ?></button>
                    <button type="button" class="btn btn-primary btn-lg" data-lvl-only="1" data-level-next><?= icon('arrow-right') ?>Дальше: уровень 2</button>
                <?php endif; ?>
                <button type="submit" name="intent" value="submit" class="btn btn-primary btn-lg" data-intent-value="submit"<?= $canDraft ? ' data-lvl="2"' : '' ?>><?= icon($sendsToReview ? 'send' : 'check') ?><?= $sendsToReview ? 'Отправить на отбор' : 'Сохранить изменения' ?></button>
            </div>
        </div>
    </form>
</div>

<?php page_footer(['create.js']); ?>
