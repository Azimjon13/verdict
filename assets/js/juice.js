/* VERDICT — «сок» игры: штамп вердикта, удар молотка, счётчики, полёт опыта, конфетти, печатающийся текст, звук.
 *
 *   Juice.verdict(el)         — штамп «ВЕРДИКТ» на выбранном варианте, молоток, вибрация
 *   Juice.strike(el)          — молоток и встряска экрана (кнопка-удержание в полном деле)
 *   Juice.result(root, kind)  — оживить вставленный результат: проценты, опыт, ранг, достижения, последствия
 *   Juice.burst(x, y, opts)   — конфетти в точке экрана
 *   Juice.sound               — { enabled, set(on), gavel(), win(), miss(), rankUp(), chime() }
 *
 * Звук синтезируется в браузере (файлов нет) и запоминается выключенным в localStorage.
 * При prefers-reduced-motion остаются только звук и конечные значения — без движения.
 */
(() => {
  'use strict';

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches || document.documentElement.dataset.fx === 'lite';
  const KEY = 'verdict:sound';

  /* ---------- Звук ---------- */
  const sound = (() => {
    let ctx = null;
    let enabled = true;
    try { enabled = localStorage.getItem(KEY) !== 'off'; } catch (_) { /* приватный режим */ }

    function ac() {
      if (!ctx) {
        const C = window.AudioContext || window.webkitAudioContext;
        if (!C) return null;
        ctx = new C();
      }
      if (ctx.state === 'suspended') ctx.resume().catch(() => {});
      return ctx;
    }
    function tone(freq, { type = 'sine', t = 0, dur = .18, gain = .07, slide = 0 } = {}) {
      const c = ac();
      if (!c) return;
      const o = c.createOscillator();
      const g = c.createGain();
      const now = c.currentTime + t;
      o.type = type;
      o.frequency.setValueAtTime(freq, now);
      if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(30, freq + slide), now + dur);
      g.gain.setValueAtTime(.0001, now);
      g.gain.exponentialRampToValueAtTime(gain, now + .012);
      g.gain.exponentialRampToValueAtTime(.0001, now + dur);
      o.connect(g).connect(c.destination);
      o.start(now);
      o.stop(now + dur + .05);
    }
    function knock(t = 0, dur = .07, gain = .3) {
      const c = ac();
      if (!c) return;
      const buf = c.createBuffer(1, Math.floor(c.sampleRate * dur), c.sampleRate);
      const d = buf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length) ** 2;
      const s = c.createBufferSource();
      s.buffer = buf;
      const f = c.createBiquadFilter();
      f.type = 'lowpass';
      f.frequency.value = 700;
      const g = c.createGain();
      g.gain.value = gain;
      s.connect(f).connect(g).connect(c.destination);
      s.start(c.currentTime + t);
    }
    const play = (fn) => { if (!enabled) return; try { fn(); } catch (_) { /* без звука — не беда */ } };
    const run = (notes, dur = .22, gap = .08, gain = .055) => () => notes.forEach((f, i) => tone(f, { t: i * gap, dur, gain }));
    return {
      get enabled() { return enabled; },
      set(on) {
        enabled = on;
        try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch (_) { /* приватный режим */ }
        if (on) play(() => tone(660, { dur: .12, gain: .05 }));
      },
      gavel() { play(() => { knock(0, .08, .35); tone(150, { type: 'triangle', dur: .18, gain: .16, slide: -100 }); knock(.14, .06, .22); tone(125, { type: 'triangle', t: .14, dur: .16, gain: .12, slide: -80 }); }); },
      win() { play(run([523, 659, 784, 1047])); },
      miss() { play(() => { tone(330, { type: 'triangle', dur: .22, gain: .06 }); tone(262, { type: 'triangle', t: .15, dur: .32, gain: .06 }); }); },
      rankUp() { play(run([392, 523, 659, 784, 1047, 1319], .32, .07)); },
      chime() { play(() => { tone(880, { dur: .2, gain: .05 }); tone(1320, { t: .1, dur: .26, gain: .045 }); }); },
    };
  })();

  const haptic = (pattern) => { try { navigator.vibrate?.(pattern); } catch (_) { /* нет вибрации */ } };
  const centre = (el) => { const r = el.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; };

  /* ---------- Конфетти ---------- */
  const COLORS = ['#00e5ff', '#8b5cf6', '#ff2bd6', '#ffb547', '#2dffa8', '#ffffff'];
  let canvas = null, c2d = null, parts = [], raf = 0, last = 0;

  function burst(x, y, { count = 70, power = 1, colors = COLORS } = {}) {
    if (reduce) return;
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.className = 'juice-canvas';
      canvas.setAttribute('aria-hidden', 'true');
      document.body.appendChild(canvas);
      c2d = canvas.getContext('2d');
    }
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    canvas.style.width = `${innerWidth}px`;
    canvas.style.height = `${innerHeight}px`;
    c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = (4 + Math.random() * 7) * power;
      parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 6 * power, r: 3 + Math.random() * 4, rot: Math.random() * 6,
        vr: (Math.random() - .5) * .4, life: 1, decay: .012 + Math.random() * .012, color: colors[i % colors.length], shape: i % 3 });
    }
    if (!raf) {
      last = performance.now();
      raf = requestAnimationFrame(step);
    }
  }

  function step(now) {
    const dt = Math.min(2.5, (now - last) / 16.7);
    last = now;
    c2d.clearRect(0, 0, innerWidth, innerHeight);
    parts = parts.filter((p) => p.life > 0);
    for (const p of parts) {
      p.vy += .32 * dt;
      p.vx *= .985;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vr * dt;
      p.life -= p.decay * dt;
      c2d.save();
      c2d.globalAlpha = Math.max(0, Math.min(1, p.life * 1.4));
      c2d.translate(p.x, p.y);
      c2d.rotate(p.rot);
      c2d.fillStyle = p.color;
      if (p.shape === 0) c2d.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
      else if (p.shape === 1) { c2d.beginPath(); c2d.arc(0, 0, p.r / 1.6, 0, Math.PI * 2); c2d.fill(); }
      else { c2d.beginPath(); c2d.moveTo(0, -p.r); c2d.lineTo(p.r, p.r); c2d.lineTo(-p.r, p.r); c2d.closePath(); c2d.fill(); }
      c2d.restore();
    }
    raf = parts.length ? requestAnimationFrame(step) : 0;
    if (!raf) c2d.clearRect(0, 0, innerWidth, innerHeight);
  }

  /* ---------- Числа, полёты, печать ---------- */
  function countUp(el, { duration = 900, delay = 0 } = {}) {
    const m = /^([+\-−]?)(\d+)(.*)$/s.exec(el.textContent.trim());
    if (!m || el.dataset.counted) return;
    el.dataset.counted = '1';
    const [, sign, num, suffix] = m;
    const to = Number(num);
    if (reduce || to === 0) return;
    const t0 = performance.now() + delay;
    el.textContent = `${sign}0${suffix}`;
    const tick = (now) => {
      const k = Math.min(1, Math.max(0, (now - t0) / duration));
      const e = 1 - (1 - k) ** 3;
      el.textContent = `${sign}${Math.round(to * e)}${suffix}`;
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function floatUp(el, text, tone = 'up') {
    if (reduce) return;
    const [x, y] = centre(el);
    const f = document.createElement('span');
    f.className = `juice-float ${tone}`;
    f.textContent = text;
    f.style.left = `${x}px`;
    f.style.top = `${y}px`;
    document.body.appendChild(f);
    setTimeout(() => f.remove(), 1200);
  }

  function bump(el) {
    el.classList.remove('is-bumped');
    void el.offsetWidth;
    el.classList.add('is-bumped');
    setTimeout(() => el.classList.remove('is-bumped'), 600);
  }

  /* +N XP летит к чипу ранга в шапке страницы и прибавляется к его числу. */
  function flyTo(from, to, text) {
    const gained = Number((/\+?(\d+)/.exec(text) || [])[1]) || 0;
    const arrive = () => {
      bump(to);
      const b = to.querySelector('b');
      const m = b && /^(\d+) XP$/.exec(b.textContent.trim());
      if (m && gained) b.textContent = `${Number(m[1]) + gained} XP`;
    };
    if (reduce) { arrive(); return; }
    const [x0, y0] = centre(from);
    const [x1, y1] = centre(to);
    const t = document.createElement('span');
    t.className = 'juice-fly';
    t.textContent = text;
    t.style.left = `${x0}px`;
    t.style.top = `${y0}px`;
    document.body.appendChild(t);
    const anim = t.animate([
      { transform: 'translate(0, 0) scale(1)', opacity: 1 },
      { transform: `translate(${(x1 - x0) * .5}px, ${(y1 - y0) * .5 - 60}px) scale(1.1)`, opacity: 1, offset: .5 },
      { transform: `translate(${x1 - x0}px, ${y1 - y0}px) scale(.6)`, opacity: .9 },
    ], { duration: 750, easing: 'cubic-bezier(.3, .7, .3, 1)' });
    anim.onfinish = () => { t.remove(); arrive(); };
  }

  function typewriter(el, delay = 0) {
    if (reduce || el.dataset.typed || el.textContent.length > 400) return;
    el.dataset.typed = '1';
    const full = el.textContent;
    const perTick = full.length > 160 ? 2 : 1;
    let i = 0, timer = 0;
    el.textContent = '';
    el.classList.add('juice-typing');
    const finish = () => { clearInterval(timer); el.textContent = full; el.classList.remove('juice-typing'); };
    el.addEventListener('click', finish, { once: true });
    setTimeout(() => {
      timer = setInterval(() => {
        i += perTick;
        el.textContent = full.slice(0, i);
        if (i >= full.length) finish();
      }, 18);
    }, delay);
  }

  /* ---------- Вердикт ---------- */
  function stamp(el, text = 'Вердикт') {
    const scope = el.closest('.quick-options, form, .quick-steps') || el.parentElement;
    scope?.querySelectorAll('.juice-stamp').forEach((s) => s.remove());
    scope?.querySelectorAll('.is-stamped').forEach((s) => s.classList.remove('is-stamped'));
    const s = document.createElement('span');
    s.className = 'juice-stamp';
    s.textContent = text;
    el.appendChild(s);
    el.classList.add('is-stamped');
  }

  function verdict(el) {
    stamp(el);
    sound.gavel();
    haptic([25]);
  }

  function strike(el) {
    sound.gavel();
    haptic([30, 40, 60]);
    if (reduce) return;
    const main = document.getElementById('main') || document.body;
    main.classList.remove('is-struck');
    void main.offsetWidth;
    main.classList.add('is-struck');
    setTimeout(() => main.classList.remove('is-struck'), 450);
    if (el) bump(el);
  }

  function result(root) {
    if (!root) return;
    root.querySelectorAll('.dist-top b, [data-quick-score]').forEach((el, i) => countUp(el, { delay: 250 + i * 70 }));
    const strip = root.querySelector('.career-strip');
    const win = root.querySelector('.guess-win');
    const miss = root.querySelector('.guess-miss');
    if (strip?.classList.contains('is-rank-up')) {
      setTimeout(() => { burst(...centre(strip), { count: 120, power: 1.2 }); sound.rankUp(); haptic([20, 30, 20, 30, 60]); }, 500);
    } else if (win) {
      sound.win();
      haptic([15, 30, 15]);
    } else if (miss) {
      sound.miss();
    } else {
      sound.chime();
    }
    root.querySelectorAll('.ach-chip.is-new').forEach((chip, i) => {
      setTimeout(() => burst(...centre(chip), { count: 40, power: .7, colors: ['#ffb547', '#ffe2b0', '#ffffff'] }), 900 + i * 250);
    });
    const news = root.querySelector('.world-news');
    if (news && !reduce) setTimeout(() => window.VerdictFX?.shockwave?.(...centre(news), 1), 700);
    const xp = root.querySelector('.cs-xp');
    if (xp) {
      const text = xp.textContent.trim();
      const target = document.querySelector('.rank-chip');
      setTimeout(() => (target ? flyTo(xp, target, text) : floatUp(xp, text)), 350);
      countUp(xp, { delay: 300 });
    }
    root.querySelectorAll('.cs-bar i').forEach((bar) => fill(bar));
    const conseq = root.querySelector('.quick-conseq');
    if (conseq) typewriter(conseq, 700);
  }

  function fill(bar) {
    if (reduce) return;
    const w = bar.style.width;
    bar.style.transition = 'none';
    bar.style.width = '0%';
    requestAnimationFrame(() => requestAnimationFrame(() => {
      bar.style.transition = 'width 1.1s cubic-bezier(.2, .8, .2, 1)';
      bar.style.width = w;
    }));
  }

  /* ---------- На каждой странице ---------- */
  function init() {
    // Кнопка звука в шапке
    const toggles = [...document.querySelectorAll('[data-sound-toggle]')];
    const paint = () => toggles.forEach((btn) => {
      btn.classList.toggle('is-off', !sound.enabled);
      btn.setAttribute('aria-pressed', sound.enabled ? 'true' : 'false');
      btn.title = sound.enabled ? 'Звук включён' : 'Звук выключен';
    });
    paint();
    toggles.forEach((btn) => btn.addEventListener('click', () => { sound.set(!sound.enabled); paint(); }));

    // Кампания: штамп и молоток перед отправкой вердикта
    document.querySelectorAll('[data-verdict-form]').forEach((form) => {
      let armed = false;
      form.addEventListener('submit', (e) => {
        if (armed || reduce) return;
        const btn = e.submitter;
        if (!btn || !btn.classList.contains('option')) return;
        e.preventDefault();
        armed = true;
        verdict(btn);
        form.querySelectorAll('button').forEach((b) => { b.disabled = b !== btn; });
        setTimeout(() => form.requestSubmit(btn), 520);
      });
    });

    // Таймер дела дня
    document.querySelectorAll('[data-countdown]').forEach((el) => {
      const start = Date.now();
      const total = Number(el.dataset.countdown) || 0;
      const paint = () => {
        const left = Math.max(0, total - Math.round((Date.now() - start) / 1000));
        el.textContent = `${Math.floor(left / 3600)} ч ${Math.floor((left % 3600) / 60)} мин`;
      };
      setInterval(paint, 20000);
    });

    // Подсветка варианта под курсором
    document.addEventListener('pointermove', (e) => {
      const opt = e.target.closest?.('.option');
      if (!opt) return;
      const r = opt.getBoundingClientRect();
      opt.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`);
      opt.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`);
    }, { passive: true });

    // Финал кампании и полоски ранга на странице судьи
    const ending = document.querySelector('.camp-ending');
    if (ending) setTimeout(() => { burst(...centre(ending), { count: 140, power: 1.3 }); haptic([20, 30, 20, 30, 60]); }, 400);
    document.querySelectorAll('.cp-bar i').forEach((bar) => fill(bar));

    // Подарок из тайника и другие окна с «новым»
    new MutationObserver(() => {
      document.querySelectorAll('.gift-card.is-new:not([data-juiced])').forEach((card) => {
        card.dataset.juiced = '1';
        setTimeout(() => { burst(...centre(card), { count: 80, colors: ['#ffb547', '#ffe2b0', '#00e5ff', '#ffffff'] }); sound.chime(); haptic([15, 40, 25]); }, 350);
      });
    }).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  window.Juice = { verdict, strike, result, burst, floatUp, countUp, sound };
})();
