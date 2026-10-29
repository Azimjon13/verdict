/* For screenshots: show what appears on scroll, hide what the URL hash lists (#.a,.b), and stay at the top. */
(async () => {
  await new Promise((r) => setTimeout(r, 300));
  const hide = (location.hash.slice(1) || '').split(',').filter(Boolean);
  hide.forEach((sel) => document.querySelectorAll(sel).forEach((el) => { el.style.display = 'none'; }));
  document.querySelectorAll('.reveal').forEach((el) => el.classList.add('is-visible'));
  window.scrollTo(0, 0);
})();
