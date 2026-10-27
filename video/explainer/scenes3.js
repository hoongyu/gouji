// Chapter 3, second half, and chapter 4: grades and the mandate, the brief, the contract, the proof, the close.

// ---------- S09: grades, then the signed mandate decides ----------
SCENES.S09 = (tl, S, root) => {
  const W = root.wires;
  title(root, '', 'Decider: the controller&rsquo;s signed policy decides');
  agentOn(tl, 'Decider', S.start + 0.2, S.end);
  trace(tl, S.w('mandate'), '23:33:26', 'Decider', 'decide', 'mandate engine: ask (default)');

  const G = [['identity', 0, 'red flags F2 to F5, doppelganger'], ['account', 0, 'red flags F6 to F8, account in LV'],
    ['price', 1, 'invoice matches the contract in force'], ['receipt', 1, 'order and goods receipt agree'],
    ['duplicate', 1, 'checked, nothing found'], ['channel', 0, 'red flag F13, look-alike domain'], ['injection', 0, 'red flag F1, text aimed at the AI']];
  const tag = (ok) => `<span class="tag" style="color:${ok ? '#08714E' : '#B4232A'};background:${ok ? '#E5F6EF' : '#FDECEC'}">${ok ? 'VERIFIED' : 'NOT VERIFIED'}</span>`;
  const tbl = h('table', { cls: 'tbl tight', style: { left: '96px', top: '214px', width: '860px' } },
    h('tr', {}, h('th', { style: { width: '22%' } }, 'Aspect'), h('th', { style: { width: '27%' } }, 'Grade'), h('th', {}, 'Why')),
    ...G.map(([a, ok, why]) => h('tr', {}, h('td', { cls: 'm', style: { fontSize: '21px' } }, a), h('td', { html: tag(ok) }),
      h('td', { style: { fontSize: '21px', color: '#3A4659', whiteSpace: 'normal' } }, why))));
  root.append(tbl);
  const trs = [...tbl.querySelectorAll('tr')];

  // the rule, written out, with the systems it trusts
  const rule = text(root, { x: 96, y: 652, w: 860, html: 'VERIFIED needs two independent trusted systems that agree', size: 26, weight: 600 });
  const trusted = [['ERP', 96], ['Vendor master', 212], ['Contracts', 428], ['Registry', 610]].map(([x, xx]) => tick(root, { x: xx, y: 704, text: x, size: 22 }));
  const mail = tick(root, { x: 96, y: 756, text: 'Mailbox: never trusted', ok: false, size: 22 });
  const attacker = annot(root, W, { x: 420, y: 760, w: 360, text: 'that is where the attacker writes', tone: 'red', size: 20 });

  const clause = (id, eff, what) => `<div class="cl" style="padding:12px 26px;border-top:1px solid #EEF2F7">
    <div style="display:flex;align-items:baseline;gap:14px"><span class="mono" style="font-size:22px;font-weight:600">${id}</span>
    <span class="tag" style="color:#9A5B00;background:#FFF3DF">${eff}</span><span class="res mono" style="margin-left:auto;font-size:19px;font-weight:600"></span></div>
    <div style="font-size:20px;color:#3A4659;margin-top:5px">${what}</div></div>`;
  const man = paper(root, { x: 1010, y: 200, w: 814, kind: 'policy', kicker: 'PAYMENT POLICY · SIGNED', title: 'ap-payments', idText: 'v2', tone: 'amber',
    signedBy: 'the controller · Ed25519 bcdf6089',
    rows: [{ cls: 'x', html: clause('P1', 'ALLOW', 'Payee in the signed registry, every required aspect VERIFIED, up to EUR 250,000') },
      { cls: 'x', html: clause('P2', 'ALLOW', 'Every required aspect VERIFIED, up to EUR 250,000') },
      { cls: 'x', html: clause('Default', 'ASK', 'The AP specialist on duty decides') }] });
  const res = [...man.querySelectorAll('.res')];
  const cls = [...man.querySelectorAll('.cl')];
  clearBg(cls);
  const link = wire(W, { pts: [[956, 420], [1010, 420]], tone: 'amber', w: 3 });
  const ask = h('div', { cls: 'abs', style: { left: '1010px', top: '700px', width: '814px', height: '140px', background: '#E8890C', color: '#fff',
    padding: '22px 30px', borderRadius: '2px', display: 'flex', alignItems: 'center', gap: '30px' } },
    h('div', { cls: 'mono', style: { fontSize: '76px', fontWeight: 700, letterSpacing: '-2px' } }, 'ASK'),
    h('div', { style: { fontSize: '26px', fontWeight: 500, lineHeight: '1.35' } }, 'A person decides. No execution contract is issued.'));
  root.append(ask);

  const tg = S.w('grades');
  stagger(tl, trs, tg - 0.3, 0.13, (tl2, el, at) => fade(tl2, el, at, 0.25));
  fade(tl, tbl, tg - 0.35, 0.2);
  rise(tl, rule, S.w('verified'), { dy: 12 });
  stagger(tl, trusted, S.w('two independent'), 0.15, (tl2, el, at) => fade(tl2, el, at, 0.25));
  fade(tl, mail, S.w('mailbox'), 0.25);
  pulse(tl, mail, S.w('never counts'));
  note(tl, attacker, S.w('attacker') - 0.1);
  rise(tl, man, S.w('mandate') - 0.2, { dy: 14 });
  draw(tl, link, S.w('against'), 0.4);
  const tn = S.w('No clause');
  tl.to(res[0], { text: { value: '✕ payee not in registry' }, color: '#B4232A', duration: 0.01 }, tn);
  tl.to(cls[0], { backgroundColor: '#FFF7F7', duration: 0.25 }, tn);
  tl.to(res[1], { text: { value: '✕ 4 aspects not verified' }, color: '#B4232A', duration: 0.01 }, tn + 0.45);
  tl.to(cls[1], { backgroundColor: '#FFF7F7', duration: 0.25 }, tn + 0.45);
  tl.to(res[2], { text: { value: '✓ applies' }, color: '#9A5B00', duration: 0.01 }, tn + 0.9);
  tl.to(cls[2], { backgroundColor: '#FFF3DF', duration: 0.25 }, tn + 0.9);
  rise(tl, ask, S.we('payment'), { dy: 16 });
};

// ---------- S10: the brief, for the person who decides ----------
SCENES.S10 = (tl, S, root) => {
  const W = root.wires;
  title(root, '', 'Reporter: a brief a person can check');
  agentOn(tl, 'Reporter', S.start + 0.2, S.end);
  trace(tl, S.start + 0.6, '23:33:34', 'Reporter', 'brief', 'brief by model; 0 uncited sentences removed');

  const say = bubble(root, { x: 170, y: 212, w: 520, html: 'I plan the follow-up checks and write the brief.', size: 24 });
  const model = figure(root, { x: 96, y: 318, w: 300, h: 60, row: true, icon: 'bot', iconSize: 44, label: 'Model', size: 24 });
  const noVote = annot(root, W, { x: 300, y: 330, w: 360, text: 'no vote on payment', tone: 'red', size: 24 });
  const ask = stamp(root, { x: 110, y: 430, text: 'ASK', tone: 'amber', size: 46 });
  const askWhy = text(root, { x: 290, y: 446, w: 420, html: 'decided by the signed policy', size: 22, color: '#6B7789' });
  const who = person(root, { x: 110, y: 560, w: 130, tone: 'blue' });
  const whoLb = text(root, { x: 270, y: 584, w: 420, html: '<b style="font-size:30px">AP specialist</b><br><span style="color:#6B7789">decides, with the brief in hand</span>', size: 21 });
  const w1 = wire(W, { pts: [[175, 500], [175, 560]], tone: 'ink', w: 3 });
  const w2 = wire(W, { pts: [[690, 625], [780, 625]], tone: 'blue', w: 3 });
  const br = browser(root, { x: 780, y: 196, w: 1044, h: 664, url: 'localhost:8010/brief/INV-5567', src: 'assets/brief5567.png',
    imgW: 1920, imgH: 10500, view: { x: 0, y: 0, scale: 1044 / 1920 } });
  const mHold = mark(br, { x: 238, y: 216, w: 1444, h: 210, tone: 'red', bw: 7 });
  const mWhy = mark(br, { x: 238, y: 520, w: 1444, h: 335, tone: 'blue', bw: 6 });
  const mNote = mark(br, { x: 238, y: 860, w: 1220, h: 44, tone: 'blue', bw: 5 });
  hide(mHold, mWhy, mNote);
  const cite = annot(root, W, { x: 96, y: 790, w: 620, text: 'every sentence cites findings [F1] … [F14]', tone: 'blue', size: 22 });

  rise(tl, say, S.start + 0.3, { dy: 12 });
  fade(tl, model, S.start + 0.4, 0.3);
  note(tl, noVote, S.w('not'));
  tl.to(say, { opacity: 0.5, duration: 0.3 }, S.w('not') + 0.2);
  pop(tl, ask, S.w('decide') - 0.1, { from: 1.6, ease: 'power3.out', dur: 0.3 });
  fade(tl, askWhy, S.w('decide') + 0.1, 0.3);
  draw(tl, w1, S.w('person') - 0.15, 0.3);
  pop(tl, who, S.w('person'));
  fade(tl, whoLb, S.w('person') + 0.1, 0.3);
  draw(tl, w2, S.w('brief') - 0.3, 0.3);
  slide(tl, br, S.w('brief') - 0.2, { dx: 60 });
  fade(tl, mHold, S.w('hold'), 0.25);
  view(tl, br, { x: 200, y: 160, scale: 0.72 }, S.w('Every') - 0.5, 0.9);
  fade(tl, mWhy, S.w('Every') + 0.2, 0.3);
  fade(tl, mNote, S.w('links') + 0.2, 0.3);
  note(tl, cite, S.w('evidence'));
};

// ---------- chapter 4: why trust it. Numbers below come from the runs in output_examples/ ----------
const PROOF = {
  contract: 'EC-96e4f180', notaryKey: '2c9d7b4e', facts: '38dd5434', evidence: '8a07e706', cells: 17, policy: '3086c1d7',
  queries: 35,
  verify: [
    "The policy carries the controller's signature",
    'The decision was taken under this policy',
    'Every cited cell reads the same in zetaris today: 18 of 18',
    'The evidence root matches the cited cells',
    'The World Model raises the same alerts',
    'The signed mandate decides the same on this evidence: allow',
    "The contract carries the notary's signature",
    "The notary's cells read the same in zetaris today: 17 of 17",
    'The contract binds this payment, this evidence and this policy',
    'Run again without a model, it releases it too',
  ],
  verifyEnd: 'VALID: 10 of 10 checks pass (46 queries on zetaris)',
};

// ---------- S11: guarantee 1, words cannot move money (the model handed to the attacker) ----------
SCENES.S11 = (tl, S, root) => {
  const W = root.wires;
  title(root, '1', 'Words cannot move money');
  guaranteeOn(tl, 0, S.start + 0.2, S.end);
  const model = figure(root, { x: 96, y: 360, w: 420, h: 110, row: true, icon: 'bot', iconSize: 84, tone: 'blue',
    label: 'The model', sub: 'plans, screens, writes', size: 36 });
  const evil = chip(root, { x: 96, y: 492, text: 'now controlled by the attacker', tone: 'red', solid: true, size: 22, icon: 'triangle-alert' });
  const said = [
    ['“No injection here.”', 'Guard', 'its pattern screen runs anyway', 'blue'],
    ['“No more checks needed.”', 'Notary', 'runs every check again, with no model', 'amber'],
    ['“Safe to pay. Release today.” [F99]', 'Brief filter', 'removes the sentence', 'blue'],
  ];
  const rows = said.map(([q, who, what, tone], i) => {
    const y = 226 + i * 160;
    const b = bubble(root, { x: 600, y, w: 560, html: q, tone: 'red', size: 23, mono: true, ink: '#B4232A' });
    b.g = { x: 600, y, w: 560, h: 74 };
    const wallBar = shape(root, { kind: 'process', x: 1268, y: y - 18, w: 26, h: 120, tone, solid: true });
    const lb = text(root, { x: 1322, y: y - 4, w: 500, html: `<b style="font-size:30px">${who}</b><br><span style="color:#6B7789">${what}</span>`, size: 21, lh: 1.35 });
    const a = wire(W, { pts: [[516, 415], [560, 415], [560, y + 37], [600, y + 37]], tone: 'red', w: 3, headSize: 0.8 });
    const hit = wire(W, { pts: [[1160, y + 37], [1262, y + 37]], tone: 'red', w: 3, headSize: 0.8 });
    return { b, wallBar, lb, a, hit };
  });
  const stat1 = h('div', { cls: 'abs', style: { left: '96px', top: '716px', width: '560px', borderTop: '3px solid #0B1220', paddingTop: '10px' } },
    h('div', { cls: 'mono', style: { fontSize: '88px', fontWeight: 600, color: '#08714E', lineHeight: '1' } }, '0 / 18'),
    h('div', { style: { fontSize: '21px', color: '#3A4659', marginTop: '8px' } }, 'attacks after money paid, held-out set'));
  const stat2 = h('div', { cls: 'abs', style: { left: '720px', top: '736px', width: '380px', borderTop: '3px solid #0B1220', paddingTop: '10px' } },
    h('div', { cls: 'mono', style: { fontSize: '52px', fontWeight: 600, color: '#0B1220', lineHeight: '1' } }, '80'),
    h('div', { style: { fontSize: '20px', color: '#3A4659', marginTop: '8px' } }, 'sentences arguing for payment, removed'));
  root.append(stat1, stat2);
  const same = tick(root, { x: 1180, y: 790, text: 'the same releases as with no model at all', size: 22 });

  rise(tl, model, S.start + 0.4, { dy: 14 });
  const ta = S.w('attacker');
  tl.to(model.querySelector('svg'), { color: '#E5383B', duration: 0.3 }, ta);
  model.querySelectorAll('.fic svg *').forEach((n) => tl.to(n, { attr: { stroke: '#E5383B' }, duration: 0.3 }, ta));
  pop(tl, evil, ta + 0.15);
  [['denied', 0], ['skipped', 1], ['argued', 2]].forEach(([word, i]) => {
    const t = S.w(word), r = rows[i];
    draw(tl, r.a, t - 0.25, 0.35);
    pop(tl, r.b, t, { from: 0.8 });
    draw(tl, r.hit, t + 0.35, 0.25);
    pop(tl, r.wallBar, t + 0.55, { from: 0.4 });
    fade(tl, r.lb, t + 0.6, 0.3);
    tl.to(r.b, { opacity: 0.4, duration: 0.3 }, t + 0.95);
    tl.to(r.b, { textDecoration: 'line-through', duration: 0.01 }, t + 0.95);
  });
  const tn = S.w('single');
  rise(tl, stat1, tn - 0.3);
  rise(tl, stat2, tn);
  fade(tl, same, S.w('extra') + 0.2, 0.3);
};

// ---------- S12: guarantee 2, nothing pays without proof (notary and gateway) ----------
SCENES.S12 = (tl, S, root) => {
  const W = root.wires;
  title(root, '2', 'Nothing pays without proof');
  guaranteeOn(tl, 1, S.start + 0.2, S.end);
  const asp = ['identity', 'account', 'price', 'receipt', 'duplicate', 'channel', 'injection']
    .map((a) => `<span class="tag" style="color:#08714E;background:#E5F6EF;font-size:16px">✓ ${a}</span>`).join(' ');
  const inv = paper(root, { x: 96, y: 226, w: 540, kind: 'invoice', kicker: 'INVOICE · BANK CHANGE', title: 'Quorvane Cables GmbH', idText: 'INV-5559', tone: 'green',
    rows: [['Amount', 'EUR 3,861.20'], { html: `<div style="display:flex;flex-wrap:wrap;gap:6px">${asp}</div>` }] });
  const allow = annot(root, W, { x: 96, y: 520, w: 500, text: 'agents and the signed policy: ALLOW', tone: 'amber', size: 21 });
  const big = seal(root, { x: 770, y: 318, r: 96, center: 'NOTARY', ring: 'NO MODEL · ONLY SIGNER · ', repeat: 2, ringSize: 12, ls: 1.4, centerSize: 26, rot: -6 });
  const nlb = text(root, { x: 890, y: 236, w: 420, html: '<b style="font-size:36px">Notary</b><br><span style="color:#6B7789">no model · the only signing key</span>', size: 21, lh: 1.35 });
  const q = text(root, { x: 890, y: 332, w: 420, html: 'every check again: <span class="mono n" style="font-weight:600">0</span> queries', size: 22, color: '#3A4659' });
  const pol = tick(root, { x: 890, y: 372, text: 'the controller’s signature on the policy', size: 20 });
  const con = paper(root, { x: 700, y: 470, w: 600, kind: 'contract', kicker: 'EXECUTION CONTRACT', title: PROOF.contract, tone: 'amber',
    rows: [['Payment', `sha256 ${PROOF.facts}…`], ['Evidence', `${PROOF.cells} cells · root ${PROOF.evidence}…`], ['Policy', `sha256 ${PROOF.policy}…`],
      ['Valid for', '<span class="ttl">15:00</span> · uses left <span class="uses">1</span>']] });
  con.querySelector('.t').style.fontFamily = "'JetBrains Mono', monospace";
  const [rPay, rEv, rPol, rTtl] = con.rows;
  clearBg(con.rows);
  const ttlEl = con.querySelector('.ttl'), uses = con.querySelector('.uses');
  const mini = seal(root, { x: 1232, y: 802, r: 46, center: 'ED25519', ring: 'NOTARY · ', repeat: 3, ringSize: 9, ls: 1, centerSize: 14, rot: -10 });
  const gw = lock(root, { x: 1560, y: 236, w: 130, tone: 'ink' });
  const gwLb = text(root, { x: 1460, y: 410, w: 364, align: 'center', html: '<b style="font-size:30px">Gateway</b><br><span style="color:#6B7789">holds only the notary’s public key</span>', size: 20, lh: 1.35 });
  const w0 = wire(W, { pts: [[636, 318], [674, 318]], tone: 'amber', w: 3 });
  const w1 = wire(W, { pts: [[770, 414], [770, 470]], tone: 'amber', w: 3 });
  const w2 = wire(W, { pts: [[1300, 640], [1625, 640], [1625, 500]], tone: 'green', w: 3 });
  const paid = stamp(root, { x: 1700, y: 260, text: 'Paid', tone: 'green', size: 34 });
  const no1 = text(root, { x: 1460, y: 700, w: 364, html: 'signed with any other key: <b>refused</b>', cls: 'note', size: 21, color: '#B4232A' });
  const no2 = text(root, { x: 1460, y: 738, w: 364, html: 'the same contract again: <b>refused</b>', cls: 'note', size: 21, color: '#B4232A' });
  const no3 = text(root, { x: 1460, y: 776, w: 364, html: 'another amount or account: <b>refused</b>', cls: 'note', size: 21, color: '#B4232A' });

  rise(tl, inv, S.start + 0.3, { dy: 16 });
  note(tl, allow, S.start + 0.8);
  const tn = S.w('notary');
  draw(tl, w0, tn - 0.3, 0.3);
  stampOn(tl, big, tn);
  fade(tl, nlb, tn + 0.2, 0.3);
  const tr = S.w('runs');
  fade(tl, q, tr);
  count(tl, q.querySelector('.n'), PROOF.queries, tr, 1.6);
  fade(tl, pol, S.w('controller'), 0.3);
  const ts = S.w('signs');
  draw(tl, w1, ts - 0.3, 0.3);
  rise(tl, con, ts, { dy: 16 });
  stampOn(tl, mini, ts + 0.4);
  tl.to(rPay, { backgroundColor: '#FFF3DF', duration: 0.25 }, S.w('payment'));
  tl.to(rEv, { backgroundColor: '#FFF3DF', duration: 0.25 }, S.w('evidence'));
  tl.to(rPol, { backgroundColor: '#FFF3DF', duration: 0.25 }, S.w('evidence') + 0.3);
  tl.to(rTtl, { backgroundColor: '#FFF3DF', duration: 0.25 }, S.w('fifteen'));
  count(tl, ttlEl, 893, S.w('fifteen') + 0.2, 3.5, (v) => { const s = Math.round(v); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }, 900);
  const tg = S.w('gateway');
  pop(tl, gw, tg - 0.1);
  fade(tl, gwLb, tg, 0.3);
  draw(tl, w2, tg + 0.4, 0.5);
  travel(tl, packet(W, { tone: 'green', r: 9 }), w2, tg + 0.6, 0.6);
  unlock(tl, gw, tg + 1.15);
  pop(tl, paid, tg + 1.3, { from: 1.6, ease: 'power3.out', dur: 0.3 });
  tl.to(uses, { text: { value: '0' }, duration: 0.01 }, tg + 1.2);
  stagger(tl, [no1, no2, no3], S.w('public') + 0.1, 0.25, fade);
};

// ---------- S13: guarantee 3, anyone can check the proof ----------
SCENES.S13 = (tl, S, root) => {
  const W = root.wires;
  title(root, '3', 'Anyone can check the proof');
  guaranteeOn(tl, 2, S.start + 0.2, S.end);
  const term = win(root, { x: 96, y: 222, w: 1150, h: 610, title: 'terminal · gouji', body: '', size: 21 });
  term.body.innerHTML = '';
  term.body.style.lineHeight = '1.75';
  const cmd = h('span', { cls: 'ln' });
  const cmdText = '$ uv run python run.py verify INV-5559-proof.json --backend zetaris';
  const lines = PROOF.verify.map((l) => h('span', { cls: 'ln', html: `  <span style="color:#08714E;font-weight:600">[ok]</span> ${l}` }));
  const end = h('span', { cls: 'ln', html: `<b style="color:#08714E">${PROOF.verifyEnd}</b>` });
  term.body.append(cmd, h('span', { cls: 'ln', html: '&nbsp;' }), ...lines, end);
  for (const el of [cmd, ...lines, end]) el.style.display = 'block';
  hide(lines, end);
  // what the lines prove, pointed at from the side
  const lineY = (i) => 222 + 34 + 18 + 21 * 1.75 * (i + 2) + 18;
  const notes = [
    { text: '<b>Two signatures</b><br>the controller’s on the policy, the notary’s on the contract', line: 0, y: 300, size: 22 },
    { text: '<b>Every cell, again</b><br>re-read through Zetaris, at the source', line: 2, y: 440, size: 22 },
    { text: '<b>The decision, again</b><br>derived by the program, then re-run with no model', line: 9, y: 640, size: 22 },
  ].map((n) => annot(root, W, { x: 1300, y: n.y, w: 524, text: n.text, size: n.size, from: [1290, n.y + 16], to: [1246, lineY(n.line)] }));
  const valid = stamp(root, { x: 1360, y: 770, text: 'Valid · 10 of 10', tone: 'green', size: 36 });

  fade(tl, term, S.start + 0.3);
  type(tl, cmd, cmdText, S.w('One'), 70);
  const tr = S.w('rereads');
  stagger(tl, lines.slice(0, 5), tr, 0.28, fade);
  note(tl, notes[0], S.w('check'));
  note(tl, notes[1], tr + 0.4);
  const td = S.w('derives');
  stagger(tl, lines.slice(5), td, 0.25, fade);
  note(tl, notes[2], td + 0.6);
  fade(tl, end, S.w('Ten'));
  pop(tl, valid, S.w('pass'), { from: 1.6, ease: 'power3.out', dur: 0.3 });
};

// ---------- S14: the sealed held-out test ----------
SCENES.S14 = (tl, S, root) => {
  title(root, '', 'Tested on attacks we never saw');
  guaranteeOn(tl, 0, S.start + 0.2, S.end);
  guaranteeOn(tl, 1, S.start + 0.2, S.end);
  guaranteeOn(tl, 2, S.start + 0.2, S.end);
  const head = text(root, { x: 96, y: 222, w: 640, html: '44 requests, written by NVIDIA Nemotron', size: 30, weight: 600 });
  const grid = h('div', { cls: 'abs', style: { left: '96px', top: '290px', width: '640px', display: 'flex', flexWrap: 'wrap', gap: '10px' } });
  const sq = [];
  for (let i = 0; i < 44; i++) {
    const kind = i < 18 ? 'money' : i < 24 ? 'text' : 'normal';
    const [bd, bg] = { money: ['#E5383B', '#FDECEC'], text: ['#E8890C', '#FFF3DF'], normal: ['#A3ADBD', '#F1F4F8'] }[kind];
    const el = h('div', { style: { width: '48px', height: '48px', border: `2px solid ${bd}`, background: bg, borderRadius: '2px' } });
    grid.append(el);
    sq.push(el);
  }
  root.append(grid);
  const legend = text(root, { x: 96, y: 532, w: 680, html: '<span style="color:#B4232A;font-weight:600">18 attacks after money</span> · <span style="color:#9A5B00;font-weight:600">6 instructions only</span> · <span style="color:#6B7789;font-weight:600">20 normal</span>', size: 21 });
  const seal = stamp(root, { x: 300, y: 360, text: 'Sealed', tone: 'blue', size: 40 });
  const sealNote = text(root, { x: 96, y: 580, w: 640, html: 'Committed (efa9fec) before the first run, with a SHA-256 of every file. No code was tuned on it.', cls: 'note', size: 21 });

  const X0 = 860, BW = 480;
  const chartT = text(root, { x: X0, y: 222, w: 964, html: 'Attacks after money not owed, paid without a human, of 18', size: 25, weight: 600 });
  const bars = [['Payee list', 9, '#E5383B', 'EUR 170,800'], ['PayProof, no model', 0, '#0E9F6E'], ['PayProof, model screen', 0, '#0E9F6E'],
    ['PayProof, attacker&rsquo;s model', 0, '#0E9F6E']].map(([lb, v, c, eur], i) => {
    const y = 280 + i * 78;
    const label = text(root, { x: X0, y: y + 10, w: 330, html: lb, size: 22, color: '#3A4659' });
    const track = h('div', { cls: 'abs', style: { left: X0 + 340 + 'px', top: y + 'px', width: BW + 'px', height: '50px', background: '#F1F4F8' } });
    const bar = h('div', { cls: 'abs', style: { left: '0px', top: '0px', height: '50px', width: Math.max(6, (BW * v) / 18) + 'px', background: c, transformOrigin: '0 50%' } });
    track.append(bar);
    root.append(track);
    const val = text(root, { x: X0 + 340 + Math.max(6, (BW * v) / 18) + 14, y: y + 6, w: 360, html: `<span class="n">0</span> / 18${eur ? ` <span style="font-size:20px;color:#B4232A">${eur}</span>` : ''}`, size: 28, weight: 600, mono: true, color: c });
    return { label, track, bar, val, v };
  });
  const chart2T = text(root, { x: X0, y: 610, w: 964, html: 'Normal payments interrupted, of 20', size: 25, weight: 600 });
  const nums = [['Payee list', 4], ['PayProof, every configuration', 0]].map(([lb, v], i) => {
    const el = h('div', { cls: 'abs', style: { left: X0 + i * 420 + 'px', top: '656px', width: '400px', borderTop: '3px solid #0B1220', paddingTop: '10px' } },
      h('div', { cls: 'mono', style: { fontSize: '44px', fontWeight: 600, color: v ? '#E5383B' : '#08714E' } }, `${v} / 20`),
      h('div', { style: { fontSize: '19px', color: '#6B7789' } }, lb));
    root.append(el);
    return el;
  });

  const tn = S.w('NVIDIA');
  fade(tl, head, tn - 0.3);
  stagger(tl, sq, tn - 0.2, 0.03, (tl2, el, at) => pop(tl2, el, at, { dur: 0.3 }));
  fade(tl, legend, tn + 1.0);
  pop(tl, seal, S.w('sealed'), { from: 1.7, ease: 'power3.out', dur: 0.35 });
  fade(tl, sealNote, S.w('sealed') + 0.4);
  fade(tl, chartT, S.w('payee') - 0.4);
  const at = [S.w('payee'), S.w('none'), S.w('even') + 0.2, S.w('attackers')];
  bars.forEach((b, i) => {
    const t = at[i];
    fade(tl, b.label, t - 0.2, 0.3);
    fade(tl, b.track, t - 0.2, 0.3);
    gsap.set(b.bar, { scaleX: 0 });
    tl.to(b.bar, { scaleX: 1, duration: 0.9, ease: 'power2.out' }, t);
    fade(tl, b.val, t, 0.2);
    count(tl, b.val.querySelector('.n'), b.v, t, 0.9);
  });
  fade(tl, chart2T, S.w('interrupted') - 0.2);
  stagger(tl, nums, S.w('interrupted'), 0.3, rise);
};

// ---------- S15: the close ----------
SCENES.S15 = (tl, S, root) => {
  const ttlEl = title(root, '', 'Who carries what');
  const M = buildMap(root);
  const { N, Wd } = M;
  gsap.set(M.world, MAP_VIEW);
  for (const w of [Wd.loop, ...Wd.row, Wd.inv, Wd.ver, Wd.trunk, Wd.bus, ...Wd.drops, Wd.man, Wd.con, Wd.pay, Wd.brief]) drawn(w);
  const tag1 = annot(M.world, M.W, { x: 640, y: 752, w: 760, text: 'Zetaris: every query and every re-read, in place', tone: 'blue', size: 25 });
  const tag2 = annot(M.world, M.W, { x: 1515, y: 350, w: 330, text: 'Meterless World Model', tone: 'violet', size: 25 });
  const tag3 = annot(M.world, M.W, { x: 15, y: 330, w: 260, text: 'red team:<br>NVIDIA Nemotron', tone: 'green', size: 24 });
  const tag4 = annot(M.world, M.W, { x: 1560, y: 56, w: 280, align: 'right', text: 'mandate-engine v0.1.1', tone: 'amber', size: 22 });
  hide(tag1, tag2, tag3, tag4);
  const tz = S.w('Zetaris');
  pulse(tl, N.zet, tz);
  N.sys.forEach((b, i) => light(tl, b, 'blue', tz + 0.2 + i * 0.06, 0.3, { frame: true, fill: true }));
  rise(tl, tag1, tz + 0.2);
  const tw = S.w('World');
  pulse(tl, N.wm, tw);
  light(tl, N.wm, 'violet', tw, 0.3, { frame: true, fill: true });
  rise(tl, tag2, tw + 0.2);
  rise(tl, tag3, tw + 0.7);
  rise(tl, tag4, tw + 1.0);

  const tp = S.w('PayProof');
  tl.to(M.world, { autoAlpha: 0, scale: 0.68, x: 140, y: 175, duration: 0.6, ease: 'power2.in' }, tp - 0.35);
  out(tl, ttlEl, tp - 0.35);
  const end = h('div', { cls: 'abs', style: { left: '96px', top: '230px', width: '1728px' } },
    h('div', { style: { fontSize: '168px', fontWeight: 600, letterSpacing: '-5px', lineHeight: '1' }, html: 'Pay<span style="color:#1F6BFF">Proof</span>' }),
    h('div', { style: { fontSize: '64px', fontWeight: 600, marginTop: '30px', lineHeight: '1.1', letterSpacing: '-1px' } }, 'No proof, no payment.'),
    h('div', { style: { fontSize: '30px', fontWeight: 400, marginTop: '18px', color: '#3A4659', maxWidth: '1500px' } }, 'The checkpoint before money moves: it explains why, and pays only against a notary’s signed proof.'),
    h('div', { cls: 'mono', style: { fontSize: '24px', color: '#3A4659', marginTop: '48px', paddingTop: '22px', borderTop: '3px solid #0B1220', display: 'flex', gap: '40px', flexWrap: 'wrap' } },
      h('span', {}, 'github.com/hoongyu/gouji'), h('span', {}, 'open source · MIT'), h('span', {}, 'runs on a CPU'), h('span', {}, 'sample mode needs no keys')),
    h('div', { cls: 'mono', style: { fontSize: '21px', color: '#6B7789', marginTop: '18px' } }, 'Zetaris · Meterless World Model · NVIDIA Nemotron · mandate-engine v0.1.1'));
  root.append(end);
  rise(tl, end, tp + 0.15, { dy: 24, dur: 0.8 });
};
