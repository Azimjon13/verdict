/* VERDICT — админка: подсказки на графиках (наведение и фокус), поля форм, которые зависят от выбора. */
(() => {
  'use strict';

  /* Подсказка графика: значение крупно, подпись мельче. Текст — только через textContent. */
  const tip = document.createElement('div');
  tip.className = 'vz-tip';
  tip.hidden = true;
  tip.innerHTML = '<b></b><span></span>';
  document.body.appendChild(tip);

  function show(el, x, y) {
    tip.querySelector('b').textContent = el.dataset.tip || '';
    tip.querySelector('span').textContent = el.dataset.tipLabel || '';
    tip.hidden = false;
    const w = tip.offsetWidth;
    const h = tip.offsetHeight;
    const left = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2));
    const top = y - h - 12 < 8 ? y + 16 : y - h - 12;
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  document.addEventListener('pointermove', (e) => {
    const el = e.target.closest?.('[data-tip]');
    if (!el) { tip.hidden = true; return; }
    show(el, e.clientX, e.clientY);
  }, { passive: true });
  document.addEventListener('focusin', (e) => {
    const el = e.target.closest?.('[data-tip]');
    if (!el) return;
    const r = el.getBoundingClientRect();
    show(el, r.left + r.width / 2, r.top);
  });
  document.addEventListener('focusout', () => { tip.hidden = true; });
  window.addEventListener('scroll', () => { tip.hidden = true; }, { passive: true });

  /* Подарок: поле кодов — только для вида «Код». */
  document.querySelectorAll('[data-gift-kind]').forEach((select) => {
    const form = select.form;
    const sync = () => {
      const codes = form.querySelector('[data-gift-codes]');
      if (codes) codes.hidden = select.value !== 'code';
    };
    select.addEventListener('change', sync);
    sync();
  });

  /* Тайник: для игры — сцена, для сайта — адрес страницы. */
  document.querySelectorAll('[data-spot-page]').forEach((select) => {
    const form = select.form;
    const sync = () => {
      const unity = select.value === 'unity';
      const scene = form.querySelector('[data-spot-scene]');
      const path = form.querySelector('[data-spot-path]');
      if (scene) scene.hidden = !unity;
      if (path) path.hidden = unity;
    };
    select.addEventListener('change', sync);
    sync();
  });
})();
