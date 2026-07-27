// WCAG AA contrast audit of a rendered artifact, over the DevTools protocol.
//
//   node contrast-check.mjs <file.html> [more.html ...]
//
// No dependencies: Node's global WebSocket (Node 22+) and a headless Chrome that
// the caller has already started on CDP_PORT.
//
// Why this cannot be done in the Python harness: the harness reads CSS as text,
// so it can see `color:#EAE7DF` and `background:#e08e0b26` but not *which
// surface the element actually lands on*, nor how an 8-digit alpha colour
// composites against that surface. Three defects shipped in exactly that blind
// spot. Only a real layout engine can answer it.
const [, , ...files] = process.argv;
const PORT = Number(process.env.CDP_PORT || 9333);
const WIDTHS = (process.env.WIDTHS || '390,768,1280').split(',').map(Number);

const { webSocketDebuggerUrl } = await (
  await fetch(`http://127.0.0.1:${PORT}/json/version`)
).json();
const ws = new WebSocket(webSocketDebuggerUrl);
await new Promise((ok, bad) => { ws.onopen = ok; ws.onerror = bad; });

let id = 0;
const pending = new Map();
const events = [];
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data);
  if (msg.id && pending.has(msg.id)) {
    const { ok, bad } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? bad(new Error(JSON.stringify(msg.error))) : ok(msg.result);
  } else events.push(msg);
};
const send = (method, params = {}, sessionId) =>
  new Promise((ok, bad) => {
    const n = ++id;
    pending.set(n, { ok, bad });
    ws.send(JSON.stringify({ id: n, method, params, sessionId }));
  });

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
await send('Page.enable', {}, sessionId);

// Runs in the page. Kept as one self-contained expression so there is nothing to
// bundle and nothing to install.
const AUDIT = `(() => {
  const parse = (s) => {
    const m = String(s).match(/rgba?\\(([^)]+)\\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (fg, bg) => ({            // fg composited onto bg
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });
  const lum = (c) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const hex = (c) => '#' + [c.r, c.g, c.b]
    .map((v) => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();

  // Walk up compositing every background until opaque. Returns null if a
  // background-image (gradient) intervenes — we must not guess at those.
  const surfaceOf = (el) => {
    let stack = [], node = el, gradient = false;
    while (node && node !== document.documentElement.parentNode) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') gradient = true;
      const bg = parse(cs.backgroundColor);
      if (bg && bg.a > 0) {
        stack.push(bg);
        if (bg.a === 1) break;
      }
      node = node.parentElement;
    }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) base = over(stack[i], base);
    return { surface: base, gradient };
  };

  const out = [], seen = new Map();
  for (const el of document.querySelectorAll('body *')) {
    // Only elements that directly render text.
    const own = [...el.childNodes]
      .filter((n) => n.nodeType === 3 && n.textContent.trim())
      .map((n) => n.textContent.trim()).join(' ');
    if (!own) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (parseFloat(cs.opacity) === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    const fg0 = parse(cs.color);
    if (!fg0) continue;
    const { surface, gradient } = surfaceOf(el);
    // Fold element opacity into the foreground. Opacity does not change the
    // computed colour, so a naive colour-pair check cannot see it — but it fades
    // the text toward its backdrop exactly as an alpha channel would, and it was
    // being used to take already-marginal tile text further under AA.
    let eff = 1;
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      eff *= parseFloat(getComputedStyle(n).opacity);
    }
    const fg = over({ ...fg0, a: fg0.a * eff }, surface);
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3 : 4.5;
    const cr = ratio(fg, surface);
    if (cr >= need) continue;

    const key = el.tagName.toLowerCase() +
      (el.className && typeof el.className === 'string'
        ? '.' + el.className.trim().split(/\\s+/).join('.') : '');
    // Dedupe by selector: one bad rule should be one line, not 106.
    if (seen.has(key + hex(surface))) { seen.get(key + hex(surface)).count++; continue; }
    const rec = {
      key, count: 1, ratio: Math.round(cr * 100) / 100, need,
      fg: hex(fg), bg: hex(surface), size, weight, gradient,
      sample: own.slice(0, 46),
    };
    seen.set(key + hex(surface), rec);
    out.push(rec);
  }
  return JSON.stringify(out.sort((a, b) => a.ratio - b.ratio));
})()`;

let failures = 0;
for (const f of files) {
  for (const vw of WIDTHS) {
    await send('Emulation.setDeviceMetricsOverride', {
      width: vw, height: 900, deviceScaleFactor: 1, mobile: vw < 800,
    }, sessionId);
    const loaded = new Promise((ok) => {
      const t = setInterval(() => {
        if (events.some((e) => e.method === 'Page.loadEventFired')) {
          clearInterval(t); events.length = 0; ok();
        }
      }, 50);
    });
    await send('Page.navigate', { url: `file://${f}` }, sessionId);
    await loaded;
    await new Promise((r) => setTimeout(r, 400));

    const { result } = await send('Runtime.evaluate',
      { expression: AUDIT, returnByValue: true }, sessionId);
    const hits = JSON.parse(result.value);
    const name = f.split('/').pop();
    if (!hits.length) { console.log(`  ok        ${name} @${vw}px`); continue; }
    failures += hits.length;
    console.log(`  FAIL      ${name} @${vw}px — ${hits.length} pairing(s) under AA`);
    for (const h of hits) {
      console.log(`              ${String(h.ratio).padStart(5)}:1 (need ${h.need})  ` +
        `${h.fg} on ${h.bg}  ${h.size}px/${h.weight}  ×${h.count}` +
        `${h.gradient ? '  [over gradient — approx]' : ''}`);
      console.log(`                    ${h.key}`);
      console.log(`                    "${h.sample}"`);
    }
  }
}
ws.close();
console.log(failures ? `\ncontrast: ${failures} finding(s)` : '\ncontrast: all text meets WCAG AA');
process.exit(failures ? 1 : 0);
