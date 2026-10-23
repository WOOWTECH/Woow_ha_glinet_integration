import { chromium, firefox, webkit } from "playwright-core";
const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765/frontend/e2e/harness/index.html";
// CHROME_PATH is an installed Chrome: only the Chromium engine may use it (Firefox and WebKit have their own builds)
const launch = (type) => type.launch({ headless: true, ...(type === chromium && process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const engines = [["chrome", () => launch(chromium)], ["firefox", () => launch(firefox)], ["webkit", () => launch(webkit)]];
let failed = 0;
for (const [name, launch] of engines) {
  const check = (n, c, x = "") => { if (!c) failed++; console.log(`${c ? "PASS" : "FAIL"} [${name}] ${n}${x ? "  " + x : ""}`); };
  let browser;
  try { browser = await launch(); } catch (e) { console.log(`SKIP ${name}: ${String(e).slice(0, 100)}`); continue; }
  for (const [label, w, h, dark] of [["phone", 412, 915, true], ["desktop", 1280, 900, false]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: dark ? "dark" : "light" });
    const page = await ctx.newPage();
    const problems = [];
    page.on("pageerror", (e) => problems.push(String(e.message).slice(0, 80)));
    page.on("console", (m) => m.type() === "error" && !/favicon|404/.test(m.text()) && problems.push(m.text().slice(0, 80)));
    await page.goto(`${BASE}?s=many&lang=zh-Hant&dark=${dark ? 1 : 0}&live=1`);
    await page.waitForSelector("woow-glinet-panel"); await sleep(900);
    const tabs = (await page.locator("button.tab").allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim());
    check(`${label}: five tabs render`, tabs.length === 5, tabs.join("|"));
    for (let i = 0; i < 5; i++) { await page.locator("button.tab").nth(i).click(); await sleep(450); if (label === "phone") await page.screenshot({ path: `${process.env.E2E_OUT || "/tmp"}/xb-${name}-${i}.png` }); }
    await page.locator("button.tab").nth(1).click(); await sleep(500);
    check(`${label}: 24 device cards`, (await page.locator("woow-glinet-clients .client").count()) === 24);
    await page.locator("woow-glinet-clients input[type=search]").fill("hue"); await sleep(300);
    check(`${label}: search filters`, (await page.locator("woow-glinet-clients .client").count()) === 1);
    await page.locator("woow-glinet-clients input[type=search]").fill("");
    await page.locator("woow-glinet-clients .client button.link").first().click(); await sleep(1100);
    check(`${label}: details chart draws`, (await page.locator("woow-glinet-clients woow-glinet-chart path.line").count()) === 2);
    await page.locator("woow-glinet-clients .client .actions button").nth(1).click(); await sleep(300);
    const focused = await page.evaluate(() => { let a = document.activeElement; while (a && a.shadowRoot && a.shadowRoot.activeElement) a = a.shadowRoot.activeElement; return a && a.tagName; });
    check(`${label}: dialog opens with the input focused`, focused === "INPUT", String(focused));
    await page.keyboard.press("Escape"); await sleep(300);
    check(`${label}: Esc closes the dialog`, (await page.locator(".dialog").count()) === 0);
    await page.locator("button.tab").nth(2).click(); await sleep(400);
    await page.locator("woow-glinet-wifi button.switch").nth(1).click(); await sleep(600);
    const calls = await page.evaluate(() => window.__calls.map((c) => c.type));
    check(`${label}: Wi-Fi switch sends the command`, calls.includes("woow_glinet/wifi/set"));
    await page.locator("button.tab").nth(0).click(); await sleep(3500);
    check(`${label}: live chart keeps drawing`, (await page.locator("woow-glinet-overview woow-glinet-chart path.line").count()) === 2);
    const mixed = await page.evaluate(() => { const el = document.querySelector("woow-glinet-panel").shadowRoot.querySelector("woow-glinet-overview").shadowRoot.querySelector(".chip.ok"); return el ? getComputedStyle(el).color : null; });
    console.log(`   · [${name}/${label}] .chip.ok colour: ${mixed}`);
    check(`${label}: no console errors`, problems.length === 0, problems.slice(0, 2).join(" | "));
    await ctx.close();
  }
  await browser.close();
}
console.log(failed ? `\n${failed} FAILED` : "\nALL PASSED");
