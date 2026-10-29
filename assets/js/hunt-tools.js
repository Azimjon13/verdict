/* VERDICT — для команды: размещение тайника кликом по странице (?hunt_place=<тайник>) и предпросмотр
 * тайников охоты (?hunt_preview=<охота>). Данные — <script id="hunt-tools">.
 */
(() => {
  'use strict';

  const dataEl = document.getElementById('hunt-tools');
  if (!dataEl) return;
  let cfg;
  try { cfg = JSON.parse(dataEl.textContent); } catch (_) { return; }

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* Панель сверху: что происходит и как выйти. */
  const bar = document.createElement('div');
  bar.className = 'hunt-tools';
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', 'Инструменты охоты');
  document.body.appendChild(bar);

  /* Уже размещённые тайники охоты на этой странице — подписанные маркеры. */
  const marks = [];
  function addMark(spot, cls) {
    const el = document.createElement('span');
    el.className = `hunt-mark ${cls || ''}`;
    el.style.setProperty('--s', `${spot.size}px`);
    el.innerHTML = `${spot.svg || ''}<small>${esc(spot.label || '')}</small>`;
    document.body.appendChild(el);
    marks.push({ spot, el });
    return el;
  }
  function placeMarks() {
    marks.forEach(({ spot, el }) => {
      const a = spot.selector && document.querySelector(spot.selector);
      const r = a && a.getBoundingClientRect();
      if (!r || (!r.width && !r.height)) { el.hidden = true; return; }
      el.hidden = false;
      el.style.left = `${r.left + window.scrollX + (r.width * spot.x) / 100}px`;
      el.style.top = `${r.top + window.scrollY + (r.height * spot.y) / 100}px`;
    });
  }
  (cfg.others || []).forEach((s) => addMark(s, cfg.mode === 'preview' ? 'is-preview' : ''));
  const replace = () => requestAnimationFrame(placeMarks);
  window.addEventListener('resize', replace, { passive: true });
  window.addEventListener('load', replace);
  document.addEventListener('transitionend', replace, true);
  document.addEventListener('animationend', replace, true);
  setInterval(placeMarks, 1500);
  placeMarks();

  if (cfg.mode === 'preview') {
    bar.innerHTML = `<span class="ht-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg></span>
      <span class="ht-text"><b>Предпросмотр охоты «${esc(cfg.title)}»</b>
      <small>${marks.length ? `На этой странице тайников: ${marks.length}. Игроки видят их бледнее — как задано в настройках.` : 'На этой странице тайников нет.'}</small></span>
      <a class="btn btn-sm" href="${esc(cfg.back)}">Вернуться в админку</a>`;
    return;
  }

  /* ---------- Размещение ---------- */
  if (!cfg.allowed) {
    bar.innerHTML = `<span class="ht-text"><b>Здесь тайник разместить нельзя</b><small>Откройте страницу игры или для авторов.</small></span>
      <a class="btn btn-sm" href="${esc(cfg.back)}">Назад</a>`;
    return;
  }

  const scopes = [];
  if (cfg.with_id) scopes.push(['page', `Только эта страница (${cfg.path})`], ['kind', `Все страницы «${cfg.page_name}»`]);
  else scopes.push(['page', `Страница «${cfg.page_name}»`]);
  scopes.push(['site', 'Все страницы сайта (например, в шапке или подвале)']);

  bar.innerHTML = `<span class="ht-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M22 12h-4M6 12H2M12 6V2M12 22v-4"/></svg></span>
    <span class="ht-text"><b>Где спрятать «${esc(cfg.spot.label)}»?</b><small>Наведите на элемент и кликните в нужную точку. Тайник будет держаться за этот элемент. Esc — отмена.</small></span>
    <label class="ht-scope"><span>Показывать</span><select>${scopes.map(([v, t]) => `<option value="${v}">${esc(t)}</option>`).join('')}</select></label>
    <button type="button" class="btn btn-sm btn-ghost" data-ht-move title="Если панель закрывает нужное место">Панель вниз</button>
    <a class="btn btn-sm btn-ghost" href="${esc(cfg.back)}">Отмена</a>`;
  const scope = bar.querySelector('select');
  bar.querySelector('[data-ht-move]').addEventListener('click', (e) => {
    const down = bar.classList.toggle('at-bottom');
    e.currentTarget.textContent = down ? 'Панель вверх' : 'Панель вниз';
  });

  const box = document.createElement('div');
  box.className = 'hunt-target';
  box.hidden = true;
  document.body.appendChild(box);
  const ghost = addMark({ ...cfg.spot, x: 0, y: 0 }, 'is-ghost');
  ghost.hidden = true;
  marks.pop(); // призрак ходит за курсором, его не пересчитываем

  const skip = (el) => !el || el === document.documentElement || el === document.body || el.closest('.hunt-tools, .hunt-mark, .hunt-target, .modal-root, .toasts');

  /* Элемент для привязки: не значок и не его линия, а то, в чём он стоит (кнопка, ссылка, заголовок). */
  function anchorOf(target) {
    let el = target;
    while (el && el.closest && el.closest('svg')) el = el.closest('svg').parentElement;
    return skip(el) ? null : el;
  }

  /* Селектор, который найдёт этот элемент снова: от ближайшего предка с id, иначе от body. */
  function selectorFor(el) {
    const parts = [];
    for (let n = el; n && n.nodeType === 1 && n !== document.body; n = n.parentElement) {
      if (n.id && /^[A-Za-z][\w-]*$/.test(n.id) && document.querySelectorAll(`#${CSS.escape(n.id)}`).length === 1) {
        parts.unshift(`#${CSS.escape(n.id)}`);
        return parts.join(' > ');
      }
      let part = n.tagName.toLowerCase();
      const parent = n.parentElement;
      if (parent) {
        const same = [...parent.children].filter((c) => c.tagName === n.tagName);
        if (same.length > 1) part += `:nth-of-type(${same.indexOf(n) + 1})`;
      }
      parts.unshift(part);
    }
    return `body > ${parts.join(' > ')}`;
  }

  let current = null;
  function hover(e) {
    const el = anchorOf(document.elementFromPoint(e.clientX, e.clientY));
    current = el;
    if (!el) { box.hidden = true; ghost.hidden = true; return; }
    const r = el.getBoundingClientRect();
    Object.assign(box.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    box.hidden = false;
    box.dataset.tag = el.tagName.toLowerCase() + (el.classList[0] ? `.${el.classList[0]}` : '');
    ghost.hidden = false;
    ghost.style.left = `${e.clientX + window.scrollX}px`;
    ghost.style.top = `${e.clientY + window.scrollY}px`;
  }

  let saving = false;
  async function pick(e) {
    if (e.target.closest('.hunt-tools')) return;
    e.preventDefault();
    e.stopPropagation();
    const el = anchorOf(document.elementFromPoint(e.clientX, e.clientY));
    if (!el || saving) return;
    const r = el.getBoundingClientRect();
    const round = (v) => Math.round(Math.max(0, Math.min(100, v)) * 100) / 100;
    const payload = {
      page: cfg.page,
      path: cfg.path,
      scope: scope.value,
      selector: selectorFor(el),
      x: round(((e.clientX - r.left) / (r.width || 1)) * 100),
      y: round(((e.clientY - r.top) / (r.height || 1)) * 100),
    };
    if (document.querySelector(payload.selector) !== el) {
      window.VerdictModal?.alert({ tone: 'warn', title: 'Не получилось привязаться', text: 'Выберите соседний или родительский элемент.' });
      return;
    }
    saving = true;
    bar.classList.add('is-saving');
    try {
      const res = await fetch(cfg.save, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': cfg.csrf },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data || !data.ok) throw new Error((data && data.error) || 'Не удалось сохранить место тайника.');
      window.location.href = data.back;
    } catch (err) {
      saving = false;
      bar.classList.remove('is-saving');
      window.VerdictModal?.alert({ tone: 'danger', title: 'Тайник не размещён', text: err.message });
    }
  }

  document.documentElement.classList.add('hunt-placing');
  document.addEventListener('mousemove', hover, { passive: true });
  document.addEventListener('click', pick, true);
  ['pointerdown', 'mousedown', 'touchstart', 'submit'].forEach((type) => {
    document.addEventListener(type, (e) => { if (!e.target.closest?.('.hunt-tools')) e.stopPropagation(); }, true);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !window.VerdictModal?.isOpen()) window.location.href = cfg.back;
  });
  window.addEventListener('scroll', () => { box.hidden = true; current = null; }, { passive: true });
})();
