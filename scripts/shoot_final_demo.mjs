import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";

const require = createRequire("/workspace/apps/web/package.json");
const { chromium } = require("playwright");

const outDir = new URL("../docs/screenshots/final/", import.meta.url);
await mkdir(outDir, { recursive: true });
const notes = [];

function log(line) {
  notes.push(line);
  console.log(line);
}

const browser = await chromium.launch({
  executablePath: "/usr/local/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name) {
  const file = new URL(name, outDir);
  await page.screenshot({ path: file.pathname, fullPage: false });
  log(`shot ${name}`);
}

await page.goto("http://127.0.0.1:5194/", { waitUntil: "networkidle" });
await shot("01-login.png");
await page.getByRole("button", { name: "管理员 · admin" }).click();
await page.waitForURL("**/app");
await page.waitForSelector("text=总览");
await shot("02-dashboard.png");

await page.getByRole("link", { name: "数据" }).click();
await page.waitForSelector("text=数据平台");
await shot("03-data.png");

await page.getByRole("link", { name: "仿真" }).click();
await page.waitForSelector("text=数据模式");
await page.locator("select").nth(0).selectOption("fully_real");
const refusedResponse = page.waitForResponse((response) => response.url().includes("/api/simulation/control") && response.request().method() === "POST");
await page.getByRole("button", { name: "按参数重置" }).click();
const refusedStatus = (await refusedResponse).status();
if (refusedStatus !== 409) throw new Error("fully_real returned " + refusedStatus);
await page.waitForSelector("text=数据未切换", { timeout: 20000 });
const refused = await page.locator(".error").innerText();
if (!refused.includes("数据未切换") || !refused.includes("不会被悄悄换成合成轨迹")) {
  throw new Error("fully_real refusal was not shown: " + refused.slice(0, 500));
}
await shot("04-fully-real-refused.png");
log("fully_real refused and previous world kept");

await page.locator("select").nth(0).selectOption("real_mobility");
await page.locator("select").nth(1).selectOption("yjmob_dataset1");
const algo = page.locator("select").nth(3);
await algo.selectOption("eer_reach");
const resetResponse = page.waitForResponse((response) => response.url().includes("/api/simulation/control") && response.request().method() === "POST");
await page.getByRole("button", { name: "按参数重置" }).click();
const resetJson = await (await resetResponse).json();
if (resetJson.mode !== "real_mobility" || resetJson.mobility_source !== "YJMob100K" || resetJson.user_count !== 10) {
  throw new Error("YJMob reset payload was " + JSON.stringify({ mode: resetJson.mode, mobility_source: resetJson.mobility_source, user_count: resetJson.user_count }));
}
if (resetJson.current_slot !== resetJson.horizon_start || resetJson.budget_spent !== 0 || resetJson.budget_left !== resetJson.budget_total) {
  throw new Error("reset did not restore the clock and budget: " + JSON.stringify(resetJson));
}
await page.waitForSelector("text=世界已生成", { timeout: 30000 });
const simText = await page.locator(".main").innerText();
if (!simText.includes("用户 10") || simText.includes("夹具")) {
  throw new Error("YJMob reset did not show 10 real users: " + simText.slice(0, 800));
}
if (simText.includes("来源 synthetic")) {
  throw new Error("real mobility fell back to synthetic");
}
await shot("05-sim-yjmob.png");
log("yjmob reset ok");

await page.getByRole("link", { name: "轨迹" }).click();
await page.waitForSelector("text=轨迹分析");
await shot("06-tracks.png");

await page.getByRole("link", { name: "噪声地图" }).click();
await page.waitForSelector("text=噪声地图");
await page.locator("canvas").first().click({ position: { x: 180, y: 160 } });
await shot("07-map.png");

await page.getByRole("link", { name: "任务发布" }).click();
await page.waitForSelector("text=新任务");
await page.getByLabel("标题").fill("答辩采样点");
await page.getByLabel("网格 X").fill("2");
await page.getByLabel("网格 Y").fill("2");
await page.getByLabel("开始片").fill("50");
await page.getByLabel("结束片").fill("54");
await page.getByRole("button", { name: "创建草稿" }).click();
await page.waitForSelector("text=答辩采样点");
await page.getByRole("button", { name: "发布" }).first().click();
await page.waitForSelector("text=published");
await shot("08-task-published.png");
log("task published");

await page.getByRole("link", { name: "智能分配" }).click();
await page.waitForSelector("text=执行分配");
await page.locator("select").first().selectOption("eer_reach");
await page.getByRole("button", { name: "执行分配" }).click();
await page.waitForSelector("text=到达概率");
await page.waitForTimeout(500);
const assignText = await page.locator(".main").innerText();
log("assign text snippet: " + assignText.replace(/\s+/g, " ").slice(0, 400));
await shot("09-assign-eer.png");

await page.getByRole("link", { name: "仿真" }).click();
const stepResponse = page.waitForResponse((response) => response.url().includes("/api/simulation/control") && response.request().method() === "POST");
await page.getByRole("button", { name: "前进 4 步" }).click();
const steppedJson = await (await stepResponse).json();
if (!steppedJson.log.some((line) => line.includes("成功") || line.includes("失败"))) {
  throw new Error("step did not execute a task: " + (steppedJson.log || []).slice(-8).join(" | "));
}
log("step budget_left=" + steppedJson.budget_left + " spent=" + steppedJson.budget_spent + " mae=" + (steppedJson.metrics || {}).mae_current_slot);
await page.waitForFunction(() => (document.querySelector(".clock")?.textContent || "").includes("D1 02:00"), null, { timeout: 8000 });
await shot("10-sim-stepped.png");
const stepped = await page.locator(".main").innerText();
log("after step: " + stepped.replace(/\s+/g, " ").slice(0, 500));

await page.getByRole("link", { name: "噪声地图" }).click();
await page.waitForSelector("text=匿名虚拟 500 m");
await shot("11-map-after-step.png");

await page.getByRole("link", { name: "实验" }).click();
await page.waitForSelector("h1, h2, .page-title", { timeout: 10000 }).catch(() => {});
await page.getByRole("heading", { name: "算法实验" }).waitFor();
await page.waitForSelector("text=公平协议 MAE");
await page.locator(".main canvas").first().waitFor();
await shot("12-experiments.png");
log("experiments: " + (await page.locator(".main").innerText()).replace(/\s+/g, " ").slice(0, 400));

await browser.close();
await writeFile(new URL("notes.txt", outDir), notes.join("\n"), "utf8");
log("done");
