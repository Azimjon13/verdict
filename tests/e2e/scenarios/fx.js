/* «Меньше эффектов»: the footer switch turns off the moving background, blur and animations (remembered across pages),
 * and turns them back on. */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const st = JSON.parse(sessionStorage.getItem('e2e') || '{"out":[],"step":0}');
  const ok = (label, cond, extra = '') => st.out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const save = () => sessionStorage.setItem('e2e', JSON.stringify(st));
  const report = () => fetch('/__report', { method: 'POST', body: st.out.join('\n') });
  const html = document.documentElement;
  const aurora = () => getComputedStyle(document.querySelector('.bg-aurora')).display;
  const blur = () => getComputedStyle(document.querySelector('.site-header')).backdropFilter;
  try {
    await wait(500);
    const toggle = document.querySelector('.footer-fx[data-fx-toggle]');
    if (st.step === 0) {
      ok('full effects by default', !html.dataset.fx && aurora() !== 'none' && blur() !== 'none', blur());
      ok('the footer offers fewer effects', toggle && /Меньше эффектов/.test(toggle.innerText), toggle && toggle.innerText);
      st.step = 1;
      save();
      toggle.click(); // reloads
      return;
    }
    if (st.step === 1) {
      ok('the page came back with fewer effects', html.dataset.fx === 'lite' && localStorage.getItem('verdict:fx') === 'lite');
      ok('no moving glow and no blur', aurora() === 'none' && blur() === 'none', aurora() + ' / ' + blur());
      ok('appear-on-scroll blocks are simply there', [...document.querySelectorAll('.reveal')].every((el) => getComputedStyle(el).opacity === '1'));
      ok('the switch now offers all effects', /Включить все эффекты/.test(toggle.innerText) && toggle.getAttribute('aria-pressed') === 'true');
      st.step = 2;
      save();
      location.href = '/quick';
      return;
    }
    if (st.step === 2) {
      ok('remembered on the next page', html.dataset.fx === 'lite' && aurora() === 'none');
      st.step = 3;
      save();
      toggle.click();
      return;
    }
    if (st.step === 3) {
      ok('all effects are back', !html.dataset.fx && aurora() !== 'none' && localStorage.getItem('verdict:fx') === 'full');
      report();
    }
  } catch (e) {
    st.out.push('ERROR ' + e.message);
    report();
  }
})();
