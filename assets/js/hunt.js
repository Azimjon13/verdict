/* VERDICT — охота за тайниками: тайник стоит на своём элементе страницы, нажатие открывает подарок.
 *
 * Данные — <script id="hunt-data">: { spots: [{ id, token, selector, x, y, size, svg, opacity }], claim, back }.
 * x, y — % ширины и высоты элемента, так тайник остаётся на месте при любой ширине экрана.
 */
(() => {
  'use strict';

  const dataEl = document.getElementById('hunt-data');
  if (!dataEl) return;
  let cfg;
  try { cfg = JSON.parse(dataEl.textContent); } catch (_) { return; }

  const csrf = document.body.dataset.csrf || '';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const items = [];

  /* Элемент или его предок закреплён (шапка) — тогда тайник тоже fixed и пересчитывается при прокрутке. */
  function pinned(el) {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      const p = getComputedStyle(n).position;
      if (p === 'fixed' || p === 'sticky') return true;
    }
    return false;
  }

  function place(item) {
    if (!item.anchor || !item.anchor.isConnected) {
      item.anchor = document.querySelector(item.spot.selector);
      item.pinned = item.anchor ? pinned(item.anchor) : false;
    }
    const a = item.anchor;
    const r = a ? a.getBoundingClientRect() : null;
    if (!r || (!r.width && !r.height) || getComputedStyle(a).visibility === 'hidden') {
      item.el.hidden = true;
      return;
    }
    item.el.hidden = false;
    const x = r.left + (r.width * item.spot.x) / 100;
    const y = r.top + (r.height * item.spot.y) / 100;
    item.el.style.position = item.pinned ? 'fixed' : 'absolute';
    item.el.style.left = `${item.pinned ? x : x + window.scrollX}px`;
    item.el.style.top = `${item.pinned ? y : y + window.scrollY}px`;
  }

  let frame = 0;
  function placeAll() {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => items.forEach(place));
  }

  function remove(item) {
    item.el.classList.add('is-gone');
    setTimeout(() => item.el.remove(), reduce ? 0 : 700);
    const i = items.indexOf(item);
    if (i >= 0) items.splice(i, 1);
  }

  /* Значок охоты: счётчик, полоса, подсказка найденного тайника. */
  function progress(data) {
    const box = document.querySelector(`[data-hunt="${data.hunt}"]`);
    if (box) {
      const total = Number(box.dataset.total) || data.total;
      box.querySelector('[data-hunt-found]').textContent = String(data.found);
      const bar = box.querySelector('.hunt-progress');
      bar.setAttribute('aria-valuenow', String(data.found));
      bar.querySelector('i').style.width = `${Math.round((data.found / total) * 100)}%`;
      const li = box.querySelector(`[data-spot="${data.spot}"]`);
      if (li) {
        li.classList.add('is-found');
        const text = li.querySelector('span');
        const page = text.querySelector('small');
        text.textContent = data.gift ? `Найден: ${data.gift}` : 'Найден';
        if (page) text.appendChild(page);
      }
    }
    const count = document.querySelector('[data-hunt-count]');
    if (count) {
      let found = 0;
      let total = 0;
      document.querySelectorAll('[data-hunt]').forEach((h) => {
        found += Number(h.querySelector('[data-hunt-found]').textContent) || 0;
        total += Number(h.dataset.total) || 0;
      });
      count.textContent = `${found}/${total}`;
      document.querySelector('[data-hunt-badge]')?.classList.add('is-bumped');
    }
  }

  const TITLES = {
    found: 'Этот тайник уже ваш',
    empty: 'Тайник пуст',
    gone: 'Тайник исчез',
    blocked: 'Охота недоступна',
    token: 'Тайник не открылся',
  };

  async function claim(item) {
    if (item.busy) return;
    item.busy = true;
    item.el.classList.add('is-opening');
    const body = new FormData();
    body.append('_csrf', csrf);
    body.append('spot', String(item.spot.id));
    body.append('token', item.spot.token);
    body.append('back', cfg.back || '');
    let data = null;
    try {
      const res = await fetch(cfg.claim, {
        method: 'POST',
        body,
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrf },
        credentials: 'same-origin',
      });
      try { data = await res.json(); } catch (_) { /* не JSON */ }
    } catch (_) { /* сеть */ }
    item.busy = false;
    item.el.classList.remove('is-opening');
    const modal = window.VerdictModal;

    if (data && data.ok) {
      remove(item);
      progress(data);
      window.VerdictFX?.boost?.(2);
      if (modal) modal.alert({ tone: 'success', icon: 'gift', kicker: 'Тайник найден', title: 'Вы нашли тайник!', html: data.html, ok: 'Забрать' });
      return;
    }
    if (data && data.code === 'account') {
      if (!modal) return;
      modal.alert({
        tone: 'info', icon: 'lock', kicker: 'Тайник найден', title: 'Подарок ждёт вас в аккаунте', text: data.error, ok: 'Позже',
        items: [
          { text: 'Войти и забрать', onClick: () => { window.location.href = data.login; } },
          { text: 'Создать аккаунт', onClick: () => { window.location.href = data.register; } },
        ],
      });
      return;
    }
    if (data && ['found', 'empty', 'gone'].includes(data.code)) remove(item);
    if (modal) {
      modal.alert({
        tone: 'warn',
        title: (data && TITLES[data.code]) || 'Тайник не открылся',
        text: (data && data.error) || 'Нет связи с сервером. Попробуйте ещё раз.',
      });
    }
  }

  (cfg.spots || []).forEach((spot) => {
    const el = document.createElement('button');
    el.type = 'button';
    el.className = 'hunt-spot';
    el.tabIndex = -1; // тайник ищут глазами, а не перебором Tab по странице
    el.setAttribute('aria-label', 'Тайник');
    el.style.setProperty('--s', `${spot.size}px`);
    el.style.setProperty('--o', String(spot.opacity));
    el.innerHTML = spot.svg;
    el.hidden = true;
    const item = { spot, el, anchor: null, pinned: false, busy: false };
    el.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      claim(item);
    });
    document.body.appendChild(el);
    items.push(item);
  });

  if (!items.length) return;
  placeAll();
  window.addEventListener('resize', placeAll, { passive: true });
  window.addEventListener('scroll', () => { if (items.some((i) => i.pinned)) placeAll(); }, { passive: true });
  window.addEventListener('load', placeAll);
  // появление блоков при прокрутке (.reveal) двигает их transform-ом — после анимации тайник встаёт на место
  document.addEventListener('transitionend', placeAll, true);
  document.addEventListener('animationend', placeAll, true);
  document.fonts?.ready?.then(placeAll);
  if ('ResizeObserver' in window) new ResizeObserver(placeAll).observe(document.body);
  setInterval(placeAll, 1500); // вкладки, комикс и раскрывающиеся блоки меняют раскладку без resize
})();
