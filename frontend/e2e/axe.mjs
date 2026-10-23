import { chromium } from "playwright-core";
const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765/frontend/e2e/harness/index.html";
const launch = (type) => type.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
import { readFileSync } from "node:fs";
const AXE = readFileSync(new URL("../node_modules/axe-core/axe.min.js", import.meta.url), "utf8");
const browser = await launch(chromium);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const found = new Map();
for (const dark of [0, 1]) for (const [scenario, tabs] of [["many", 5], ["white", 5], ["ap", 3]]) {
  const ctx = await browser.newContext({ viewport: { width: 412, height: 915 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}?s=${scenario}&lang=en&dark=${dark}`);
  await page.waitForSelector("woow-glinet-panel"); await sleep(700);
  await page.addScriptTag({ content: AXE });
  for (let i = 0; i < tabs; i++) {
    await page.locator("button.tab").nth(i).click(); await sleep(500);
    const label = (await page.locator("button.tab").nth(i).innerText()).trim().split("\n")[0];
    const res = await page.evaluate(async () => {
      const r = await axe.run(document.querySelector("woow-glinet-panel"), { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"] } });
      return r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, n: v.nodes.length, sample: v.nodes[0].target.flat().join(" ").slice(-90), html: v.nodes[0].html.slice(0, 100) }));
    });
    for (const v of res) {
      const key = v.id + "|" + v.impact;
      const cur = found.get(key) || { help: v.help, where: new Set(), n: 0, sample: v.sample, html: v.html };
      cur.where.add(`${scenario}/${label}/${dark ? "dark" : "light"}`); cur.n += v.n; found.set(key, cur);
    }
  }
  await ctx.close();
}
await browser.close();
if (!found.size) console.log("axe: no violations");
process.exitCode = found.size ? 1 : 0; // the harness carries Home Assistant's default theme, so colour contrast counts too
for (const [key, v] of [...found].sort()) console.log(`${key.padEnd(34)} ${String(v.n).padStart(4)} nodes  ${v.help}\n     e.g. ${v.html}\n     in ${[...v.where].slice(0, 4).join(", ")}`);
