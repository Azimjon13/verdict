/* VERDICT — игровой фон: неоновое солнце, горы, сетка-пол, созвездия, искры, ударные волны. */
(() => {
  'use strict';

  const canvas = document.getElementById('bg-canvas');
  if (!canvas || !canvas.getContext) return;

  const ctx = canvas.getContext('2d');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const calm = document.body.dataset.bg === 'calm';

  const C = {
    cyan: [0, 229, 255],
    magenta: [255, 43, 214],
    violet: [139, 92, 246],
    amber: [255, 181, 71],
  };
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const rand = (a, b) => a + Math.random() * (b - a);

  let W = 0, H = 0, DPR = 1, horizon = 0, baseHorizon = 0;
  let stars = [], nodes = [], sparks = [], streaks = [], waves = [], ridges = [];
  let sunCanvas = null, sunR = 0;
  let offset = 0, boost = 0, flash = 0, nextStreak = 0, running = false, raf = 0, last = 0;
  const mouse = { x: -9999, y: -9999, tx: .5, ty: .5, px: .5, py: .5 };

  /* ---------- построение сцены ---------- */

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 1.5);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    baseHorizon = H * (calm ? .7 : .62);
    horizon = baseHorizon;
    build();
  }

  function build() {
    const area = W * H;
    stars = Array.from({ length: Math.round(Math.min(280, area / 5200)) }, () => ({
      x: Math.random() * W,
      y: Math.random() * baseHorizon,
      r: rand(.2, 1.4),
      p: Math.random() * Math.PI * 2,
      s: rand(.01, .04),
    }));
    nodes = Array.from({ length: Math.round(Math.min(calm ? 46 : 78, area / 17000)) }, newNode);
    ridges = [makeRidge(.085, 34), makeRidge(.05, 48)];
    buildSun();
  }

  function newNode() {
    const roll = Math.random();
    return {
      x: Math.random() * W,
      y: Math.random() * Math.max(80, baseHorizon - 30),
      vx: rand(-.25, .25),
      vy: rand(-.2, .2),
      r: rand(.8, 2.1),
      c: roll < .6 ? C.cyan : roll < .85 ? C.violet : C.magenta,
    };
  }

  function makeRidge(maxH, count) {
    const pts = [];
    for (let i = 0; i <= count; i++) {
      const x = i / count;
      const side = Math.min(1, Math.abs(x - .5) * 2.3); // в центре ниже — видно солнце
      pts.push([x, rand(.35, 1) * maxH * (.12 + .88 * side)]);
    }
    return pts;
  }

  function buildSun() {
    sunR = Math.max(70, Math.min(W, H) * (calm ? .15 : .2));
    const size = Math.ceil(sunR * 2 + 4);
    sunCanvas = document.createElement('canvas');
    sunCanvas.width = Math.round(size * DPR);
    sunCanvas.height = Math.round(size * DPR);
    const g = sunCanvas.getContext('2d');
    g.scale(DPR, DPR);
    const grad = g.createLinearGradient(0, 0, 0, size);
    grad.addColorStop(0, '#ffe27a');
    grad.addColorStop(.42, '#ff6f91');
    grad.addColorStop(.75, '#ff2bd6');
    grad.addColorStop(1, '#8b2cff');
    g.fillStyle = grad;
    g.beginPath();
    g.arc(size / 2, size / 2, sunR, 0, Math.PI * 2);
    g.fill();
    // Горизонтальные прорези, как в ретро-аркадах.
    g.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 10; i++) {
      const y = size / 2 + sunR * .05 + i * (sunR / 10.5);
      g.fillRect(0, y, size, .8 + i * .75);
    }
  }

  /* ---------- отрисовка ---------- */

  function drawStars(t) {
    for (const s of stars) {
      if (s.y > horizon - 4) continue;
      const a = .35 + Math.sin(t * s.s * 60 + s.p) * .35;
      ctx.fillStyle = `rgba(220,235,255,${Math.max(.05, a)})`;
      ctx.fillRect(s.x, s.y, s.r, s.r);
    }
  }

  function drawNetwork(dt) {
    const linkDist = 130;
    const skyBottom = horizon - 20;
    for (const n of nodes) {
      n.x += n.vx * dt;
      n.y += n.vy * dt;
      const dx = n.x - mouse.x, dy = n.y - mouse.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 150 * 150 && d2 > 1) {
        const d = Math.sqrt(d2), f = (1 - d / 150) * 1.2;
        n.x += (dx / d) * f * dt;
        n.y += (dy / d) * f * dt;
      }
      if (n.x < -20) n.x = W + 20; else if (n.x > W + 20) n.x = -20;
      if (n.y < 10) { n.y = 10; n.vy = Math.abs(n.vy); }
      if (n.y > skyBottom) { n.y = skyBottom; n.vy = -Math.abs(n.vy); }
    }
    ctx.lineWidth = 1;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 < linkDist * linkDist) {
          ctx.strokeStyle = rgba(a.c, (1 - Math.sqrt(d2) / linkDist) * .32);
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
      }
      const mx = a.x - mouse.x, my = a.y - mouse.y;
      const md = mx * mx + my * my;
      if (md < 190 * 190) {
        ctx.strokeStyle = rgba(C.cyan, (1 - Math.sqrt(md) / 190) * .55);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(mouse.x, mouse.y);
        ctx.stroke();
      }
    }
    for (const n of nodes) {
      ctx.fillStyle = rgba(n.c, .25);
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = rgba(n.c, .95);
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawSun(t, vpX) {
    const cy = horizon - sunR * .42;
    const pulse = .9 + Math.sin(t * 1.4) * .06 + flash * .4;
    const glow = ctx.createRadialGradient(vpX, cy, sunR * .4, vpX, cy, sunR * 2.6);
    glow.addColorStop(0, rgba(C.magenta, .32 * pulse));
    glow.addColorStop(.5, rgba(C.violet, .12 * pulse));
    glow.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = glow;
    ctx.fillRect(vpX - sunR * 2.6, cy - sunR * 2.6, sunR * 5.2, sunR * 2.6 + (horizon - cy));

    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, W, horizon);
    ctx.clip();
    ctx.globalAlpha = (calm ? .55 : .92) * Math.min(1, pulse);
    const size = sunCanvas.width / DPR;
    ctx.drawImage(sunCanvas, vpX - size / 2, cy - size / 2, size, size);
    ctx.restore();
  }

  function drawRidge(pts, color, shift) {
    ctx.beginPath();
    ctx.moveTo(-60, horizon);
    for (const [x, h] of pts) ctx.lineTo(x * (W + 120) - 60 + shift, horizon - h * H);
    ctx.lineTo(W + 60, horizon);
    ctx.closePath();
    const g = ctx.createLinearGradient(0, horizon - H * .1, 0, horizon);
    g.addColorStop(0, 'rgba(10,4,32,.96)');
    g.addColorStop(1, 'rgba(26,4,48,.96)');
    ctx.fillStyle = g;
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = rgba(color, .18);
    ctx.stroke();
    ctx.lineWidth = 1.1;
    ctx.strokeStyle = rgba(color, .85);
    ctx.stroke();
  }

  function drawFloor(vpX) {
    const depth = H - horizon;
    if (depth <= 0) return;

    const base = ctx.createLinearGradient(0, horizon, 0, H);
    base.addColorStop(0, 'rgba(60,8,90,.35)');
    base.addColorStop(1, 'rgba(6,2,22,.6)');
    ctx.fillStyle = base;
    ctx.fillRect(0, horizon, W, depth);

    // Свечение горизонта.
    const hg = ctx.createLinearGradient(0, horizon - 50, 0, horizon + 60);
    hg.addColorStop(0, 'rgba(0,0,0,0)');
    hg.addColorStop(.45, rgba(C.magenta, .35 + flash * .5));
    hg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = hg;
    ctx.fillRect(0, horizon - 50, W, 110);

    // Сходящиеся линии.
    const count = W < 700 ? 14 : 22;
    const spread = W * 2.2;
    const vg = ctx.createLinearGradient(0, horizon, 0, H);
    vg.addColorStop(0, rgba(C.cyan, 0));
    vg.addColorStop(.35, rgba(C.cyan, .35));
    vg.addColorStop(1, rgba(C.cyan, .85));
    ctx.beginPath();
    for (let i = -count; i <= count; i++) {
      ctx.moveTo(vpX, horizon);
      ctx.lineTo(vpX + (i / count) * spread, H);
    }
    const dim = W < 700 ? .6 : 1;
    ctx.strokeStyle = vg;
    ctx.lineWidth = 3.5;
    ctx.globalAlpha = .25 * dim;
    ctx.stroke();
    ctx.globalAlpha = dim;
    ctx.lineWidth = 1.2;
    ctx.stroke();

    // Поперечные линии бегут к зрителю.
    const frac = offset % 1;
    for (let i = 0; i < 34; i++) {
      const z = i + 1 - frac;
      const y = horizon + depth / (1 + z * .5);
      const a = Math.min(1, (y - horizon) / depth * 1.6);
      ctx.strokeStyle = rgba(C.magenta, a * .22 * dim);
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
      ctx.strokeStyle = rgba(C.magenta, a * .9);
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Яркая линия горизонта.
    ctx.strokeStyle = rgba([255, 160, 240], .9);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, horizon);
    ctx.lineTo(W, horizon);
    ctx.stroke();
  }

  function spawnSpark() {
    sparks.push({
      x: Math.random() * W,
      y: H + 10,
      vx: rand(-.3, .3),
      vy: -rand(.6, 2.2),
      life: 1,
      decay: rand(.003, .008),
      r: rand(.8, 2.4),
      c: Math.random() < .55 ? C.cyan : Math.random() < .5 ? C.magenta : C.amber,
      sway: Math.random() * Math.PI * 2,
    });
  }

  function drawSparks(dt, t) {
    const target = calm ? .35 : 1.4;
    let spawn = target * dt * (1 + boost * 6);
    while (spawn > 0) {
      if (Math.random() < spawn) spawnSpark();
      spawn -= 1;
    }
    ctx.globalCompositeOperation = 'lighter';
    for (let i = sparks.length - 1; i >= 0; i--) {
      const s = sparks[i];
      s.x += (s.vx + Math.sin(t * 2 + s.sway) * .3) * dt;
      s.y += s.vy * dt * (1 + boost * 2);
      s.life -= s.decay * dt;
      if (s.life <= 0 || s.y < -10) { sparks.splice(i, 1); continue; }
      ctx.fillStyle = rgba(s.c, s.life * .25);
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r * 3.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = rgba(s.c, s.life);
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    if (sparks.length > 220) sparks.splice(0, sparks.length - 220);
    ctx.globalCompositeOperation = 'source-over';
  }

  function drawStreaks(dt, now) {
    if (now > nextStreak) {
      const fromLeft = Math.random() < .5;
      streaks.push({
        x: fromLeft ? rand(-100, W * .4) : rand(W * .6, W + 100),
        y: rand(-20, horizon * .45),
        vx: (fromLeft ? 1 : -1) * rand(9, 15),
        vy: rand(2.5, 5),
        life: 1,
        c: Math.random() < .5 ? C.cyan : C.magenta,
      });
      nextStreak = now + rand(calm ? 4000 : 1800, calm ? 9000 : 4800);
    }
    ctx.globalCompositeOperation = 'lighter';
    for (let i = streaks.length - 1; i >= 0; i--) {
      const s = streaks[i];
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      s.life -= .012 * dt;
      if (s.life <= 0 || s.y > horizon) { streaks.splice(i, 1); continue; }
      const tx = s.x - s.vx * 9, ty = s.y - s.vy * 9;
      const g = ctx.createLinearGradient(s.x, s.y, tx, ty);
      g.addColorStop(0, `rgba(255,255,255,${s.life})`);
      g.addColorStop(.2, rgba(s.c, s.life * .8));
      g.addColorStop(1, rgba(s.c, 0));
      ctx.strokeStyle = g;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(tx, ty);
      ctx.stroke();
    }
    ctx.globalCompositeOperation = 'source-over';
  }

  function drawWaves(dt) {
    for (let i = waves.length - 1; i >= 0; i--) {
      const w = waves[i];
      w.r += w.speed * dt;
      w.life -= .02 * dt;
      if (w.life <= 0) { waves.splice(i, 1); continue; }
      for (const n of nodes) {
        const dx = n.x - w.x, dy = n.y - w.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        if (Math.abs(d - w.r) < 30) {
          n.x += (dx / d) * 4 * w.life;
          n.y += (dy / d) * 4 * w.life;
        }
      }
      ctx.lineWidth = 2.5 * w.life + .5;
      ctx.strokeStyle = rgba(C.cyan, w.life * .8);
      ctx.beginPath();
      ctx.arc(w.x, w.y, w.r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.lineWidth = 1;
      ctx.strokeStyle = rgba(C.magenta, w.life * .6);
      ctx.beginPath();
      ctx.arc(w.x, w.y, w.r * .72, 0, Math.PI * 2);
      ctx.stroke();
    }
  }

  function frame(now) {
    const dt = Math.min(3, (now - last) / 16.667 || 1);
    last = now;
    const t = now / 1000;

    mouse.px += (mouse.tx - mouse.px) * .04 * dt;
    mouse.py += (mouse.ty - mouse.py) * .04 * dt;
    boost = Math.max(0, boost - .012 * dt);
    flash = Math.max(0, flash - .02 * dt);

    const scrollLift = Math.min(window.scrollY * .06, H * .1);
    horizon = baseHorizon - scrollLift + (mouse.py - .5) * -18;
    offset += (calm ? .012 : .02) * dt * (1 + boost * 9);

    const vpRatio = W > 960 ? (parseFloat(document.body.dataset.vp) || .5) : .5;
    const vpX = W * vpRatio + (mouse.px - .5) * -70;

    ctx.clearRect(0, 0, W, H);
    drawStars(t);
    drawStreaks(dt, now);
    drawSun(t, vpX);
    drawRidge(ridges[0], C.violet, (mouse.px - .5) * -25);
    drawRidge(ridges[1], C.cyan, (mouse.px - .5) * -50);
    drawNetwork(dt);
    drawFloor(vpX);
    drawSparks(dt, t);
    drawWaves(dt);

    if (running) raf = requestAnimationFrame(frame);
  }

  function start() {
    if (running || reduce) return;
    running = true;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    cancelAnimationFrame(raf);
  }

  /* ---------- события ---------- */

  window.addEventListener('resize', () => {
    resize();
    if (reduce) frame(performance.now());
  });

  window.addEventListener('pointermove', (e) => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.tx = e.clientX / W;
    mouse.ty = e.clientY / H;
  }, { passive: true });

  document.addEventListener('pointerleave', () => { mouse.x = mouse.y = -9999; });

  document.addEventListener('pointerdown', (e) => {
    if (e.target.closest('input, textarea, select, label, .hold-btn')) return;
    shockwave(e.clientX, e.clientY, .7);
  }, { passive: true });

  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));

  function shockwave(x, y, power = 1) {
    if (reduce) return;
    waves.push({ x, y, r: 4, speed: 9 * power + 4, life: 1 });
  }

  /* Публичный API для эффектов игры (вердикт). */
  window.VerdictFX = {
    shockwave,
    boost(power = 1) {
      if (reduce) return;
      boost = Math.min(1.5, boost + power);
      flash = 1;
      shockwave(W / 2, H * .55, 1.6);
      for (let i = 0; i < 40; i++) spawnSpark();
    },
  };

  resize();
  if (reduce) {
    frame(performance.now());
  } else {
    start();
  }
})();
