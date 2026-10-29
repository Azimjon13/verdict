<?php
declare(strict_types=1);

defined('APP_ROOT') || exit;

/* Рендер повторяющихся блоков формы «Создать ситуацию».
   $i — индекс поля (или '__i__' для <template>), $n — номер по порядку. */

function field_error(array $errors, string $key): string
{
    return isset($errors[$key]) ? '<p class="field-error" role="alert">' . icon('alert') . e($errors[$key]) . '</p>' : '';
}

function rep_head(string $label, int $n, string $removeLabel): string
{
    return '<div class="rep-head"><span class="rep-label">' . e($label) . ' <b class="rep-num">' . ($n ?: '') . '</b></span>'
        . '<button type="button" class="rep-remove" aria-label="' . e($removeLabel) . '" title="' . e($removeLabel) . '">' . icon('x') . '</button></div>';
}

function render_participant(string $i, array $p, int $n): string
{
    $v = static fn(string $k): string => e($p[$k] ?? '');
    $name = "participants[$i]";
    return '<div class="rep-item person-item">'
        . rep_head('Участник', $n, 'Удалить участника')
        . '<div class="grid grid-3">'
        . '<label class="field"><span>Имя</span><input type="text" name="' . $name . '[name]" value="' . $v('name') . '" maxlength="80" placeholder="Например: Аран"></label>'
        . '<label class="field"><span>Возраст</span><input type="text" name="' . $name . '[age]" value="' . $v('age') . '" maxlength="40" placeholder="41"></label>'
        . '<label class="field"><span>Роль</span><input type="text" name="' . $name . '[role]" value="' . $v('role') . '" maxlength="120" placeholder="Механик водяных насосов"></label>'
        . '</div>'
        . '<label class="field"><span>Отношение к другим</span><input type="text" name="' . $name . '[relations]" value="' . $v('relations') . '" maxlength="300" placeholder="Отец Леи, в натянутых отношениях с главой охраны"></label>'
        . '<label class="field"><span>Краткое описание</span><textarea name="' . $name . '[description]" rows="2" maxlength="600" placeholder="Характер, мотивы, что важно знать игроку">' . $v('description') . '</textarea></label>'
        . '</div>';
}

function render_line(string $field, string $i, string $value, int $n, string $label, string $placeholder): string
{
    return '<div class="rep-item line-item">'
        . rep_head($label, $n, 'Удалить')
        . '<textarea name="' . $field . '[' . $i . ']" rows="2" maxlength="1000" placeholder="' . e($placeholder) . '" aria-label="' . e($label) . '">' . e($value) . '</textarea>'
        . '</div>';
}

function render_witness(string $i, array $w, int $n): string
{
    $v = static fn(string $k): string => e($w[$k] ?? '');
    $name = "witnesses[$i]";
    return '<div class="rep-item witness-item">'
        . rep_head('Свидетель', $n, 'Удалить свидетеля')
        . '<label class="field"><span>Имя</span><input type="text" name="' . $name . '[name]" value="' . $v('name') . '" maxlength="120" placeholder="Например: Агафья, травница"></label>'
        . '<label class="field"><span>Что он утверждает</span><textarea name="' . $name . '[claim]" rows="2" maxlength="1000" placeholder="Показания своими словами">' . $v('claim') . '</textarea></label>'
        . '<div class="grid grid-2">'
        . '<label class="field"><span>Насколько ему можно доверять</span><textarea name="' . $name . '[trust]" rows="2" maxlength="1000">' . $v('trust') . '</textarea></label>'
        . '<label class="field"><span>Есть ли личный интерес</span><textarea name="' . $name . '[interest]" rows="2" maxlength="1000">' . $v('interest') . '</textarea></label>'
        . '</div></div>';
}

function render_decision(string $i, array $d, int $n): string
{
    $v = static fn(string $k): string => e($d[$k] ?? '');
    $name = "decisions[$i]";
    $letter = $n > 0 ? chr(64 + $n) : '';
    $open = decision_has_consequences($d) || !empty($d['effects']) ? ' open' : '';

    $effects = '';
    foreach (METRICS as $key => $m) {
        $val = (int)($d['effects'][$key] ?? 0);
        $effects .= '<label class="effect">'
            . '<span class="effect-name">' . icon($m['icon']) . e($m['name']) . '</span>'
            . '<input type="range" min="-3" max="3" step="1" name="' . $name . '[effects][' . $key . ']" value="' . $val . '">'
            . '<output class="effect-out ' . ($val > 0 ? 'up' : ($val < 0 ? 'down' : '')) . '">' . ($val > 0 ? '+' . $val : $val) . '</output>'
            . '</label>';
    }

    // Сколько игроков уже выбрали этот вариант (только при правке дела в игре) — удалять такой вариант осторожно.
    $votes = (int)($d['votes'] ?? 0);
    $votesChip = $votes > 0
        ? '<span class="rep-votes" title="Столько игроков уже выбрали этот вариант. Голоса останутся за ним, даже если буква сменится.">'
            . icon('gavel') . $votes . ' ' . plural($votes, 'голос', 'голоса', 'голосов') . '</span>'
        : '';

    return '<div class="rep-item decision-item"' . ($votes > 0 ? ' data-votes="' . $votes . '"' : '') . '>'
        . '<input type="hidden" name="' . $name . '[uid]" value="' . $v('uid') . '">'
        . '<div class="rep-head"><span class="rep-letter">' . $letter . '</span><span class="rep-label">Вариант решения</span>' . $votesChip
        . '<button type="button" class="rep-remove" aria-label="Удалить вариант" title="Удалить вариант">' . icon('x') . '</button></div>'
        . '<label class="field"><span>Решение</span><input type="text" name="' . $name . '[text]" value="' . $v('text') . '" maxlength="300" placeholder="Например: Частично ответственен — понять мотив, но назначить отработку"></label>'
        . '<label class="field" data-lvl="2"><span>Почему игрок может выбрать этот вариант</span><textarea name="' . $name . '[why]" rows="2" maxlength="1000">' . $v('why') . '</textarea></label>'
        . '<details class="conseq" data-lvl="3"' . $open . '><summary>' . icon('zap') . 'Последствия этого решения <small>раздел 8</small>' . icon('chevron-down', 'chev') . '</summary>'
        . '<div class="grid grid-2">'
        . '<label class="field"><span>Немедленное последствие</span><textarea name="' . $name . '[immediate]" rows="2" maxlength="1000">' . $v('immediate') . '</textarea></label>'
        . '<label class="field"><span>Долгосрочное последствие</span><textarea name="' . $name . '[longterm]" rows="2" maxlength="1000">' . $v('longterm') . '</textarea></label>'
        . '<label class="field"><span>Влияние на персонажей</span><textarea name="' . $name . '[characters]" rows="2" maxlength="1000">' . $v('characters') . '</textarea></label>'
        . '<label class="field"><span>Влияние на общество / мир</span><textarea name="' . $name . '[world]" rows="2" maxlength="1000">' . $v('world') . '</textarea></label>'
        . '</div>'
        . '<div class="effects"><p class="effects-title">Влияние на показатели мира <small>от −3 до +3</small></p><div class="effects-grid">' . $effects . '</div></div>'
        . '</details></div>';
}

/**
 * Обёртка повторителя: список элементов, <template> для новых и кнопка «добавить».
 */
function render_repeater(string $key, array $items, callable $render, string $addLabel, int $min, int $max): string
{
    $html = '<div class="repeater" data-repeater="' . e($key) . '" data-min="' . $min . '" data-max="' . $max . '" data-next="' . count($items) . '">';
    $html .= '<div class="rep-list">';
    $n = 0;
    foreach ($items as $item) {
        $html .= $render((string)$n, $item, $n + 1);
        $n++;
    }
    $html .= '</div>';
    $html .= '<template>' . $render('__i__', [], 0) . '</template>';
    $html .= '<button type="button" class="btn btn-sm btn-ghost rep-add">' . icon('plus') . e($addLabel) . '</button>';
    $html .= '</div>';
    return $html;
}
