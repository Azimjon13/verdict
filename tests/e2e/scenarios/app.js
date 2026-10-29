/* The installable app in a real browser: the service worker takes the whole site, keeps the offline page and the
 * styles in its cache, and the manifest with its icons loads. */
(async () => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const out = [];
  const ok = (label, cond, extra = '') => out.push((cond ? 'PASS ' : 'FAIL ') + label + (extra !== '' ? '  [' + extra + ']' : ''));
  try {
    const reg = await Promise.race([navigator.serviceWorker.ready, wait(10000).then(() => null)]);
    ok('the service worker is active for the whole site', !!reg && reg.scope === location.origin + '/' && /\/sw\.js$/.test(reg.active?.scriptURL || ''),
      reg && reg.scope);
    await wait(500);
    const offline = await caches.match('/offline');
    ok('the offline page is kept', !!offline && /Нет связи/.test(await offline.text()));
    const keys = await caches.keys();
    ok('one cache, named by version', keys.length === 1 && /^verdict-\d+$/.test(keys[0]), keys.join());
    if (!navigator.serviceWorker.controller) {  // the first page comes under the worker once it claims it
      await Promise.race([new Promise((r) => navigator.serviceWorker.addEventListener('controllerchange', r, { once: true })), wait(5000)]);
    }
    ok('it serves this page now', !!navigator.serviceWorker.controller);
    await fetch(document.querySelector('link[rel="stylesheet"][href^="/assets/"]').href);
    await wait(400);  // the worker stores a copy right after answering
    const cached = await (await caches.open(keys[0])).keys();
    ok('styles are cached after use', cached.some((r) => /\/assets\/css\/style\.css/.test(r.url)), cached.length);
    ok('pages are not cached', !cached.some((r) => new URL(r.url).pathname === '/play'));
    const manifest = await (await fetch(document.querySelector('link[rel="manifest"]').href)).json();
    ok('the manifest names the app', manifest.short_name === 'VERDICT' && manifest.display === 'standalone');
    const img = new Image();
    img.src = manifest.icons.find((i) => i.sizes === '512x512').src;
    await img.decode();
    ok('its 512 px icon loads', img.naturalWidth === 512 && img.naturalHeight === 512);
  } catch (e) {
    out.push('ERROR ' + e.message);
  }
  fetch('/__report', { method: 'POST', body: out.join('\n') });
})();
