// Measure rendered page width at a given device width, via the Chrome DevTools
// Protocol. No dependencies: Node's global WebSocket (Node 22+) plus a headless
// Chrome that responsive.sh has already started on PORT.
//
//   node measure-width.mjs <device-width> <file.html> [more.html ...]
//
// Exits non-zero if any page's document is wider than the device.
const [, , widthArg, ...files] = process.argv;
const VW = Number(widthArg);
const PORT = Number(process.env.CDP_PORT || 9333);

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

const out = [];
for (const f of files) {
  await send('Emulation.setDeviceMetricsOverride', {
    width: VW, height: 812, deviceScaleFactor: 1, mobile: VW < 800,
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
  await new Promise((r) => setTimeout(r, 400)); // the register table is built by inline JS

  const { result } = await send('Runtime.evaluate', {
    expression: `JSON.stringify({
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
      widest: (() => {
        const hits = [], seen = new Set();
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect();
          if (r.right > ${VW} + 1) {
            hits.push({ right: Math.round(r.right),
                        el: (el.tagName + '.' + (el.className || '(none)')).slice(0, 60) });
          }
        }
        return hits.sort((a, b) => b.right - a.right)
                   .filter(h => !seen.has(h.el) && seen.add(h.el)).slice(0, 4);
      })(),
    })`,
    returnByValue: true,
  }, sessionId);
  out.push({ file: f.split('/').pop(), ...JSON.parse(result.value) });
}

// Compare against the DEVICE width, never window.innerWidth. When content
// overflows, Chrome zooms the visual viewport out to fit it, so innerWidth grows
// to equal scrollWidth and a check written against it can never fail. That very
// mistake made the first version of this script report a broken page as clean.
const bad = (r) => r.scrollWidth > VW + 1;
for (const r of out) {
  console.log(
    `  ${bad(r) ? 'OVERFLOW' : 'ok      '}  ${r.file.padEnd(24)} ` +
    `page=${String(r.scrollWidth).padStart(5)}px  device=${VW}px`,
  );
  if (bad(r)) for (const h of r.widest) console.log(`              ${h.el} @ ${h.right}px`);
}
ws.close();
process.exit(out.some(bad) ? 1 : 0);
