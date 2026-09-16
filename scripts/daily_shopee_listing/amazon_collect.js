const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const asins = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ executablePath:'/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args:['--no-sandbox'], proxy:{server:'http://127.0.0.1:38125'} });
  const ctx = await b.newContext({ locale:'ja-JP', timezoneId:'Asia/Tokyo',
    userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    viewport:{width:390,height:844}, isMobile:true, hasTouch:true });
  const out = [];
  for (const asin of asins) {
    const page = await ctx.newPage();
    const rec = { asin };
    try {
      const resp = await page.goto(`https://www.amazon.co.jp/gp/aw/d/${asin}?language=ja_JP`, {waitUntil:'domcontentloaded', timeout:60000});
      rec.status = resp ? resp.status() : null;
      rec.finalUrl = page.url();
      await page.waitForTimeout(2500);
      await page.evaluate(()=>window.scrollBy(0,3000));
      await page.waitForTimeout(1500);
      Object.assign(rec, await page.evaluate(() => {
        const txt = document.body.innerText;
        const title = document.querySelector('h1')?.innerText?.trim() || null;
        // gallery: main image (UF894,1000) + thumbnails (UF350,350)
        const srcs = Array.from(document.querySelectorAll('img')).map(i=>i.src).filter(s=>/m\.media-amazon\.com\/images\/I\//.test(s));
        const toFull = (s) => { const m = s.match(/(https:\/\/m\.media-amazon\.com\/images\/I\/[A-Za-z0-9%+-]+)\./); return m ? m[1] + '._SL1500_.jpg' : null; };
        const main = srcs.filter(s=>/_UF894,1000_|_AC_SX|_AC_UL1500/.test(s)).map(toFull);
        const thumbs = srcs.filter(s=>/_UF350,350_/.test(s)).map(toFull);
        const images = [...new Set([...main, ...thumbs])].filter(Boolean).slice(0,7);
        // variation signals per skill rules
        const varLabels = [...txt.matchAll(/^(色|カラー|サイズ|スタイル|パターン|種類|タイプ)\s*[:：]\s*(.+)$/gm)].map(m=>m[0]);
        const optionLines = [...txt.matchAll(/^(.+?)\n?￥[\d,]+から\d+個のオプション$/gm)].map(m=>m[0]);
        const priceMentions = [...txt.matchAll(/￥[\d,]+/g)].map(m=>m[0]);
        return { title, images, varLabels, optionLines, priceMentions: [...new Set(priceMentions)].slice(0,8),
                 rating: (txt.match(/5つ星のうち([\d.]+)/)||[])[1] || null,
                 reviews: (txt.match(/\((\d[\d,]*)\)/)||[])[1] || null,
                 notFound: /お探しの商品|ページが見つかりません|現在このページは利用できません/.test(txt),
                 crossBorder: /にお届け/.test(txt) && !/日本にお届け/.test(txt) };
      }));
    } catch (e) { rec.error = String(e).slice(0,200); }
    await page.close();
    out.push(rec);
    console.error(`${asin}: ${(rec.title||rec.error||'?').slice(0,45)} | imgs=${(rec.images||[]).length} | var=${JSON.stringify(rec.varLabels||[])}`);
  }
  await b.close();
  fs.writeFileSync(process.env.OUT || 'collect.json', JSON.stringify(out, null, 2));
})();
