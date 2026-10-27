// Building blocks for the explainer: elements, wires, motion and scene timing. Every scene adds tweens to one
// paused GSAP timeline at absolute seconds; nothing moves on its own, so a seek gives the same frame every time.

const NS = 'http://www.w3.org/2000/svg';
const TONE = {
  ink:    { fg: '#0B1220', tint: '#EEF2F7', deep: '#0B1220' },
  blue:   { fg: '#1F6BFF', tint: '#EAF1FF', deep: '#0F4ACC' },
  red:    { fg: '#E5383B', tint: '#FDECEC', deep: '#B4232A' },
  green:  { fg: '#0E9F6E', tint: '#E5F6EF', deep: '#08714E' },
  amber:  { fg: '#E8890C', tint: '#FFF3DF', deep: '#9A5B00' },
  violet: { fg: '#6E56CF', tint: '#F0EDFC', deep: '#4F3AA8' },
  grey:   { fg: '#A3ADBD', tint: '#F1F4F8', deep: '#6B7789' },
};

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null) continue;
    if (k === 'style') Object.assign(el.style, v);
    else if (k === 'cls') el.className = v;
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}

function s(tag, attrs = {}) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  return el;
}

// place an absolutely positioned element; g keeps its box for wiring
function place(el, o) {
  const st = el.style;
  if (o.x != null) st.left = o.x + 'px';
  if (o.y != null) st.top = o.y + 'px';
  if (o.w != null) st.width = o.w + 'px';
  if (o.h != null) st.height = o.h + 'px';
  el.g = { x: o.x, y: o.y, w: o.w, h: o.h };
  return el;
}

function icon(name, size = 36, color = 'currentColor', sw = 2) {
  if (!ICONS[name]) throw new Error('no icon ' + name);
  const el = s('svg', { viewBox: '0 0 24 24', width: size, height: size, fill: 'none', stroke: color,
    'stroke-width': sw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
  el.innerHTML = ICONS[name];
  el.style.display = 'block';
  return el;
}

// ---------- scene ----------

function scene(id) {
  const root = h('div', { cls: 'scene', id });
  const wires = s('svg', { class: 'wires', width: 1920, height: 1080, viewBox: '0 0 1920 1080' });
  root.append(wires);
  document.getElementById('stage').append(root);
  root.wires = wires;
  return root;
}

// a top SVG layer for things that travel over the boxes
function overlay(root) {
  if (!root.over) {
    root.over = s('svg', { class: 'wires', width: 1920, height: 1080, viewBox: '0 0 1920 1080' });
    root.append(root.over);
  }
  return root.over;
}

// timing for one scene: S.w('Guard') is the second the word "Guard" starts, on the whole video's clock
const norm = (w) => w.toLowerCase().replace(/[^a-z0-9]/g, '');
function timing(info) {
  const words = info.words.map((x) => ({ ...x, k: norm(x.w) }));
  const find = (phrase, nth, edge) => {
    const ks = phrase.split(/\s+/).map(norm);
    let c = 0;
    for (let i = 0; i + ks.length <= words.length; i++) {
      if (ks.every((k, j) => words[i + j].k === k) && ++c === nth)
        return info.voice + (edge === 't1' ? words[i + ks.length - 1].t1 : words[i].t0);
    }
    throw new Error(`${info.id}: "${phrase}" #${nth} not in narration`);
  };
  return {
    id: info.id, start: info.start, end: info.end, voice: info.voice, speechEnd: info.voice + info.speech,
    w: (phrase, nth = 1) => find(phrase, nth, 't0'),
    we: (phrase, nth = 1) => find(phrase, nth, 't1'),
    at: (sec) => info.voice + sec,
  };
}

// a scene is on screen from start to end, with a short cross-fade at both ends
function showScene(tl, root, S, fadeIn = 0.45, fadeOut = 0.4) {
  tl.set(root, { visibility: 'visible' }, S.start - 0.001);
  tl.fromTo(root, { opacity: 0 }, { opacity: 1, duration: fadeIn, ease: 'power1.out', immediateRender: false }, S.start);
  tl.to(root, { opacity: 0, duration: fadeOut, ease: 'power1.in' }, S.end - fadeOut);
  tl.set(root, { visibility: 'hidden' }, S.end);
}

// ---------- pieces ----------

function box(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'box' + (o.solid ? ' solid' : '') + (o.center ? ' center' : ''), id: o.id }), o);
  el.style.borderTopColor = t.fg;
  if (o.solid) el.style.background = t.fg;
  if (o.bg) el.style.background = o.bg;
  if (o.icon) {
    const ic = h('div', { cls: 'ic' });
    ic.append(icon(o.icon, o.iconSize || 40, o.solid ? '#fff' : t.fg, 2));
    el.append(ic);
  }
  const tx = h('div', { cls: 'tx' });
  tx.append(h('div', { cls: 'lb', html: o.label, style: o.size ? { fontSize: o.size + 'px' } : null }));
  if (o.sub) tx.append(h('div', { cls: 'sb', html: o.sub, style: o.subSize ? { fontSize: o.subSize + 'px' } : null }));
  el.append(tx);
  if (o.num) el.append(h('div', { cls: 'num' }, o.num));
  parent.append(el);
  return el;
}

function text(parent, o) {
  const el = place(h('div', { cls: o.cls || 'abs', html: o.html, id: o.id }), o);
  const st = el.style;
  if (o.size) st.fontSize = o.size + 'px';
  if (o.weight) st.fontWeight = o.weight;
  if (o.color) st.color = o.color;
  if (o.align) st.textAlign = o.align;
  if (o.lh) st.lineHeight = o.lh;
  if (o.mono) st.fontFamily = "'JetBrains Mono', Consolas, monospace";
  if (o.nowrap) st.whiteSpace = 'nowrap';
  if (o.ls != null) st.letterSpacing = o.ls + 'px';
  parent.append(el);
  return el;
}

function chip(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'chip' }), o);
  el.style.color = o.solid ? '#fff' : t.deep;
  el.style.borderColor = t.fg;
  el.style.background = o.solid ? t.fg : (o.bg || t.tint);
  if (o.size) el.style.fontSize = o.size + 'px';
  if (o.icon) el.append(icon(o.icon, o.iconSize || 22, o.solid ? '#fff' : t.fg, 2.2));
  el.append(h('span', { html: o.text }));
  parent.append(el);
  return el;
}

function stamp(parent, o) {
  const t = TONE[o.tone || 'red'];
  const el = place(h('div', { cls: 'stamp', html: o.text }), o);
  el.style.color = t.fg;
  el.style.borderColor = t.fg;
  if (o.size) el.style.fontSize = o.size + 'px';
  if (o.rot != null) el.style.transform = `rotate(${o.rot}deg)`;
  el.style.background = 'rgba(255,255,255,.88)';
  parent.append(el);
  return el;
}

function title(parent, num, label) {
  const el = h('div', { cls: 'title' }, h('span', { cls: 'n' }, num), h('span', { cls: 't', html: label }));
  parent.append(el);
  return el;
}

// a document block: header plus rows [k, v] or {html}
function doc(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'doc', id: o.id }), o);
  el.style.borderTopColor = t.fg;
  const hd = h('div', { cls: 'hd' });
  if (o.icon) hd.append(icon(o.icon, 30, t.fg, 2));
  hd.append(h('span', { cls: 't', html: o.title, style: { flex: '1' } }));
  if (o.idText) hd.append(h('span', { cls: 'id', html: o.idText }));
  el.append(hd);
  el.rows = [];
  for (const r of o.rows || []) {
    const row = Array.isArray(r)
      ? h('div', { cls: 'row' }, h('span', { cls: 'k', html: r[0] }), h('span', { cls: 'v', html: r[1] }))
      : h('div', { cls: r.cls || 'block', html: r.html });
    el.append(row);
    el.rows.push(row);
  }
  parent.append(el);
  return el;
}

// a real screenshot in a browser frame; view() pans and zooms it
function browser(parent, o) {
  const el = place(h('div', { cls: 'browser', id: o.id }), o);
  const bar = h('div', { cls: 'bar' }, h('i', { cls: 'dot' }), h('i', { cls: 'dot' }), h('i', { cls: 'dot' }),
    h('div', { cls: 'url' }, o.url), h('div', { cls: 'live' }, h('i'), o.live || 'LIVE · BACKEND ZETARIS'));
  const vp = h('div', { cls: 'vp' });
  const inner = h('div', { cls: 'inner' });
  const img = h('img', { src: o.src, width: o.imgW, height: o.imgH });
  inner.append(img);
  vp.append(inner);
  el.append(bar, vp);
  el.inner = inner;
  el.vp = { w: o.w, h: o.h - 44 };
  const v = o.view || { x: 0, y: 0, scale: o.w / o.imgW };
  gsap.set(inner, { x: -v.x * v.scale, y: -v.y * v.scale, scale: v.scale });
  parent.append(el);
  return el;
}

// show the screenshot region whose top-left is (x, y) in image pixels, at the given scale
function view(tl, br, v, at, dur = 1.1, ease = 'power2.inOut') {
  tl.to(br.inner, { x: -v.x * v.scale, y: -v.y * v.scale, scale: v.scale, duration: dur, ease }, at);
}

// a highlight frame drawn in image pixels on a screenshot
function mark(br, o) {
  const t = TONE[o.tone || 'red'];
  const el = place(h('div', { cls: 'mark' }), o);
  el.style.borderColor = t.fg;
  if (o.bw) el.style.borderWidth = o.bw + 'px';
  br.inner.append(el);
  return el;
}

// ---------- wires ----------

// an orthogonal polyline through points, corners rounded by r
function polyline(pts, r = 12) {
  pts = pts.filter((p, i) => i === 0 || p[0] !== pts[i - 1][0] || p[1] !== pts[i - 1][1]);
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const [x, y] = pts[i];
    if (i < pts.length - 1 && r > 0) {
      const [px, py] = pts[i - 1], [nx, ny] = pts[i + 1];
      const l1 = Math.hypot(x - px, y - py), l2 = Math.hypot(nx - x, ny - y);
      const rr = Math.min(r, l1 / 2, l2 / 2);
      const ax = x - ((x - px) / l1) * rr, ay = y - ((y - py) / l1) * rr;
      const bx = x + ((nx - x) / l2) * rr, by = y + ((ny - y) / l2) * rr;
      d += ` L ${ax} ${ay} Q ${x} ${y} ${bx} ${by}`;
    } else d += ` L ${x} ${y}`;
  }
  return d;
}

let wireId = 0;
function wire(layer, o) {
  const t = TONE[o.tone || 'ink'];
  const color = o.color || t.fg;
  const d = o.d || polyline(o.pts, o.r ?? 12);
  const g = s('g');
  const p = s('path', { d, fill: 'none', stroke: color, 'stroke-width': o.w || 3, 'stroke-linecap': o.dash ? 'butt' : 'round',
    'stroke-linejoin': 'round' });
  g.append(p);
  layer.append(g);
  const len = p.getTotalLength();
  const w = { g, p, len, color, dashed: !!o.dash };
  if (o.dash) {
    // a dashed line is revealed through a mask whose solid stroke is drawn on
    p.setAttribute('stroke-dasharray', o.dash);
    const id = 'wm' + ++wireId;
    const mask = s('mask', { id, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: 4000, height: 3000 });
    const mp = s('path', { d, fill: 'none', stroke: '#fff', 'stroke-width': (o.w || 3) + 6, 'stroke-linecap': 'butt' });
    mask.append(mp);
    layer.append(mask);
    p.setAttribute('mask', `url(#${id})`);
    w.reveal = mp;
  } else w.reveal = p;
  gsap.set(w.reveal, { strokeDasharray: len + ' ' + (len + 10), strokeDashoffset: len + 1 });
  if (o.head !== false) {
    const a = p.getPointAtLength(len), b = p.getPointAtLength(Math.max(0, len - 2));
    const ang = (Math.atan2(a.y - b.y, a.x - b.x) * 180) / Math.PI;
    const sz = o.headSize || 1;
    const head = s('path', { d: `M ${2 * sz} 0 L ${-11 * sz} ${-7 * sz} L ${-8 * sz} 0 L ${-11 * sz} ${7 * sz} Z`, fill: color,
      transform: `translate(${a.x} ${a.y}) rotate(${ang})` });
    g.append(head);
    w.head = head;
    gsap.set(head, { opacity: 0 });
  }
  if (o.label) {
    const lb = o.label;
    w.label = text(o.labelParent, { x: lb.x, y: lb.y, w: lb.w, html: lb.html, cls: 'note', size: lb.size || 22,
      color: lb.color || t.deep, align: lb.align, mono: lb.mono });
    gsap.set(w.label, { autoAlpha: 0 });
  }
  return w;
}

function draw(tl, w, at, dur = 0.7, ease = 'power2.inOut') {
  tl.to(w.reveal, { strokeDashoffset: 0, duration: dur, ease }, at);
  if (w.head) tl.to(w.head, { opacity: 1, duration: 0.12 }, at + dur - 0.08);
  if (w.label) tl.to(w.label, { autoAlpha: 1, duration: 0.35 }, at + dur * 0.6);
  return at + dur;
}

// a wire already drawn, for a scene that opens on a finished diagram
function drawn(w) {
  gsap.set(w.reveal, { strokeDashoffset: 0 });
  if (w.head) gsap.set(w.head, { opacity: 1 });
  if (w.label) gsap.set(w.label, { autoAlpha: 1 });
}

function undraw(tl, w, at, dur = 0.3) {
  tl.to(w.g, { opacity: 0, duration: dur }, at);
  if (w.label) tl.to(w.label, { autoAlpha: 0, duration: dur }, at);
}

// a dot that runs along a wire
function packet(layer, o = {}) {
  const t = TONE[o.tone || 'blue'];
  const g = s('g');
  if (o.halo !== false) g.append(s('circle', { cx: 0, cy: 0, r: (o.r || 7) + 6, fill: t.fg, opacity: 0.18 }));
  g.append(s('circle', { cx: 0, cy: 0, r: o.r || 7, fill: t.fg }));
  layer.append(g);
  gsap.set(g, { opacity: 0 });
  return g;
}

function travel(tl, dot, w, at, dur = 0.9, ease = 'power1.inOut', o = {}) {
  tl.set(dot, { opacity: 1 }, at);
  tl.fromTo(dot, { motionPath: { path: w.p, align: w.p, alignOrigin: [0.5, 0.5], start: o.reverse ? 1 : 0, end: o.reverse ? 1 : 0 } },
    { motionPath: { path: w.p, align: w.p, alignOrigin: [0.5, 0.5], start: o.reverse ? 1 : 0, end: o.reverse ? 0 : 1 },
      duration: dur, ease, immediateRender: false }, at);
  tl.set(dot, { opacity: 0 }, at + dur);
  return at + dur;
}

// ---------- motion ----------

function hide(...els) { gsap.set(els.flat(), { autoAlpha: 0 }); }

// start a background tween from transparent white, not transparent black
function clearBg(...els) { gsap.set(els.flat(), { backgroundColor: 'rgba(255,255,255,0)' }); }

function pop(tl, el, at, o = {}) {
  gsap.set(el, { autoAlpha: 0, scale: o.from ?? 0.86, transformOrigin: o.origin || '50% 50%' });
  tl.to(el, { autoAlpha: 1, scale: 1, duration: o.dur || 0.5, ease: o.ease || 'back.out(1.7)' }, at);
  return at;
}

function fade(tl, el, at, dur = 0.45) {
  gsap.set(el, { autoAlpha: 0 });
  tl.to(el, { autoAlpha: 1, duration: dur, ease: 'power1.out' }, at);
  return at;
}

function rise(tl, el, at, o = {}) {
  gsap.set(el, { autoAlpha: 0, y: o.dy ?? 28 });
  tl.to(el, { autoAlpha: 1, y: 0, duration: o.dur || 0.6, ease: o.ease || 'power3.out' }, at);
  return at;
}

function slide(tl, el, at, o = {}) {
  gsap.set(el, { autoAlpha: 0, x: o.dx ?? 60 });
  tl.to(el, { autoAlpha: 1, x: 0, duration: o.dur || 0.6, ease: o.ease || 'power3.out' }, at);
  return at;
}

function out(tl, el, at, dur = 0.35) {
  tl.to(el, { autoAlpha: 0, duration: dur, ease: 'power1.in' }, at);
  return at;
}

function stagger(tl, els, at, gap, fn = rise, o = {}) {
  els.forEach((el, i) => fn(tl, el, at + i * gap, o));
  return at + (els.length - 1) * gap;
}

// type text into an element, characters per second
function type(tl, el, str, at, cps = 45) {
  el.textContent = '';
  const dur = str.length / cps;
  tl.to(el, { text: { value: str }, duration: dur, ease: 'none' }, at);
  return at + dur;
}

// count a number up; fmt turns the value into text
function count(tl, el, to, at, dur = 1.2, fmt = (v) => Math.round(v).toLocaleString('en-US'), from = 0) {
  const o = { v: from };
  el.textContent = fmt(from);
  tl.to(o, { v: to, duration: dur, ease: 'power2.out', onUpdate: () => { el.textContent = fmt(o.v); } }, at);
  return at + dur;
}

// colour a block's top rule, border and fill, e.g. to light it up
function light(tl, el, tone, at, dur = 0.35, o = {}) {
  if (el.outline) return hue(tl, el, tone, at, { ...o, dur });
  const t = TONE[tone];
  const v = { borderTopColor: t.fg, duration: dur, ease: 'power1.out' };
  if (o.fill) v.backgroundColor = o.fill === true ? t.tint : o.fill;
  if (o.frame) v.borderColor = t.fg;
  tl.to(el, v, at);
  return at;
}

function pulse(tl, el, at, o = {}) {
  tl.to(el, { scale: o.scale || 1.06, duration: 0.18, ease: 'power2.out', transformOrigin: '50% 50%' }, at)
    .to(el, { scale: 1, duration: 0.35, ease: 'power2.inOut' }, at + 0.18);
  return at;
}

// box edge midpoints for wiring
const L = (el, dy = 0) => [el.g.x, el.g.y + el.g.h / 2 + dy];
const R = (el, dy = 0) => [el.g.x + el.g.w, el.g.y + el.g.h / 2 + dy];
const T = (el, dx = 0) => [el.g.x + el.g.w / 2 + dx, el.g.y];
const B = (el, dx = 0) => [el.g.x + el.g.w / 2 + dx, el.g.y + el.g.h];
