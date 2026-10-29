/* Phone width: the main pages, one by one in a 360 px frame on /__phone (headless Chrome won't make its window
 * narrower than ~500 px), signed in as the team so the header is at its fullest. A page passes when no text, link or
 * button sticks out past the right edge, unless a scroll box inside the screen holds it (wide tables, chip rows). */
(async () => {
  if (window.top !== window) return;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = [];
  const ok = (label, cond, extra = '') => out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  const seed = window.__e2e.seed;
  const pages = ['/', '/quick', '/case/3', '/play', '/judge', '/ratings', '/campaigns', '/campaign/rubezh', '/communities',
    '/friends', '/account', '/create', '/library', '/admin/', '/admin/players', '/admin/hunts/' + seed.hunt, '/admin/gifts', '/admin/game'];
  const frame = document.getElementById('phone');
  const describe = (el) => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')
    + ' «' + (el.textContent || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 30) + '»';
  try {
    for (const path of pages) {
      await new Promise((resolve) => { frame.onload = resolve; frame.src = path; });
      await wait(900);
      const doc = frame.contentDocument;
      const view = frame.contentWindow;
      doc.querySelectorAll('.reveal').forEach((el) => el.classList.add('is-visible'));
      await wait(300);
      const width = doc.documentElement.clientWidth;
      const clippedInside = (el) => {
        for (let a = el.parentElement; a && a !== doc.body; a = a.parentElement) {
          const s = view.getComputedStyle(a);
          if (s.overflowX !== 'visible' && a.getBoundingClientRect().right <= width + 1) return true;
          if (s.position === 'fixed' && s.visibility === 'hidden') return true;
        }
        return false;
      };
      const offenders = [...doc.body.querySelectorAll('a, button, input, select, textarea, label, h1, h2, h3, p, li, td, th, span, b, strong, small, code')]
        .filter((el) => {
          if (el.closest('[hidden], [aria-hidden="true"], .hunt-spot, .toasts')) return false;
          const s = view.getComputedStyle(el);
          if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
          const r = el.getBoundingClientRect();
          if (!r.width || !r.height || r.right <= width + 1) return false;
          const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || el.matches('a, button, input, select, textarea');
          return hasText && !clippedInside(el);
        })
        .filter((el, _, all) => !all.some((o) => o !== el && o.contains(el)));
      ok(path + ' fits ' + width + ' px', doc.documentElement.scrollWidth <= width && offenders.length === 0,
        offenders.slice(0, 4).map((el) => describe(el) + ' →' + Math.round(el.getBoundingClientRect().right)).join('; '));
    }
  } catch (e) {
    out.push('ERROR ' + e.message);
  }
  fetch('/__report', { method: 'POST', body: out.join('\n') });
})();
