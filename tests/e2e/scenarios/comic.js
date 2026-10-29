/* Drives the comic on /quick/5: frames, reveal, keys, dots, text mode, finish → verdict. */
(async () => {
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"stage":0,"out":[]}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const persist = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const finish = () => { persist(); fetch('/__report', { method: 'POST', body: st.out.join('\n') }); };
  const key = (k) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  try {
    await wait(400);
    const root = document.querySelector('[data-comic]');
    const panels = [...root.querySelectorAll('[data-cm-panel]')];
    const visibleIdx = () => panels.findIndex((p) => !p.hidden);
    const count = () => root.querySelector('[data-cm-count]').textContent;
    const next = root.querySelector('[data-cm-next]');
    const label = () => root.querySelector('[data-cm-next-label]').textContent;

    if (st.stage === 0) {
      ok('comic initialised', root.classList.contains('is-ready') && visibleIdx() === 0 && count() === `1 / ${panels.length}`, count());
      ok('only one frame visible', panels.filter((p) => !p.hidden).length === 1);
      ok('world frame shows role / place', !!panels[0].querySelector('.cm-place'));
      ok('frame kinds in order', panels[0].classList.contains('cm-world') && panels.at(-1).classList.contains('cm-decide')
        && !!root.querySelector('.cm-panel.cm-cast') && !!root.querySelector('.cm-panel.cm-evidence'));

      // Reveal sequence: right after showing, text appears step by step.
      next.click(); next.click(); // finish frame 1 reveal, go to frame 2
      await wait(50);
      const seq = panels[1].querySelectorAll('[data-seq]');
      const shownEarly = panels[1].querySelectorAll('[data-seq].in').length;
      ok('frame 2 reveals text gradually', visibleIdx() === 1 && shownEarly < seq.length && label() === 'Показать всё', `${shownEarly}/${seq.length}`);
      next.click();
      ok('"Показать всё" shows the whole frame', panels[1].querySelectorAll('[data-seq].in').length === seq.length && label() === 'Дальше');
      const figs = root.querySelector('[data-cm-figures="1"]');
      ok('characters of frame 2 on stage', !figs.hidden && figs.querySelectorAll('.cm-fig').length >= 1, figs.querySelectorAll('.cm-fig').length);
      ok('camera moved', root.querySelector('[data-cm-scene]').style.transform.includes('scale(1.08)'), root.querySelector('[data-cm-scene]').style.transform);

      // Keys.
      root.scrollIntoView();
      await wait(300);
      key('ArrowRight'); key('ArrowRight');
      ok('→ key goes forward', visibleIdx() === 2, count());
      key('ArrowLeft');
      ok('← key goes back', visibleIdx() === 1, count());

      // Dots.
      root.querySelectorAll('[data-cm-dot]')[panels.length - 2].click();
      ok('dot jumps to a frame', visibleIdx() === panels.length - 2, count());
      ok('previous dots marked done', root.querySelectorAll('.cm-dot.done').length === panels.length - 2);

      // Text mode (remembered).
      root.querySelector('[data-cm-mode]').click();
      ok('text mode shows every frame', root.classList.contains('is-text') && panels.every((p) => !p.hidden));
      ok('text mode shows all text', root.querySelectorAll('[data-seq]:not(.in)').length === 0);
      root.querySelector('[data-cm-mode]').click();
      ok('back to comic', !root.classList.contains('is-text') && panels.filter((p) => !p.hidden).length === 1);

      // Last frame → finish → verdict.
      root.querySelectorAll('[data-cm-dot]')[panels.length - 1].click();
      next.click();
      ok('last frame offers "К вердикту"', label() === 'К вердикту' && next.classList.contains('is-final'), label());
      next.click();
      await wait(900);
      const step = document.querySelector('[data-quick] [data-step="1"]');
      ok('finish scrolls to the verdict', Math.abs(step.getBoundingClientRect().top) < 400, Math.round(step.getBoundingClientRect().top));
      ok('first option focused', document.activeElement?.matches('[data-pick], .quick-cast *, button'), document.activeElement?.className);
      ok('cast strip above options', document.querySelectorAll('.quick-cast .qc').length >= 2);

      // Text mode persists across pages.
      root.querySelector('[data-cm-mode]').click();
      st.stage = 1; persist();
      location.reload();
      return;
    }
    if (st.stage === 1) {
      ok('text mode remembered after reload', root.classList.contains('is-text'));
      root.querySelector('[data-cm-mode]').click();
      finish();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    finish();
  }
})();
