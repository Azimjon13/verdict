/* VERDICT — неоновые выпадающие списки поверх обычного <select class="vs">.
 *
 * Настоящий <select> остаётся в форме (скрыт) и получает value и событие change,
 * поэтому отправка форм, onchange и проверка обязательных полей работают как раньше.
 *
 * Атрибуты <option>: data-icon (SVG-разметка), data-hue (оттенок точки/иконки), data-desc (подпись).
 * Атрибуты <select>: data-search (поиск по списку), data-size="sm", data-align="right",
 *                    data-autosubmit (отправить форму при выборе).
 */
(() => {
  'use strict';

  const SVG = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const CHEVRON = SVG('<path d="m6 9 6 6 6-6"/>');
  const CHECK = SVG('<path d="M20 6 9 17l-5-5"/>');
  const SEARCH = SVG('<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>');

  let uid = 0;
  let current = null;

  function optionHtml(opt) {
    const hue = opt.dataset.hue ? ` style="--h:${opt.dataset.hue}"` : '';
    const mark = opt.dataset.icon
      ? `<span class="vs-ico"${hue}>${opt.dataset.icon}</span>`
      : (opt.dataset.hue ? `<span class="vs-dot"${hue}></span>` : '');
    return { mark, text: opt.textContent.trim(), desc: opt.dataset.desc || '' };
  }

  function enhance(select) {
    if (select.dataset.enhanced) return;
    select.dataset.enhanced = '1';
    const id = `vs${++uid}`;

    const wrap = document.createElement('div');
    wrap.className = 'vselect'
      + (select.dataset.size === 'sm' ? ' vselect-sm' : '')
      + (select.dataset.align === 'right' ? ' align-right' : '');
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add('vselect-native');
    select.tabIndex = -1;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'vselect-btn';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', `${id}-list`);
    const label = select.getAttribute('aria-label') || select.closest('.field')?.querySelector(':scope > span, :scope > label')?.firstChild?.textContent?.trim() || '';
    btn.innerHTML = `<span class="visually-hidden">${label ? label + ': ' : ''}</span><span class="vselect-current"></span><span class="vselect-chev">${CHEVRON}</span>`;

    const panel = document.createElement('div');
    panel.className = 'vselect-panel';
    panel.hidden = true;

    let search = null;
    if (select.dataset.search !== undefined || select.options.length > 9) {
      const box = document.createElement('label');
      box.className = 'vselect-search';
      box.innerHTML = `${SEARCH}<input type="text" placeholder="Поиск…" autocomplete="off" aria-label="Поиск по списку">`;
      search = box.querySelector('input');
      panel.appendChild(box);
    }

    const list = document.createElement('div');
    list.className = 'vselect-options';
    list.id = `${id}-list`;
    list.setAttribute('role', 'listbox');
    list.tabIndex = -1;
    if (label) list.setAttribute('aria-label', label);
    panel.appendChild(list);

    const empty = document.createElement('div');
    empty.className = 'vselect-empty';
    empty.textContent = 'Ничего не найдено';
    empty.hidden = true;
    panel.appendChild(empty);

    wrap.append(btn, panel);

    const items = [];
    const addOption = (opt, group) => {
      const { mark, text, desc } = optionHtml(opt);
      const el = document.createElement('div');
      el.className = 'vselect-opt';
      el.id = `${id}-o${items.length}`;
      el.setAttribute('role', 'option');
      el.innerHTML = `${mark}<span class="vs-text"><span></span>${desc ? '<small></small>' : ''}</span><span class="vs-check">${CHECK}</span>`;
      el.querySelector('.vs-text > span').textContent = text;
      if (desc) el.querySelector('small').textContent = desc;
      if (opt.disabled) el.setAttribute('aria-disabled', 'true');
      list.appendChild(el);
      items.push({ el, opt, text: (text + ' ' + desc).toLowerCase(), group });
    };
    [...select.children].forEach((child) => {
      if (child.tagName === 'OPTGROUP') {
        const head = document.createElement('div');
        head.className = 'vselect-group';
        head.textContent = child.label;
        list.appendChild(head);
        [...child.children].forEach((o) => addOption(o, head));
      } else {
        addOption(child, null);
      }
    });

    const inst = { select, wrap, btn, panel, list, search, empty, items, active: -1, typed: '', typedAt: 0 };
    select._vs = inst;
    sync(inst);

    btn.addEventListener('click', () => (wrap.classList.contains('open') ? close(inst, true) : open(inst)));
    btn.addEventListener('keydown', (e) => {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        open(inst);
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        typeahead(inst, e.key, true);
      }
    });
    panel.addEventListener('keydown', (e) => onPanelKey(inst, e));
    list.addEventListener('click', (e) => {
      const el = e.target.closest('.vselect-opt');
      if (el && el.getAttribute('aria-disabled') !== 'true') choose(inst, items.find((i) => i.el === el));
    });
    list.addEventListener('mousemove', (e) => {
      const el = e.target.closest('.vselect-opt');
      if (el) setActive(inst, items.findIndex((i) => i.el === el), false);
    });
    search?.addEventListener('input', () => filter(inst));
    // Клик по <label> или фокус на скрытом select переводим на кнопку.
    select.addEventListener('focus', () => btn.focus());
    select.addEventListener('click', (e) => { e.preventDefault(); open(inst); });
    select.addEventListener('change', () => sync(inst));
  }

  function sync(inst) {
    const sel = inst.items.find((i) => i.opt.selected) || inst.items[0];
    inst.items.forEach((i) => i.el.setAttribute('aria-selected', String(i === sel)));
    const cur = inst.btn.querySelector('.vselect-current');
    if (!sel) { cur.textContent = ''; return; }
    const { mark, text } = optionHtml(sel.opt);
    cur.innerHTML = `${mark}<span class="vs-label"></span>`;
    cur.querySelector('.vs-label').textContent = text;
    inst.wrap.classList.toggle('is-placeholder', sel.opt.value === '' && sel.opt.dataset.placeholder !== undefined);
  }

  function visible(inst) {
    return inst.items.filter((i) => !i.el.hidden && i.el.getAttribute('aria-disabled') !== 'true');
  }

  function setActive(inst, index, scroll = true) {
    inst.items.forEach((i, n) => i.el.classList.toggle('active', n === index));
    inst.active = index;
    const item = inst.items[index];
    if (item) {
      inst.list.setAttribute('aria-activedescendant', item.el.id);
      if (scroll) item.el.scrollIntoView({ block: 'nearest' });
    }
  }

  function move(inst, step) {
    const vis = visible(inst);
    if (!vis.length) return;
    const pos = vis.findIndex((i) => inst.items.indexOf(i) === inst.active);
    let next;
    if (step === 'first') next = vis[0];
    else if (step === 'last') next = vis[vis.length - 1];
    else next = vis[Math.max(0, Math.min(vis.length - 1, (pos < 0 ? (step > 0 ? -1 : vis.length) : pos) + step))];
    setActive(inst, inst.items.indexOf(next));
  }

  function filter(inst) {
    const q = inst.search.value.trim().toLowerCase();
    inst.items.forEach((i) => { i.el.hidden = q !== '' && !i.text.includes(q); });
    inst.list.querySelectorAll('.vselect-group').forEach((g) => {
      g.hidden = !inst.items.some((i) => i.group === g && !i.el.hidden);
    });
    const vis = visible(inst);
    inst.empty.hidden = vis.length > 0;
    setActive(inst, vis.length ? inst.items.indexOf(vis[0]) : -1);
  }

  function typeahead(inst, ch, selectDirectly) {
    const now = Date.now();
    inst.typed = (now - inst.typedAt < 700 ? inst.typed : '') + ch.toLowerCase();
    inst.typedAt = now;
    const match = visible(inst).find((i) => i.text.startsWith(inst.typed));
    if (!match) return;
    if (selectDirectly) choose(inst, match, false);
    else setActive(inst, inst.items.indexOf(match));
  }

  function onPanelKey(inst, e) {
    const inSearch = e.target === inst.search;
    switch (e.key) {
      case 'ArrowDown': e.preventDefault(); move(inst, 1); break;
      case 'ArrowUp': e.preventDefault(); move(inst, -1); break;
      case 'Home': if (!inSearch) { e.preventDefault(); move(inst, 'first'); } break;
      case 'End': if (!inSearch) { e.preventDefault(); move(inst, 'last'); } break;
      case 'Enter':
        e.preventDefault();
        if (inst.items[inst.active]) choose(inst, inst.items[inst.active]);
        break;
      case ' ':
        if (!inSearch) { e.preventDefault(); if (inst.items[inst.active]) choose(inst, inst.items[inst.active]); }
        break;
      case 'Escape': e.preventDefault(); e.stopPropagation(); close(inst, true); break;
      case 'Tab': close(inst, false); break;
      default:
        if (!inSearch && e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) typeahead(inst, e.key, false);
    }
  }

  function open(inst) {
    if (current && current !== inst) close(current, false);
    current = inst;
    inst.panel.hidden = false;
    inst.wrap.classList.add('open');
    inst.btn.setAttribute('aria-expanded', 'true');
    if (inst.search) { inst.search.value = ''; filter(inst); }

    // Открываем вверх, если снизу не хватает места.
    inst.wrap.classList.remove('drop-up');
    const r = inst.btn.getBoundingClientRect();
    const need = Math.min(inst.panel.scrollHeight, 360) + 12;
    if (window.innerHeight - r.bottom < need && r.top > need) inst.wrap.classList.add('drop-up');

    const sel = inst.items.findIndex((i) => i.opt.selected);
    setActive(inst, sel >= 0 ? sel : inst.items.indexOf(visible(inst)[0]));
    (inst.search || inst.list).focus({ preventScroll: true });
  }

  function close(inst, focusButton) {
    if (!inst.wrap.classList.contains('open')) return;
    inst.wrap.classList.remove('open', 'drop-up');
    inst.panel.hidden = true;
    inst.btn.setAttribute('aria-expanded', 'false');
    if (current === inst) current = null;
    if (focusButton) inst.btn.focus({ preventScroll: true });
  }

  function choose(inst, item, closeAfter = true) {
    if (!item) return;
    const changed = inst.select.value !== item.opt.value;
    if (changed) {
      inst.select.dataset.prev = inst.select.value;
      inst.select.value = item.opt.value;
    }
    sync(inst);
    if (closeAfter) close(inst, true);
    if (changed) {
      inst.select.dispatchEvent(new Event('input', { bubbles: true }));
      inst.select.dispatchEvent(new Event('change', { bubbles: true }));
      if (inst.select.dataset.autosubmit !== undefined && inst.select.form) {
        const form = inst.select.form;
        form.requestSubmit ? form.requestSubmit() : form.submit();
      }
    }
  }

  document.addEventListener('pointerdown', (e) => {
    if (current && !current.wrap.contains(e.target)) close(current, false);
  });
  window.addEventListener('resize', () => current && close(current, false));

  // Если подтверждение в модальном окне отменено — возвращаем прежнее значение.
  document.addEventListener('verdict:confirm-cancel', (e) => {
    e.target.querySelectorAll?.('select[data-autosubmit]').forEach((s) => {
      if (s.dataset.prev !== undefined) {
        s.value = s.dataset.prev;
        if (s._vs) sync(s._vs);
      }
    });
  });

  window.VerdictSelect = { enhance, refresh: (s) => s._vs && sync(s._vs) };
  document.querySelectorAll('select.vs').forEach(enhance);
})();
