// Laptop + phone test of the web demo · Owner: Nancy · built with AI assistance (Claude), reviewed by the team
//
//   cd web && python -m http.server 8000          (in one terminal)
//   node web/tests/ui_check.mjs http://localhost:8000 docs/testing/screenshots
//
// Needs Playwright: npm i -D playwright && npx playwright install chromium
// For each device it opens the cohort, a patient, the "Explain in plain words" panel and a body system,
// and records: console errors, horizontal scrolling, tap targets smaller than 44 px (phone), load times.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const BASE = (process.argv[2] || "http://localhost:8000").replace(/\/$/, "");
// Nancy's Sprint 4 page; the original web/index.html is left unchanged
const PAGE = process.env.PAGE || "/demo-v0.5.html";
const OUT = process.argv[3] || "docs/testing/screenshots";
mkdirSync(OUT, { recursive: true });

const DEVICES = {
  laptop: { viewport: { width: 1366, height: 768 }, deviceScaleFactor: 1 },
  phone: { ...devices["iPhone 13"], defaultBrowserType: undefined },
};
const PATIENT = "PC0989";
// Optional: THREE_DIR=/path/to/node_modules/three serves Three.js locally when the CDN is blocked (e.g. a locked-down network)
const THREE_DIR = process.env.THREE_DIR; // featured: metabolic · worsening

async function overflow(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const wide = [...document.querySelectorAll("body *")].filter((el) => { const r = el.getBoundingClientRect(); return r.width && r.right > vw + 1 && getComputedStyle(el).position !== "fixed"; })
      .filter((el) => !el.closest(".tbl,.plist,pre")) // these scroll on purpose
      .slice(0, 5).map((el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""}${el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : ""} (${Math.round(el.getBoundingClientRect().right)}px)`);
    return { page: document.documentElement.scrollWidth > vw + 1, scrollWidth: document.documentElement.scrollWidth, vw, wide };
  });
}
async function smallTargets(page, min = 44) {
  return page.evaluate((min) => {
    const seen = {};
    [...document.querySelectorAll("button,input,select,a,summary")].forEach((el) => {
      const r = el.getBoundingClientRect(); if (!r.width || !r.height || getComputedStyle(el).visibility === "hidden") return;
      if (r.height < min || r.width < min) { const k = (el.id ? "#" + el.id : el.className ? "." + String(el.className).split(" ")[0] : el.tagName.toLowerCase()); (seen[k] = seen[k] || { n: 0, h: Math.round(r.height), w: Math.round(r.width) }).n++; }
    });
    return seen;
  }, min);
}

const results = {};
const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"] });
for (const [name, dev] of Object.entries(DEVICES)) {
  const ctx = await browser.newContext(dev);
  if (THREE_DIR) {
    await ctx.route("**/three.min.js", (r) => r.fulfill({ path: `${THREE_DIR}/build/three.min.js`, contentType: "text/javascript" }));
    await ctx.route("**/OrbitControls.js", (r) => r.fulfill({ path: `${THREE_DIR}/examples/js/controls/OrbitControls.js`, contentType: "text/javascript" }));
  }
  const page = await ctx.newPage();
  const errors = [], failed = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("requestfailed", (r) => failed.push(r.url()));
  const R = (results[name] = { steps: [] });
  const step = async (label, fn) => { const t0 = Date.now(); try { const extra = await fn(); R.steps.push({ label, ok: true, ms: Date.now() - t0, ...(extra || {}) }); } catch (e) { R.steps.push({ label, ok: false, ms: Date.now() - t0, error: String(e).split("\n")[0] }); } };

  await step("cohort loads", async () => {
    await page.goto(BASE + PAGE, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#plist .pbtn", { timeout: 20000 });
    await page.screenshot({ path: `${OUT}/${name}-1-cohort.png`, fullPage: true });
    return { overflow: await overflow(page), small: name === "phone" ? await smallTargets(page) : undefined };
  });
  await step("open patient", async () => {
    await page.click(`[data-open="${PATIENT}"]`);
    await page.waitForSelector("#panel h2", { timeout: 20000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/${name}-2-patient.png`, fullPage: true });
    const glH = await page.evaluate(() => document.getElementById("gl").getBoundingClientRect().height);
    const panelTop = await page.evaluate(() => document.getElementById("panel").getBoundingClientRect().top);
    return { overflow: await overflow(page), small: name === "phone" ? await smallTargets(page) : undefined, glHeight: Math.round(glH), panelTop: Math.round(panelTop), webgl: await page.evaluate(() => !!document.querySelector("#gl canvas")) };
  });
  await step("explain in plain words", async () => {
    await page.click("#explain");
    await page.waitForSelector("#exbody, .blocked", { timeout: 15000 });
    const card = page.locator("#excard");
    await card.screenshot({ path: `${OUT}/${name}-3-explain.png` });
    return { passed: await page.locator("#exbody").count() > 0, checks: await page.locator(".chk li").allInnerTexts(), overflow: await overflow(page) };
  });
  await step("body system view", async () => {
    await page.click('.sysrow[data-sys="metabolic"]');
    await page.waitForSelector("#back");
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/${name}-4-system.png`, fullPage: true });
    return { overflow: await overflow(page), small: name === "phone" ? await smallTargets(page) : undefined };
  });
  await step("next / previous patient", async () => {
    await page.click("#back"); await page.click("#pnext"); await page.waitForFunction(() => document.querySelector("#pq")?.value === "PC0990", null, { timeout: 15000 });
    await page.click("#pprev"); await page.waitForFunction(() => document.querySelector("#pq")?.value === "PC0989", null, { timeout: 15000 });
  });
  await step("unknown patient ID gives feedback", async () => {
    await page.fill("#pq", "PC9999"); await page.click("#pgo"); await page.waitForTimeout(300);
    const msg = await page.evaluate(() => { const i = document.getElementById("pq"); return { valid: i.checkValidity(), text: document.getElementById("pqmsg")?.textContent || "" }; });
    if (msg.valid && !msg.text) throw new Error("no message shown for an unknown ID");
    return msg;
  });
  await step("blocked state (?demo=unsafe)", async () => {
    await page.goto(BASE + PAGE + "?demo=unsafe"); await page.waitForSelector("#plist .pbtn");
    await page.click(`[data-open="${PATIENT}"]`); await page.waitForSelector("#explain"); await page.click("#explain");
    await page.waitForSelector(".blocked", { timeout: 15000 });
    await page.locator("#excard").screenshot({ path: `${OUT}/${name}-5-blocked.png` });
    return { failedChecks: await page.locator(".chk li.fail").allInnerTexts() };
  });
  R.consoleErrors = [...new Set(errors)];
  R.failedRequests = [...new Set(failed)];
  await ctx.close();
}
await browser.close();
writeFileSync(`${OUT}/../ui_check_results.json`, JSON.stringify(results, null, 1));
for (const [d, r] of Object.entries(results)) {
  console.log(`\n== ${d} ==`);
  r.steps.forEach((s) => console.log(`${s.ok ? "PASS" : "FAIL"} ${s.label} (${s.ms} ms)${s.error ? " · " + s.error : ""}${s.overflow?.page ? " · HORIZONTAL SCROLL " + s.overflow.scrollWidth + "px" : ""}`));
  console.log("console errors:", r.consoleErrors.length, r.consoleErrors.slice(0, 3));
}
