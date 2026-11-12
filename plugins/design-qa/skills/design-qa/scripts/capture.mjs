#!/usr/bin/env node
// Annotated staging screenshots via headless Chrome (CDP). No npm deps; needs Node 22+ and Google Chrome.
//
// Usage: node capture.mjs <spec.json>
//
// spec.json:
// {
//   "url": "https://staging.example.com/page/",
//   "outDir": "/abs/path/shots",
//   "hideSelectors": ["#wpml-banner"],          // optional: hidden on every shot (dev banners, cookie bars)
//   "shots": [
//     {
//       "key": "slider-height",                   // output: <outDir>/staging_<key>.png
//       "viewport": "desktop",                    // "desktop" (1440x900) | "mobile" (390x844 @2x) | {"width":..,"height":..,"dpr":..,"mobile":bool}
//       "script": "JS run in page; must evaluate to a clip {x,y,w,h} in page coords"
//     }
//   ]
// }
//
// Helpers available inside "script":
//   __mark(el, label, pos)   red outline around el, optional red label above (or pos='below'); returns el rect
//   __box(x, y, w, h, label) dashed red box at page coords (for "missing element" bugs)
//   __guide(x, label)        cyan dashed vertical guide line at page x (e.g. expected left edge)
//   __abs(el, pad=24)        clip {x,y,w,h} around el, page coords (pad=0 for whole sections)
//   __hideHeader()           hides fixed/sticky site header so it doesn't cover the shot
//
// Example script:
//   "__hideHeader(); const s=document.querySelector('section.faq'); const p=s.querySelector('p'); __mark(p,'Colour #1E2939 – Figma #575757'); __abs(s,0)"

import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const spec = JSON.parse(readFileSync(process.argv[2], 'utf8'));
mkdirSync(spec.outDir, { recursive: true });
const CHROME = process.env.CHROME_PATH || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].find((p) => existsSync(p));
if (!CHROME) throw new Error('Chrome not found; set CHROME_PATH');
const PORT = 9300 + Math.floor(Math.random() * 600);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'dqa-'))}`,
  '--hide-scrollbars', '--autoplay-policy=no-user-gesture-required', '--no-first-run', 'about:blank',
], { stdio: 'ignore' });

let targets;
for (let i = 0; i < 75 && !targets; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); } catch { await sleep(200); }
}
const ws = new WebSocket(targets.find((t) => t.type === 'page').webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r));
let id = 0; const pending = new Map(); const listeners = [];
ws.addEventListener('message', (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } else listeners.forEach((l) => l(m));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || JSON.stringify(r.result.exceptionDetails));
  return r.result.result.value;
};
const loadEvent = () => new Promise((r) => { const l = (m) => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(l), 1); r(); } }; listeners.push(l); });
await send('Page.enable');

const VIEWPORTS = { desktop: { width: 1440, height: 900, dpr: 1, mobile: false }, mobile: { width: 390, height: 844, dpr: 2, mobile: true } };

const HELPERS = `
window.__label=(text,x,y)=>{const t=document.createElement('div');t.textContent=text;Object.assign(t.style,{position:'absolute',left:x+'px',top:y+'px',background:'#FF1F1F',color:'#fff',font:'600 14px/1 Arial,sans-serif',padding:'7px 10px',borderRadius:'4px',zIndex:2147483647,whiteSpace:'nowrap'});document.body.appendChild(t);};
window.__mark=(el,label,pos)=>{const r=el.getBoundingClientRect();const b=document.createElement('div');
 Object.assign(b.style,{position:'absolute',left:(r.left+scrollX-4)+'px',top:(r.top+scrollY-4)+'px',width:(r.width+8)+'px',height:(r.height+8)+'px',border:'3px solid #FF1F1F',borderRadius:'6px',zIndex:2147483646,pointerEvents:'none',boxSizing:'border-box'});
 document.body.appendChild(b); if(label) __label(label, r.left+scrollX-4, pos==='below'?(r.bottom+scrollY+8):(r.top+scrollY-34)); return r;};
window.__box=(x,y,w,h,label)=>{const b=document.createElement('div');Object.assign(b.style,{position:'absolute',left:x+'px',top:y+'px',width:w+'px',height:h+'px',border:'3px dashed #FF1F1F',borderRadius:'8px',zIndex:2147483646,boxSizing:'border-box'});document.body.appendChild(b);if(label)__label(label,Math.max(4,x+w-260),y+h+8);};
window.__guide=(x,label)=>{const g=document.createElement('div');Object.assign(g.style,{position:'absolute',left:x+'px',top:'0',width:'0',height:document.body.scrollHeight+'px',borderLeft:'2px dashed #00E5FF',zIndex:2147483646});document.body.appendChild(g);};
window.__abs=(el,pad=24)=>{const r=el.getBoundingClientRect();return {x:Math.max(0,r.left+scrollX-pad),y:Math.max(0,r.top+scrollY-pad-40),w:Math.min(innerWidth,r.width+pad*2),h:r.height+pad*2+40};};
window.__hideHeader=()=>{document.querySelectorAll('header').forEach(h=>{const p=getComputedStyle(h).position;if(p==='fixed'||p==='sticky')h.style.visibility='hidden';});};
`;

for (const shot of spec.shots) {
  const vp = typeof shot.viewport === 'object' ? shot.viewport : VIEWPORTS[shot.viewport || 'desktop'];
  await send('Emulation.setDeviceMetricsOverride', { width: vp.width, height: vp.height, deviceScaleFactor: vp.dpr ?? 1, mobile: !!vp.mobile });
  const loaded = loadEvent();
  await send('Page.navigate', { url: shot.url || spec.url });
  await loaded;
  await sleep(2500);
  // Scroll the whole page so lazy-loaded images and scroll animations settle.
  await evaluate(`(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0);await new Promise(r=>setTimeout(r,800));})()`);
  await evaluate(HELPERS);
  for (const sel of spec.hideSelectors || []) await evaluate(`document.querySelectorAll(${JSON.stringify(sel)}).forEach(e=>e.style.display='none')`);
  try {
    const clip = await evaluate(shot.script);
    await sleep(400);
    const img = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: clip.x, y: clip.y, width: clip.w, height: clip.h, scale: 1 } });
    const out = join(spec.outDir, `staging_${shot.key}.png`);
    writeFileSync(out, Buffer.from(img.result.data, 'base64'));
    console.log(`ok   ${shot.key} -> ${out}`);
  } catch (e) {
    console.log(`FAIL ${shot.key}: ${e.message.split('\n')[0]}`);
  }
}
ws.close(); chrome.kill();
