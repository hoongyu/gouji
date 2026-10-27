// Builds the chrome (chapter rail, agent rail, live-trace ticker, captions) and every scene into one paused
// timeline, then exposes window.seek(t) for the renderer.

const master = gsap.timeline({ paused: true });
const chrome = document.getElementById('chrome');

// ---------- chapter rail ----------
const rail = h('div', { id: 'rail' });
chrome.append(rail);
for (const c of TL.chapters) {
  const fill = h('div', { cls: 'fill' });
  const ch = h('div', { cls: 'ch' }, h('b', {}, c.n), c.name, h('div', { cls: 'bar' }, fill));
  rail.append(ch);
  master.to(ch, { color: '#0B1220', duration: 0.3 }, c.start);
  master.to(fill, { scaleX: 1, duration: c.end - c.start, ease: 'none' }, c.start);
  master.to(ch, { color: '#A3ADBD', duration: 0.3 }, c.end);
}
const brand = h('div', { id: 'brand', html: 'Pay<i>Proof</i>' });
chrome.append(brand);

// ---------- agent rail (chapter 3) ----------
const AGENTS = ['Guard', 'Planner', 'Investigator', 'Verifier', 'World Model', 'Decider', 'Reporter'];
const agentsEl = h('div', { id: 'agents' });
const agentPill = {};
AGENTS.forEach((a, i) => {
  if (i) agentsEl.append(h('span', { cls: 'sep' }, '›'));
  agentPill[a] = h('span', { cls: 'ag' }, a);
  agentsEl.append(agentPill[a]);
});
chrome.append(agentsEl);
const ch3 = TL.chapters[2];
master.to(agentsEl, { opacity: 1, duration: 0.4 }, ch3.start).to(brand, { opacity: 0, duration: 0.3 }, ch3.start);
master.to(agentsEl, { opacity: 0, duration: 0.4 }, ch3.end - 0.4);

// ---------- guarantee rail (chapter 4, until the close) ----------
const GUARANTEES = ['1 Words cannot move money', '2 Nothing pays without proof', '3 Anyone can check'];
const guarEl = h('div', { id: 'agents', style: { opacity: 0 } });
const guarPill = GUARANTEES.map((g, i) => {
  if (i) guarEl.append(h('span', { cls: 'sep' }, '·'));
  const el = h('span', { cls: 'ag' }, g);
  guarEl.append(el);
  return el;
});
chrome.append(guarEl);
const ch4 = TL.chapters[3];
const close = TL.scenes[TL.scenes.length - 1];
master.to(guarEl, { opacity: 1, duration: 0.4 }, ch4.start);
master.to(guarEl, { opacity: 0, duration: 0.4 }, close.start).to(brand, { opacity: 1, duration: 0.3 }, close.start);

// light one guarantee from t0 to t1
function guaranteeOn(tl, i, t0, t1) {
  const el = guarPill[i];
  tl.to(el, { color: '#fff', backgroundColor: TONE.green.fg, borderColor: TONE.green.fg, duration: 0.25 }, t0);
  tl.to(el, { color: '#6B7789', backgroundColor: 'rgba(0,0,0,0)', borderColor: '#D5DCE6', duration: 0.25 }, t1);
}

// light one agent from t0 to t1
function agentOn(tl, name, t0, t1) {
  const el = agentPill[name];
  const tone = name === 'World Model' ? TONE.violet : (name === 'Decider' || name === 'Contract') ? TONE.amber : TONE.blue;
  tl.to(el, { color: '#fff', backgroundColor: tone.fg, borderColor: tone.fg, duration: 0.25 }, t0);
  tl.to(el, { color: '#6B7789', backgroundColor: 'rgba(0,0,0,0)', borderColor: '#D5DCE6', duration: 0.25 }, t1);
}

// ---------- live trace ticker (chapter 3): the real trace of the run the scenes follow ----------
const ticker = h('div', { cls: 'abs', style: { left: '96px', top: '872px', width: '1728px', height: '36px',
  display: 'flex', alignItems: 'center', gap: '18px', opacity: 0 } });
const tickLabel = h('div', { cls: 'mono', style: { fontSize: '16px', fontWeight: 600, letterSpacing: '1.5px',
  color: '#08714E', display: 'flex', alignItems: 'center', gap: '8px', whiteSpace: 'nowrap' } },
  h('i', { style: { width: '9px', height: '9px', borderRadius: '50%', background: '#0E9F6E', display: 'inline-block' } }),
  'LIVE TRACE · run ui-20261026T233111');
const tickBox = h('div', { style: { position: 'relative', flex: '1', height: '36px', borderTop: '1.5px solid #D5DCE6' } });
ticker.append(tickLabel, tickBox);
chrome.append(ticker);
master.to(ticker, { opacity: 1, duration: 0.4 }, ch3.start + 0.3).to(ticker, { opacity: 0, duration: 0.3 }, ch3.end - 0.4);
let lastTick = null;
// show one trace line from t on: "time agent action summary"
function trace(tl, t, time, agent, action, summary) {
  const line = h('div', { cls: 'mono', style: { position: 'absolute', left: '0px', top: '7px', fontSize: '19px',
    whiteSpace: 'nowrap', color: '#3A4659', opacity: 0, visibility: 'hidden' } },
    h('span', { style: { color: '#A3ADBD' } }, time + '  '),
    h('span', { style: { color: '#0F4ACC', fontWeight: 600 } }, agent.padEnd(13, ' ')),
    h('span', { style: { color: '#6B7789' } }, action.padEnd(13, ' ')), summary);
  tickBox.append(line);
  if (lastTick && lastTick.t < t) tl.to(lastTick.el, { autoAlpha: 0, y: -8, duration: 0.25 }, t - 0.05);
  tl.fromTo(line, { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: 0.3, immediateRender: false }, t);
  lastTick = { el: line, t };
}

// ---------- captions ----------
const capLayer = document.getElementById('captions');
for (const sc of TL.scenes) {
  for (const c of sc.cues) {
    const el = h('div', { cls: 'cue' }, c.text);
    capLayer.append(el);
    master.to(el, { autoAlpha: 1, duration: 0.1 }, c.t0).to(el, { autoAlpha: 0, duration: 0.1 }, c.t1 - 0.1);
  }
}

// ---------- scenes ----------
const SCENE_ROOTS = {};
for (const info of TL.scenes) {
  const S = timing(info);
  const root = scene(info.id);
  SCENE_ROOTS[info.id] = root;
  showScene(master, root, S, info.id === 'S01' ? 0.01 : 0.45);
  if (!SCENES[info.id]) throw new Error('no scene ' + info.id);
  SCENES[info.id](master, S, root);
}

window.seek = (t) => { master.seek(t, false); return t; };
window.TOTAL = TL.total;
window.READY = false;
Promise.all([
  document.fonts.ready,
  document.fonts.load('600 52px "IBM Plex Sans"'), document.fonts.load('400 28px "IBM Plex Sans"'),
  document.fonts.load('500 28px "IBM Plex Sans"'), document.fonts.load('700 34px "IBM Plex Sans"'),
  document.fonts.load('500 22px "JetBrains Mono"'), document.fonts.load('600 52px "JetBrains Mono"'),
  document.fonts.load('400 22px "JetBrains Mono"'),
  ...[...document.images].map((im) => (im.complete ? 1 : new Promise((r) => { im.onload = im.onerror = r; }))),
]).then(() => { master.seek(0, false); window.READY = true; });
