// 用无头 Chrome 逐帧渲染 replica.html，直接编码成 MP4
// 用法：node render.js <起始帧> <结束帧(不含)> <输出.mp4>
//       node render.js still <秒> <输出.png>     （单帧预览）
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const FPS = 30;
const page_url = 'file://' + path.resolve(__dirname, 'replica.html') + '?render';

(async () => {
  const [mode, a, b] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, args: ['--disable-gpu-vsync'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto(page_url);
  await page.evaluate(() => document.fonts.ready);
  const grab = (t, q) => page.evaluate(([t, q]) => { window.render(t); return document.getElementById('c').toDataURL(q ? 'image/jpeg' : 'image/png', q || undefined); }, [t, q]);

  if (mode === 'still') {
    for (const t of a.split(',')) {
      const url = await grab(+t, 0);
      fs.writeFileSync(b.replace('%t', t), Buffer.from(url.split(',')[1], 'base64'));
    }
    await browser.close(); return;
  }
  const f0 = +mode, f1 = +a, out = b, tmp = out.replace(/\.mp4$/, '.part.mp4');
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', String(FPS), tmp], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = f0; f < f1; f++) {
    const url = await grab(f / FPS, 0.93);
    const ok = ff.stdin.write(Buffer.from(url.split(',')[1], 'base64'));
    if (!ok) await new Promise(r => ff.stdin.once('drain', r));
    if ((f - f0) % 150 === 0) console.log(`${out}: frame ${f}/${f1}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on('close', c => c === 0 ? res() : rej(new Error('ffmpeg ' + c))));
  fs.renameSync(tmp, out);
  await browser.close();
})();
