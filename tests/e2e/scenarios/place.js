/* The team places a spot by clicking on a page, then checks it in preview: the spot lands where the click was. */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"out":[],"step":0}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const save = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const report = () => fetch('/__report', { method: 'POST', body: st.out.join('\n') });
  try {
    await wait(900);
    const params = new URLSearchParams(location.search);
    if (st.step === 0 && params.get('hunt_place')) {
      const bar = document.querySelector('.hunt-tools');
      ok('placement bar is shown', !!bar && /Где спрятать/.test(bar.textContent), bar && bar.textContent.trim().slice(0, 80));
      ok('no live spots while placing', !document.querySelector('.hunt-spot'));
      ok('existing spots of the hunt are marked', document.querySelectorAll('.hunt-mark:not(.is-ghost)').length >= 1);
      const target = document.querySelector('.hero .hero-actions .btn');
      const r = target.getBoundingClientRect();
      const x = r.left + r.width * 0.25;
      const y = r.top + r.height * 0.5;
      document.dispatchEvent(new MouseEvent('mousemove', { clientX: x, clientY: y, bubbles: true }));
      await wait(100);
      const box = document.querySelector('.hunt-target');
      ok('hovered element is outlined (the button, not its icon)', box && !box.hidden && Math.abs(parseFloat(box.style.width) - r.width) < 1.5, box && box.style.width);
      st.click = { selectorOf: 'hero-actions btn', fx: 0.25, fy: 0.5 };
      save();
      const el = document.elementFromPoint(x, y);
      el.dispatchEvent(new MouseEvent('click', { clientX: x, clientY: y, bubbles: true, cancelable: true }));
      st.step = 1;
      save();
      await wait(4000);
      ok('page navigated to the spot after saving', false, location.href);
      report();
      return;
    }
    if (st.step === 1 && location.pathname.startsWith('/admin/spots/')) {
      const flash = [...document.querySelectorAll('.toast span')].map((s) => s.textContent).join(' ');
      ok('saved with a message', /Тайник размещён/.test(flash), flash);
      const note = document.querySelector('#place .admin-note code')?.textContent || '';
      ok('the spot remembers its element', /a/.test(note) && note.includes('nth-of-type') || note.length > 5, note);
      st.step = 2;
      save();
      location.href = '/?hunt_preview=' + window.__e2e.seed.draft_hunt;
      return;
    }
    if (st.step === 2 && params.get('hunt_preview')) {
      await wait(1500); // let the page's appear-on-scroll animations finish
      const bar = document.querySelector('.hunt-tools');
      ok('preview bar is shown', !!bar && /Предпросмотр/.test(bar.textContent));
      const target = document.querySelector('.hero .hero-actions .btn');
      const r = target.getBoundingClientRect();
      const want = { x: r.left + r.width * 0.25 + window.scrollX, y: r.top + r.height * 0.5 + window.scrollY };
      const marks = [...document.querySelectorAll('.hunt-mark.is-preview')];
      const found = marks.find((m) => Math.abs(parseFloat(m.style.left) - want.x) < 2 && Math.abs(parseFloat(m.style.top) - want.y) < 2);
      ok('the spot is where the team clicked', !!found, marks.map((m) => m.style.left + ',' + m.style.top + ' ' + m.textContent).join(' | ') + ' want ' + JSON.stringify(want));
      ok('marks carry their labels', marks.every((m) => m.querySelector('small').textContent.length > 0));
      st.step = 3;
      save();
      report();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    report();
  }
})();
