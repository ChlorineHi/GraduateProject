import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";

const require = createRequire("/workspace/apps/web/package.json");
const { chromium } = require("playwright");

const outDir = new URL("../docs/screenshots/phase2/", import.meta.url);
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: "/usr/local/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

async function shot(page, name) {
  const file = new URL(name, outDir);
  await page.screenshot({ path: file.pathname, fullPage: true });
  return file.pathname;
}

const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const notes = [];
await page.goto("http://127.0.0.1:5173/", { waitUntil: "networkidle" });
notes.push(await shot(page, "round1-login.png"));
await page.getByRole("button", { name: "管理员 · admin" }).click();
await page.waitForURL("**/app");
await page.getByRole("link", { name: "数据" }).click();
await page.waitForSelector("text=数据平台");
await page.waitForSelector("text=yjmob100k-dataset1.csv.gz");
notes.push(await shot(page, "round1-data.png"));
await page.getByRole("link", { name: "仿真" }).click();
await page.waitForSelector("text=数据模式");
notes.push(await shot(page, "round1-sim-synthetic.png"));
await page.locator("select").first().selectOption("real_mobility");
await page.getByRole("button", { name: "按参数重置" }).click();
await page.waitForSelector("text=来源 real_mobility", { timeout: 30000 });
const simText = await page.locator(".main").innerText();
if (!simText.includes("YJMob100K") || !simText.includes("用户 10")) {
  throw new Error("sim did not switch mobility source: " + simText.slice(0, 800));
}
notes.push(await shot(page, "round1-sim-yjmob.png"));
await page.getByRole("link", { name: "噪声地图" }).click();
await page.waitForSelector("text=匿名虚拟");
await page.waitForFunction(() => {
  const canvas = document.querySelector("canvas");
  const text = document.body.innerText;
  return Boolean(canvas && canvas.width > 100 && text.includes("用户 10") && text.includes("yjmob_virtual_500m"));
});
notes.push(await shot(page, "round1-map-yjmob.png"));
await page.getByRole("link", { name: "实验" }).click();
await page.waitForSelector("text=公平协议");
notes.push(await shot(page, "round1-experiments.png"));

await page.getByRole("button", { name: "退出" }).click();
await page.waitForSelector("text=进入测站");
await page.getByRole("button", { name: "采集参与者 · collector" }).click();
await page.waitForURL("**/app/mine");
await page.getByRole("link", { name: "噪声地图" }).click();
await page.waitForSelector("text=匿名虚拟");
await page.waitForFunction(() => {
  const canvas = document.querySelector("canvas");
  return Boolean(canvas && canvas.width > 100 && document.body.innerText.includes("用户 10"));
});
const collectorMap = await page.locator(".main").innerText();
if (collectorMap.includes("评估真值")) throw new Error("collector map exposes the truth toggle");
notes.push(await shot(page, "round2-collector-map.png"));
await page.getByRole("button", { name: "退出" }).click();
await page.getByRole("button", { name: "管理员 · admin" }).click();
await page.waitForURL("**/app");
await page.setViewportSize({ width: 390, height: 844 });
await page.getByRole("link", { name: "数据" }).click();
await page.waitForSelector("text=yjmob100k-dataset1.csv.gz");
await page.evaluate(() => window.scrollTo(0, 0));
const mobile = new URL("round2-data-mobile.png", outDir);
await page.screenshot({ path: mobile.pathname, fullPage: false });
const mobileBox = await page.evaluate(() => ({ scrollX: window.scrollX, scrollWidth: document.documentElement.scrollWidth, inner: window.innerWidth }));
if (mobileBox.scrollWidth > mobileBox.inner + 8) {
  throw new Error("mobile page still wider than the viewport: " + JSON.stringify(mobileBox));
}
notes.push(mobile.pathname);
await page.setViewportSize({ width: 1440, height: 900 });
await page.getByRole("link", { name: "仿真" }).click();
await page.locator("select").first().selectOption("synthetic");
await page.getByRole("button", { name: "按参数重置" }).click();
await page.waitForSelector("text=来源 synthetic");
const back = await page.locator(".main").innerText();
if (!back.includes("来源 synthetic")) throw new Error("did not return to synthetic");
notes.push(await shot(page, "round2-sim-synthetic.png"));
await page.getByRole("link", { name: "实验" }).click();
await page.waitForSelector("text=experiments/results/phase2");
notes.push(await shot(page, "round2-experiments.png"));
await browser.close();
console.log(notes.join("\n"));
