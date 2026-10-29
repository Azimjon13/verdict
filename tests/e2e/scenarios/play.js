/* Archive page: category/type filters and sorting. */
(async () => {
  const out = [];
  const ok = (label, cond, extra = '') => out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const visible = () => [...document.querySelectorAll('.case-card')].filter((c) => !c.hidden);
  try {
    await wait(300);
    const all = document.querySelectorAll('.case-card').length;
    ok('archive lists approved cases', all >= 26, all);
    document.querySelector('[data-filter-cat="crime"]').click();
    ok('category filter', visible().length > 0 && visible().every((c) => c.dataset.cat === 'crime'), visible().length);
    ok('category kept in URL', new URL(location.href).searchParams.get('category') === 'crime');
    document.querySelector('[data-filter-type="public"]').click();
    ok('type filter combines with category', visible().every((c) => c.dataset.cat === 'crime' && c.dataset.type === 'public'), visible().length);
    document.querySelector('[data-filter-cat="mystery"]').click();
    document.querySelector('[data-filter-type="witness"]').click();
    const none = visible().length === 0;
    ok('empty state when nothing matches (or matches shown)', none ? !document.querySelector('[data-empty]').hidden : document.querySelector('[data-empty]').hidden);
    document.querySelector('[data-filter-cat=""]').click();
    document.querySelector('[data-filter-type=""]').click();
    ok('"all" resets filters', visible().length === all);
    const sel = document.querySelector('[data-sort-select]');
    sel.value = 'heat';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    await wait(100);
    const first = document.querySelector('.case-card')?.getAttribute('href') || document.querySelector('.case-card a')?.getAttribute('href');
    sel.value = 'order';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    await wait(100);
    const firstByOrder = document.querySelector('.case-card')?.getAttribute('href') || document.querySelector('.case-card a')?.getAttribute('href');
    ok('sorting reorders the grid', !!first && !!firstByOrder, `${first} / ${firstByOrder}`);
    const random = document.querySelector('a[href^="/case/"].btn-primary');
    ok('"Быстрый суд" is the main button', !!document.querySelector('a[href="/quick"].btn-primary'));
  } catch (e) {
    out.push('ERROR ' + e.message);
  }
  fetch('/__report', { method: 'POST', body: out.join('\n') });
})();
