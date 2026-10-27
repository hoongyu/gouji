// Pieces that look like what they stand for, instead of one card for everything: flowchart symbols for the
// process (process, decision, terminator, predefined process, document, data store, file, envelope, manual step),
// and objects for the story (paper documents, gates, a notary's seal, a lock, speech bubbles, a person,
// leader-line notes). Each is a positioned div, so wires (L/R/T/B), pop, rise and light work on it as on a box.

let shapeId = 0;

// outline and inner strokes of each flowchart symbol, for a w x h box
function shapePaths(kind, w, h) {
  const a = 1.5, r = (h - 3) / 2, ry = Math.min(20, h * 0.17);
  switch (kind) {
    case 'terminator':
      return { outline: `M${a + r} ${a} H${w - a - r} A${r} ${r} 0 0 1 ${w - a - r} ${h - a} H${a + r} A${r} ${r} 0 0 1 ${a + r} ${a} Z` };
    case 'decision':
      return { outline: `M${w / 2} ${a} L${w - a} ${h / 2} L${w / 2} ${h - a} L${a} ${h / 2} Z` };
    case 'predef':
      return { outline: `M${a} ${a} H${w - a} V${h - a} H${a} Z`, inner: `M16 ${a} V${h - a} M${w - 16} ${a} V${h - a}` };
    case 'document':
      return { outline: `M${a} ${a} H${w - a} V${h - 18} C${w * 0.72} ${h - 40} ${w * 0.3} ${h + 6} ${a} ${h - 16} Z` };
    case 'cylinder':
      return { outline: `M${a} ${ry} V${h - ry} A${w / 2 - a} ${ry - a} 0 0 0 ${w - a} ${h - ry} V${ry} A${w / 2 - a} ${ry - a} 0 0 0 ${a} ${ry} Z`,
        inner: `M${a} ${ry} A${w / 2 - a} ${ry - a} 0 0 0 ${w - a} ${ry}` };
    case 'file':
      return { outline: `M${a} ${a} H${w - 28} L${w - a} 28 V${h - a} H${a} Z`, inner: `M${w - 28} ${a} V28 H${w - a}` };
    case 'envelope':
      return { outline: `M${a} ${a} H${w - a} V${h - a} H${a} Z`, inner: `M${a} ${a} L${w / 2} ${h * 0.46} L${w - a} ${a}` };
    case 'manual':
      return { outline: `M${a} ${a} H${w - a} L${w - 20} ${h - a} H20 Z` };
    case 'shield':
      return { outline: `M${w / 2} ${a} L${w - a} ${h * 0.17} V${h * 0.5} C${w - a} ${h * 0.78} ${w * 0.72} ${h * 0.92} ${w / 2} ${h - a} C${w * 0.28} ${h * 0.92} ${a} ${h * 0.78} ${a} ${h * 0.5} V${h * 0.17} Z` };
    default:
      return { outline: `M${a} ${a} H${w - a} V${h - a} H${a} Z` };
  }
}

// text area inside each symbol, as [left, top, right, bottom] insets
const SHAPE_PAD = {
  decision: (w, h) => [w * 0.2, h * 0.24, w * 0.2, h * 0.24], cylinder: (w, h) => [14, Math.min(20, h * 0.17) * 1.6, 14, 10],
  document: () => [18, 10, 18, 26], predef: () => [26, 8, 26, 8], file: () => [18, 12, 30, 10], envelope: (w, h) => [16, h * 0.42, 16, 8],
  terminator: (w, h) => [h * 0.36, 6, h * 0.36, 6], manual: () => [26, 8, 26, 8], shield: (w, h) => [w * 0.14, h * 0.16, w * 0.14, h * 0.24],
};

function shape(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'shape ' + (o.kind || 'process'), id: o.id }), o);
  const svg = s('svg', { class: 'shp', width: o.w, height: o.h, viewBox: `0 0 ${o.w} ${o.h}` });
  const { outline, inner } = shapePaths(o.kind, o.w, o.h);
  let fill = o.solid ? t.fg : (o.fill || '#FFFFFF');
  if (o.hatch) {
    const id = 'hatch' + ++shapeId;
    const pat = s('pattern', { id, width: 12, height: 12, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
    pat.append(s('rect', { width: 12, height: 12, fill: t.tint }), s('line', { x1: 0, y1: 0, x2: 0, y2: 12, stroke: t.fg, 'stroke-width': 2.2, opacity: 0.35 }));
    const defs = s('defs');
    defs.append(pat);
    svg.append(defs);
    fill = `url(#${id})`;
  }
  const sw = o.sw || 2.5;
  el.outline = s('path', { d: outline, fill, stroke: t.fg, 'stroke-width': sw, 'stroke-linejoin': 'round',
    'stroke-dasharray': o.dash || 'none' });
  svg.append(el.outline);
  if (inner) {
    el.inner = s('path', { d: inner, fill: 'none', stroke: o.solid ? 'rgba(255,255,255,.75)' : t.fg, 'stroke-width': sw * 0.8 });
    svg.append(el.inner);
  }
  el.append(svg);
  const [pl, pt, pr, pb] = (SHAPE_PAD[o.kind] || (() => [18, 8, 18, 8]))(o.w, o.h);
  const tx = h('div', { cls: 'stx' + (o.align === 'left' ? ' left' : ''), style: { left: pl + 'px', top: pt + 'px', right: pr + 'px', bottom: pb + 'px',
    color: o.solid ? '#fff' : (o.ink || '#0B1220') } });
  if (o.icon) tx.append(icon(o.icon, o.iconSize || 30, o.solid ? '#fff' : t.fg, 2));
  if (o.label) tx.append(h('div', { cls: 'sl', html: o.label, style: { fontSize: (o.size || 28) + 'px' } }));
  if (o.sub) tx.append(h('div', { cls: 'ss' + (o.mono ? ' mono' : ''), html: o.sub, style: { fontSize: (o.subSize || 19) + 'px',
    color: o.solid ? 'rgba(255,255,255,.85)' : '#6B7789' } }));
  el.append(tx);
  el.solid = !!o.solid;
  el.tone0 = o.tone || 'ink';
  el.fill0 = fill;
  parent.append(el);
  return el;
}

// put a shape back to how it was drawn
function unhue(tl, el, at) {
  tl.to(el.outline, { attr: { stroke: TONE[el.tone0].fg }, duration: 0.4 }, at);
  tl.set(el.outline, { attr: { fill: el.fill0 } }, at + 0.2);
  if (el.inner && !el.solid) tl.to(el.inner, { attr: { stroke: TONE[el.tone0].fg }, duration: 0.4 }, at);
  return at;
}

// recolour a shape's outline (and fill, with o.fill), the counterpart of light() for boxes
function hue(tl, el, tone, at, o = {}) {
  const t = TONE[tone];
  const v = { stroke: t.fg };
  if (o.fill) v.fill = o.fill === true ? t.tint : o.fill;
  if (o.width) v['stroke-width'] = o.width;
  tl.to(el.outline, { attr: v, duration: o.dur || 0.3, ease: 'power1.out' }, at);
  if (el.inner && !el.solid) tl.to(el.inner, { attr: { stroke: t.fg }, duration: o.dur || 0.3 }, at);
  return at;
}

// a sheet of paper: a kicker naming what kind of document it is, a title, rows; the corner is folded.
// kind: invoice | registry | policy | contract | evidence | memo (default)
function paper(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'doc paper ' + (o.kind || 'memo'), id: o.id }), o);
  const hd = h('div', { cls: 'hd' });
  const left = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '0' } });
  left.append(h('span', { cls: 'kick', html: o.kicker || (o.kind || 'document').toUpperCase(), style: { color: t.deep } }));
  if (o.title) left.append(h('span', { cls: 't', html: o.title }));
  hd.append(left);
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
  if (o.kind === 'policy' || o.kind === 'contract') {
    const sig = h('div', { cls: 'sig' });
    sig.innerHTML = `<svg width="190" height="46" viewBox="0 0 190 46"><path class="ink" d="M6 34 C 22 6, 34 6, 30 30 S 52 40, 60 18 S 78 6, 84 30 C 90 44, 104 12, 118 22 S 140 36, 150 16 C 156 6, 166 30, 184 24" fill="none" stroke="${t.deep}" stroke-width="2.6" stroke-linecap="round"/></svg>`
      + `<div class="who">${o.signedBy || ''}</div>`;
    el.append(sig);
    el.sig = sig;
  }
  if (o.accent) el.style.boxShadow = `inset 0 4px 0 ${t.fg}`;
  parent.append(el);
  return el;
}

// a gate across a horizontal track at (x, y): a frame and a bar that lifts to let a request through, or drops to stop it
function gate(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const H = o.h || 150, bw = o.bar || 16, fw = o.frame || 54;
  const el = place(h('div', { cls: 'gate' }), { x: o.x - fw / 2, y: o.y - H / 2, w: fw, h: H });
  const svg = s('svg', { width: fw, height: H + 4, viewBox: `0 0 ${fw} ${H + 4}`, style: 'overflow:visible' });
  svg.append(s('rect', { x: 0, y: 0, width: 6, height: H, fill: '#A3ADBD' }), s('rect', { x: fw - 6, y: 0, width: 6, height: H, fill: '#A3ADBD' }),
    s('rect', { x: 0, y: -4, width: fw, height: 6, fill: '#A3ADBD' }));
  el.bar = s('rect', { x: fw / 2 - bw / 2, y: 6, width: bw, height: H - 10, fill: o.solid ? t.fg : '#fff', stroke: t.fg, 'stroke-width': 2.5 });
  svg.append(el.bar);
  if (!o.solid) for (let yy = 22; yy < H - 14; yy += 26) svg.append(s('rect', { class: 'stripe', x: fw / 2 - bw / 2, y: yy, width: bw, height: 12, fill: t.fg, opacity: 0.85 }));
  el.light = s('circle', { cx: fw / 2, cy: -18, r: 7, fill: '#D5DCE6' });
  svg.append(el.light);
  el.append(svg);
  el.svg = svg;
  // labels sit under the gate: a lifted bar rises above it
  if (o.label) el.append(h('div', { cls: 'glb', html: o.label, style: { fontSize: (o.size || 26) + 'px', top: H + 14 + 'px' } }));
  if (o.sub) el.append(h('div', { cls: 'gsb', html: o.sub, style: { top: H + 18 + (o.size || 26) * 1.25 + 'px' } }));
  el.g.cx = o.x;
  parent.append(el);
  return el;
}

function lift(tl, g, at, ok = true) {
  const parts = [g.bar, ...g.svg.querySelectorAll('.stripe')];
  tl.to(parts, { y: -(g.g.h - 24), duration: 0.45, ease: 'power2.inOut' }, at);
  tl.to(g.light, { attr: { fill: ok ? TONE.green.fg : TONE.red.fg }, duration: 0.2 }, at);
  return at;
}

// a gate that starts open and slams shut
function shut(tl, g, at) {
  const parts = [g.bar, ...g.svg.querySelectorAll('.stripe')];
  gsap.set(parts, { y: -(g.g.h - 24) });
  tl.to(parts, { y: 0, duration: 0.32, ease: 'bounce.out' }, at);
  tl.to(g.light, { attr: { fill: TONE.red.fg }, duration: 0.2 }, at + 0.2);
  return at;
}

// a round seal, the notary's mark: ring text around, a centre word
function seal(parent, o) {
  const t = TONE[o.tone || 'amber'];
  const R = o.r || 80, D = 2 * R, id = 'seal' + ++shapeId;
  const el = place(h('div', { cls: 'seal' }), { x: o.x - R, y: o.y - R, w: D, h: D });
  const ring = (o.ring || 'NOTARY · NO MODEL · ED25519 · ').repeat(o.repeat || 2);
  el.innerHTML = `<svg width="${D}" height="${D}" viewBox="0 0 ${D} ${D}">
    <defs><path id="${id}" d="M ${R} ${R} m -${R - 22} 0 a ${R - 22} ${R - 22} 0 1 1 ${2 * (R - 22)} 0 a ${R - 22} ${R - 22} 0 1 1 -${2 * (R - 22)} 0"/></defs>
    <circle cx="${R}" cy="${R}" r="${R - 3}" fill="${o.fill || 'rgba(255,255,255,.92)'}" stroke="${t.fg}" stroke-width="5"/>
    <circle cx="${R}" cy="${R}" r="${R - 12}" fill="none" stroke="${t.fg}" stroke-width="1.6"/>
    <circle cx="${R}" cy="${R}" r="${R - 36}" fill="none" stroke="${t.fg}" stroke-width="1.6"/>
    <text font-family="JetBrains Mono" font-size="${o.ringSize || 13}" font-weight="600" letter-spacing="${o.ls ?? 2.2}" fill="${t.deep}"><textPath href="#${id}">${ring}</textPath></text>
    <text x="${R}" y="${R + (o.centerSize || 30) * 0.36}" text-anchor="middle" font-family="IBM Plex Sans" font-weight="700" font-size="${o.centerSize || 30}" fill="${t.deep}">${o.center || 'SIGNED'}</text>
  </svg>`;
  el.style.transform = `rotate(${o.rot ?? -8}deg)`;
  parent.append(el);
  return el;
}

// press a seal onto the page
function stampOn(tl, el, at) {
  const rot = el.style.transform;
  gsap.set(el, { autoAlpha: 0, scale: 1.8 });
  tl.to(el, { autoAlpha: 1, scale: 1, duration: 0.32, ease: 'power3.in' }, at);
  tl.to(el, { scale: 1.04, duration: 0.08, yoyo: true, repeat: 1 }, at + 0.32);
  el.style.transform = rot;
  return at;
}

// a padlock; unlock() lifts the shackle
function lock(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const W = o.w || 120, H = Math.round(W * 1.15);
  const el = place(h('div', { cls: 'lock' }), { x: o.x, y: o.y, w: W, h: H });
  el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 120 138" style="overflow:visible">
    <path class="shackle" d="M30 64 V40 a30 30 0 0 1 60 0 V64" fill="none" stroke="${t.fg}" stroke-width="11" stroke-linecap="square"/>
    <rect class="body" x="10" y="62" width="100" height="74" fill="${o.solid ? t.fg : '#fff'}" stroke="${t.fg}" stroke-width="5"/>
    <path d="M60 86 a10 10 0 1 1 0.1 0 Z M55 100 h10 l3 20 h-16 Z" fill="${o.solid ? '#fff' : t.fg}"/>
  </svg>`;
  if (o.label) el.append(h('div', { cls: 'glb under', html: o.label, style: { fontSize: (o.size || 26) + 'px' } }));
  if (o.sub) el.append(h('div', { cls: 'gsb under2', html: o.sub }));
  el.shackle = el.querySelector('.shackle');
  el.body = el.querySelector('.body');
  parent.append(el);
  return el;
}

function unlock(tl, el, at, tone = 'green') {
  tl.to(el.shackle, { y: -16, duration: 0.25, ease: 'power2.out' }, at);
  tl.to(el.shackle, { rotation: -28, svgOrigin: '90 64', duration: 0.3, ease: 'power2.out' }, at + 0.2);
  tl.to(el.body, { attr: { stroke: TONE[tone].fg, fill: TONE[tone].tint }, duration: 0.3 }, at + 0.2);
  return at;
}

// a speech bubble; the tail points down-left to whoever says it
function bubble(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'bubble' + (o.mono ? ' mono' : ''), html: o.html }), o);
  el.style.borderColor = t.fg;
  el.style.color = o.ink || '#0B1220';
  if (o.size) el.style.fontSize = o.size + 'px';
  if (o.bg) el.style.background = o.bg;
  const tail = h('i', { cls: 'tail', style: { borderTopColor: t.fg } });
  el.append(tail);
  parent.append(el);
  return el;
}

// a person, drawn, with a label below
function person(parent, o) {
  const t = TONE[o.tone || 'blue'];
  const W = o.w || 120;
  const el = place(h('div', { cls: 'person' }), { x: o.x, y: o.y, w: W, h: W });
  el.innerHTML = `<svg width="${W}" height="${W}" viewBox="0 0 120 120"><circle cx="60" cy="38" r="24" fill="${t.fg}"/>
    <path d="M14 116 C 14 82, 34 68, 60 68 C 86 68, 106 82, 106 116 Z" fill="${t.fg}"/></svg>`;
  if (o.label) el.append(h('div', { cls: 'glb under', html: o.label, style: { fontSize: (o.size || 26) + 'px' } }));
  if (o.sub) el.append(h('div', { cls: 'gsb under2', html: o.sub }));
  parent.append(el);
  return el;
}

// a note with a thin leader line to the point it is about
function annot(parent, layer, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'annot', html: o.text, style: { color: t.deep, fontSize: (o.size || 20) + 'px', textAlign: o.align || 'left' } }),
    { x: o.x, y: o.y, w: o.w || 360 });
  parent.append(el);
  el.lead = o.to ? wire(layer, { pts: [o.from || [o.x - 8, o.y + 14], o.to], tone: o.tone || 'ink', w: 1.6, head: false, r: 0 }) : null;
  return el;
}

function note(tl, el, at) {
  fade(tl, el, at, 0.3);
  if (el.lead) draw(tl, el.lead, at, 0.3);
  return at;
}

// a check mark or a cross with a few words, no frame
function tick(parent, o) {
  const ok = o.ok !== false;
  const el = place(h('div', { cls: 'tick', style: { color: ok ? '#08714E' : '#B4232A', fontSize: (o.size || 22) + 'px' } },
    icon(ok ? 'check' : 'x', (o.size || 22) + 4, ok ? '#0E9F6E' : '#E5383B', 2.8), h('span', { html: o.text })), { x: o.x, y: o.y });
  parent.append(el);
  return el;
}

// an icon with a label and a line under it, no frame; o.row puts the icon on the left
function figure(parent, o) {
  const t = TONE[o.tone || 'ink'];
  const el = place(h('div', { cls: 'figure' + (o.row ? ' row' : '') }), o);
  const ic = h('div', { cls: 'fic' });
  for (const name of [].concat(o.icon)) ic.append(icon(name, o.iconSize || 64, t.fg, o.stroke || 1.8));
  el.append(ic);
  const tx = h('div', { cls: 'ftx' });
  tx.append(h('div', { cls: 'flb', html: o.label, style: { fontSize: (o.size || 28) + 'px', color: o.labelColor || '#0B1220' } }));
  if (o.sub) tx.append(h('div', { cls: 'fsb', html: o.sub, style: { fontSize: (o.subSize || 19) + 'px' } }));
  el.append(tx);
  parent.append(el);
  return el;
}

// a program window: a title bar and a line of output with a caret
function win(parent, o) {
  const el = place(h('div', { cls: 'win' }), o);
  el.append(h('div', { cls: 'wbar' }, h('i'), h('i'), h('i'), h('span', { html: o.title })));
  const body = h('div', { cls: 'wbody', style: { fontSize: (o.size || 24) + 'px' } }, h('span', { html: o.body }), h('b', { cls: 'caret' }));
  el.append(body);
  el.body = body;
  parent.append(el);
  return el;
}
