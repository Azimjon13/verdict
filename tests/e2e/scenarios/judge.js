/* Judge profile page in a real browser: tooltip on focus, table view, emblem, layout. */
(async () => {
  const out = [];
  const ok = (label, cond, extra = '') => out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    await wait(400);
    ok('profile shown', !!document.querySelector('.judge-card h2'), document.querySelector('.judge-card h2')?.textContent);
    const rows = [...document.querySelectorAll('.jd-row')];
    ok('five metric rows', rows.length === 5);
    const tip = rows[4].querySelector('.jd-tip');
    ok('tooltip hidden by default', getComputedStyle(tip).opacity === '0');
    tip.style.transition = 'none'; // headless windows don't reliably advance CSS transitions
    rows[4].focus();
    await wait(300);
    ok('tooltip shows on keyboard focus', getComputedStyle(tip).opacity === '1');
    ok('tooltip leads with the value', /^[+−]\d+%/.test(tip.querySelector('b')?.textContent || ''), tip.querySelector('b')?.textContent);
    ok('row describes itself via the tooltip', rows[4].getAttribute('aria-describedby') === tip.id);
    rows[4].blur();
    // Bars: direction matches the sign of the label.
    const consistent = rows.every((r) => {
      const v = r.querySelector('.jd-value').textContent.trim();
      const bar = r.querySelector('.jd-bar');
      if (v === '—' || v === '0%') return !bar || bar.offsetWidth < 2;
      return bar && bar.classList.contains(v.startsWith('+') ? 'up' : 'down');
    });
    ok('every bar points the way its label says', consistent);
    const up = document.querySelector('.jd-bar.up');
    const down = document.querySelector('.jd-bar.down');
    ok('bars use the validated diverging colours', (!up || getComputedStyle(up).backgroundColor === 'rgb(57, 135, 229)') && (!down || getComputedStyle(down).backgroundColor === 'rgb(217, 89, 38)'));
    ok('bars are thin (≤ 24px)', [...document.querySelectorAll('.jd-bar')].every((b) => b.offsetHeight <= 24));
    const table = document.querySelector('.jd-table');
    table.querySelector('summary').click();
    ok('table view opens', table.open && table.querySelectorAll('tbody tr').length === 5);
    const emblemPaths = document.querySelectorAll('.judge-card .jd-emblem path').length;
    ok('mercy emblem is a whole heart (single path)', document.querySelector('.judge-card h2')?.textContent !== 'Милосердный судья' || emblemPaths === 1, emblemPaths);
    ok('no horizontal page scroll', document.documentElement.scrollWidth <= document.documentElement.clientWidth);
  } catch (e) {
    out.push('ERROR ' + e.message);
  }
  fetch('/__report', { method: 'POST', body: out.join('\n') });
})();
