/* VERDICT — фильтры архива дел. */
(() => {
  'use strict';

  const grid = document.querySelector('[data-case-grid]');
  if (!grid) return;

  const empty = document.querySelector('[data-empty]');
  const catButtons = document.querySelectorAll('[data-filter-cat]');
  const typeButtons = document.querySelectorAll('[data-filter-type]');
  const state = { cat: grid.dataset.initialCat || '', type: '' };

  function apply() {
    let shown = 0;
    grid.querySelectorAll('.case-card').forEach((card) => {
      const ok = (!state.cat || card.dataset.cat === state.cat) && (!state.type || card.dataset.type === state.type);
      card.hidden = !ok;
      if (ok) shown++;
    });
    if (empty) empty.hidden = shown > 0;
    catButtons.forEach((b) => b.classList.toggle('active', b.dataset.filterCat === state.cat));
    typeButtons.forEach((b) => b.classList.toggle('active', b.dataset.filterType === state.type));
  }

  catButtons.forEach((b) => b.addEventListener('click', () => {
    state.cat = b.dataset.filterCat;
    const url = new URL(window.location.href);
    if (state.cat) url.searchParams.set('category', state.cat); else url.searchParams.delete('category');
    history.replaceState(null, '', url);
    apply();
  }));

  typeButtons.forEach((b) => b.addEventListener('click', () => {
    state.type = b.dataset.filterType;
    apply();
  }));

  /* Сортировка карточек */
  const sortSelect = document.querySelector('[data-sort-select]');
  const num = (el, key) => Number(el.dataset[key]) || 0;
  const sorters = {
    order: (a, b) => num(a, 'id') - num(b, 'id'),
    open: (a, b) => num(a, 'done') - num(b, 'done') || num(a, 'id') - num(b, 'id'),
    heat: (a, b) => num(b, 'heat') - num(a, 'heat') || num(b, 'votes') - num(a, 'votes'),
    votes: (a, b) => num(b, 'votes') - num(a, 'votes') || num(a, 'id') - num(b, 'id'),
  };
  sortSelect?.addEventListener('change', () => {
    const cards = [...grid.querySelectorAll('.case-card')];
    cards.sort(sorters[sortSelect.value] || sorters.order).forEach((c) => grid.appendChild(c));
    try { localStorage.setItem('verdict.sort', sortSelect.value); } catch (_) { /* недоступно */ }
  });
  try {
    const saved = localStorage.getItem('verdict.sort');
    if (saved && sortSelect && sorters[saved] && saved !== sortSelect.value) {
      sortSelect.value = saved;
      sortSelect.dispatchEvent(new Event('change'));
    }
  } catch (_) { /* недоступно */ }

  apply();
})();
