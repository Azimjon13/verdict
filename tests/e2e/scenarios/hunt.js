/* Treasure hunt in a real browser: spots sit on their elements, finding them opens the gift, the badge counts,
 * the last spot brings the main prize. Runs over several pages (state in sessionStorage). */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"out":[],"step":0}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const save = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const report = () => fetch('/__report', { method: 'POST', body: st.out.join('\n') });
  const spots = () => [...document.querySelectorAll('.hunt-spot:not([hidden]):not(.is-gone)')];
  const centre = (el) => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; };
  const near = (a, b, tol = 2.5) => Math.abs(a.x - b.x) <= tol && Math.abs(a.y - b.y) <= tol;
  const modalOpen = () => document.querySelector('.modal-root') && !document.querySelector('.modal-root').hidden;
  const closeModal = async () => { document.querySelector('.modal-root [data-ok]')?.click(); await wait(400); };
  // The page settles after web fonts and appear-on-scroll animations (slower on CI); spots follow within ~1.5 s.
  const until = async (find, ms = 5000) => {
    for (const t0 = Date.now(); Date.now() - t0 < ms; await wait(100)) {
      const found = find();
      if (found) return found;
    }
    return find();
  };
  try {
    await wait(900);
    await document.fonts?.ready;
    if (st.step === 0 && location.pathname === '/') {
      const s = spots();
      ok('two spots on the home page (its own + the site-wide one)', s.length === 2, s.length);
      const want = () => { const h1 = document.querySelector('.hero h1').getBoundingClientRect(); return { x: h1.left + h1.width * 0.88, y: h1.top + h1.height * 0.85 }; };
      const home = await until(() => s.find((el) => near(centre(el), want())));
      ok('home spot sits at 88% × 85% of the title', !!home, s.map((el) => JSON.stringify(centre(el))).join(' ') + ' want ' + JSON.stringify(want()));
      ok('a «visible» spot is nearly opaque', home && Math.abs(parseFloat(getComputedStyle(home).opacity) - 0.9) < 0.01, home && getComputedStyle(home).opacity);
      const logo = s.find((el) => el !== home);
      ok('a «subtle» spot is faint', logo && Math.abs(parseFloat(getComputedStyle(logo).opacity) - 0.34) < 0.01, logo && getComputedStyle(logo).opacity);
      ok('spots are not in the Tab order', s.every((el) => el.tabIndex === -1));
      const badge = document.querySelector('[data-hunt-count]');
      ok('hunt badge shows 0/3', badge && badge.textContent === '0/3', badge && badge.textContent);
      document.querySelector('[data-hunt-badge] summary').click();
      await wait(200);
      ok('badge opens with hints', document.querySelector('[data-hunt-badge]').open && document.querySelectorAll('.hunt-hints li').length === 3);
      ok('time left is shown', /до конца 3 дн/.test(document.querySelector('.hunt-meta').textContent), document.querySelector('.hunt-meta').textContent);
      document.querySelector('[data-hunt-badge] summary').click();
      // scroll a bit: an absolutely placed spot must move with the page
      window.scrollTo(0, 120);
      await wait(300);
      const h1b = document.querySelector('.hero h1').getBoundingClientRect();
      ok('spot stays on the title after scrolling', near(centre(home), { x: h1b.left + h1b.width * 0.88, y: h1b.top + h1b.height * 0.85 }));
      window.scrollTo(0, 0);
      await wait(300);
      home.click();
      await wait(1200);
      ok('finding opens the gift window', modalOpen() && /Вы нашли тайник/.test(document.querySelector('.modal-title').textContent));
      const text = document.querySelector('.modal-text')?.textContent || '';
      ok('the window shows the gift and the XP', /\+50 XP за зоркость/.test(text) && /\+50 XP/.test(text) && /найдено 1 из 3/.test(text), text.slice(0, 160));
      ok('the found spot leaves the page', spots().length === 1);
      ok('badge counts 1/3', document.querySelector('[data-hunt-count]').textContent === '1/3');
      ok('its hint is marked found', document.querySelector('.hunt-hints li.is-found')?.textContent.includes('Найден: +50 XP'));
      await closeModal();
      st.step = 1;
      save();
      location.href = '/play';
      return;
    }
    if (st.step === 1 && location.pathname === '/play') {
      const s = spots();
      const want = () => { const f = document.querySelector('.filters').getBoundingClientRect(); return { x: f.left + f.width * 0.97, y: f.top + f.height * 0.5 }; };
      const play = await until(() => s.find((el) => near(centre(el), want())));
      ok('archive spot sits on the filters', !!play, s.map((el) => JSON.stringify(centre(el))).join(' '));
      play.click();
      await wait(1200);
      const text = document.querySelector('.modal-text')?.textContent || '';
      ok('a code gift shows its own code', /TEE-[A-Z0-9]{4}/.test(text) && /Покажите код/.test(text), text.slice(0, 160));
      ok('copy button is there', !!document.querySelector('.modal-text [data-copy]'));
      await closeModal();
      const logo = spots()[0];
      ok('site-wide spot is on this page too', !!logo);
      logo.click();
      await wait(1200);
      const last = document.querySelector('.modal-text')?.textContent || '';
      ok('the last spot brings the main prize', /Все тайники найдены/.test(last) && /Искатель тайников/.test(last), last.slice(0, 200));
      ok('a spot without a gift still counts', /найдено 3 из 3/.test(last));
      await closeModal();
      ok('badge counts 3/3', document.querySelector('[data-hunt-count]').textContent === '3/3');
      st.step = 2;
      save();
      location.href = '/judge';
      return;
    }
    if (st.step === 2 && location.pathname === '/judge') {
      ok('judge page shows the title', document.querySelector('.cp-title')?.textContent.includes('Искатель тайников'));
      ok('judge page lists three gifts', document.querySelectorAll('#gifts .gift-card').length === 3, document.querySelectorAll('#gifts .gift-card').length);
      ok('XP counts the gifts (50 + 10 + 25)', /85 XP/.test(document.querySelector('.cp-next').textContent), document.querySelector('.cp-next').textContent);
      ok('no spots left anywhere', spots().length === 0);
      ok('no horizontal page scroll', document.documentElement.scrollWidth <= document.documentElement.clientWidth);
      st.step = 3;
      save();
      report();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    report();
  }
})();
