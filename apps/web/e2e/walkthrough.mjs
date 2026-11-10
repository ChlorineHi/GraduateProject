import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const base = process.env.UNLAB_WEB || "http://127.0.0.1:5173";
const out = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../docs/screenshots");
await mkdir(out, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: true });
const notes = [];

async function shot(page, name) {
  await page.screenshot({ path: path.join(out, name), fullPage: true });
  notes.push(name);
}

async function login(page, username, password) {
  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "进入测站" }).waitFor();
  await page.locator("input").nth(0).fill(username);
  await page.locator("input").nth(1).fill(password);
  await page.getByRole("button", { name: "进入测站" }).click();
  await page.waitForURL(/\/app/);
}

const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "zh-CN" });
const page = await desktop.newPage();
page.on("pageerror", (error) => notes.push(`pageerror: ${error.message}`));

await page.goto(base, { waitUntil: "networkidle" });
await page.locator("input").nth(0).fill("admin");
await page.locator("input").nth(1).fill("wrong-password");
await page.getByRole("button", { name: "进入测站" }).click();
await page.getByText("用户名或密码错误").waitFor({ timeout: 8000 }).catch(async () => {
  notes.push(`login-error-text-missing: ${await page.locator(".error").innerText().catch(() => "none")}`);
});
await shot(page, "01-login-error.png");

await login(page, "admin", "DemoAdmin#2026");
await page.getByRole("heading", { name: "总览" }).waitFor();
await page.getByText(/D\d/).first().waitFor();
await page.locator("canvas").first().waitFor();
await page.waitForTimeout(600);
await shot(page, "02-dashboard.png");

await page.getByRole("link", { name: "噪声地图" }).click();
await page.locator("canvas").waitFor();
await page.waitForTimeout(400);
const canvas = page.locator("canvas");
const box = await canvas.boundingBox();
if (box) await page.mouse.click(box.x + box.width * 0.45, box.y + box.height * 0.45);
await page.getByText("网格详情").waitFor();
await shot(page, "03-map.png");
await page.getByLabel("不确定性").click();
await page.waitForTimeout(200);
await shot(page, "04-map-uncertainty.png");

await page.getByRole("link", { name: "任务发布" }).click();
await page.getByRole("heading", { name: "任务发布" }).waitFor();
const title = `交叉口抽查 ${Date.now().toString().slice(-6)}`;
await page.locator("label").filter({ hasText: "标题" }).locator("input").fill(title);
await page.getByRole("button", { name: "创建草稿" }).click();
const row = page.locator("tr", { hasText: title });
await row.getByRole("button", { name: "发布" }).waitFor();
await row.getByRole("button", { name: "发布" }).click();
await row.getByText("published").waitFor();
await shot(page, "05-tasks.png");

await page.getByRole("link", { name: "智能分配" }).click();
await page.getByRole("button", { name: "执行分配" }).click();
await page.waitForTimeout(1200);
await shot(page, "06-assign.png");

await page.getByRole("link", { name: "轨迹" }).click();
await page.getByRole("button", { name: "预测下一位置" }).click();
await page.waitForTimeout(800);
await shot(page, "07-tracks.png");

await page.getByRole("link", { name: "预测" }).click();
await page.getByRole("button", { name: "更新预测" }).click();
await page.waitForTimeout(800);
await shot(page, "08-predict.png");

await page.getByRole("link", { name: "仿真" }).click();
const stepped = page.waitForResponse((res) => res.url().includes("/api/simulation/control") && res.request().method() === "POST");
await page.getByRole("button", { name: "单步" }).click();
await stepped;
await shot(page, "09-simulation.png");

await page.getByRole("link", { name: "实验" }).click();
await page.getByRole("heading", { name: "算法实验" }).waitFor();
await page.waitForTimeout(600);
await shot(page, "10-experiments.png");

await page.getByRole("link", { name: "数据" }).click();
await page.getByText("Synthetic Demo").first().waitFor();
await shot(page, "11-data.png");

await page.getByRole("link", { name: "管理" }).click();
await page.getByRole("heading", { name: "系统管理" }).waitFor();
await shot(page, "12-admin.png");

await page.getByRole("button", { name: "深色" }).click();
await page.getByRole("link", { name: "总览" }).click();
await page.waitForTimeout(300);
await shot(page, "13-dashboard-dark.png");
await page.getByRole("button", { name: "浅色" }).click();
await page.getByRole("button", { name: "退出" }).click();
await page.getByRole("heading", { name: "人机混合" }).waitFor();
await shot(page, "14-login.png");

await page.getByRole("button", { name: "采集参与者 · collector" }).click();
await page.getByRole("heading", { name: "我的任务" }).waitFor();
const mine = page.locator("article.panel", { hasText: "待接收任务" });
if (await mine.count()) {
  const accept = mine.getByRole("button", { name: "接收" });
  if (await accept.count()) await accept.click();
  const start = mine.getByRole("button", { name: "开始" });
  if (await start.count()) {
    await start.click();
    await mine.getByRole("button", { name: "仿真采样" }).click();
    await page.waitForTimeout(400);
  }
  if (await page.locator(".error").count()) {
    notes.push(`simulate-sample: ${await page.locator(".error").innerText()}`);
    const manual = mine.locator("input[type=number]");
    if (await manual.count()) {
      await manual.fill("58.5");
      await mine.getByRole("button", { name: "提交测量" }).click();
      await page.waitForTimeout(600);
    }
  }
}
await shot(page, "15-collector.png");
await page.getByRole("button", { name: "退出" }).click();

await login(page, "publisher", "DemoPublish#2026");
await page.getByRole("link", { name: "任务发布" }).click();
const submitted = page.locator("tr", { hasText: "submitted" }).first();
if (await submitted.count()) {
  await submitted.getByRole("button", { name: "核验" }).click();
  await page.waitForTimeout(400);
  const verified = page.locator("tr", { hasText: "verified" }).first();
  if (await verified.count()) await verified.getByRole("button", { name: "完成" }).click();
}
await shot(page, "16-publisher-tasks.png");
await desktop.close();

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "zh-CN", isMobile: true });
const phone = await mobile.newPage();
await login(phone, "admin", "DemoAdmin#2026");
await phone.getByText(/D\d/).first().waitFor();
await phone.locator("canvas").first().waitFor();
await phone.waitForTimeout(400);
await shot(phone, "17-mobile-dashboard.png");
await phone.getByRole("link", { name: "噪声地图" }).click();
await phone.locator("canvas").waitFor();
await phone.waitForTimeout(400);
await shot(phone, "18-mobile-map.png");
await phone.getByRole("link", { name: "任务发布" }).click();
await shot(phone, "19-mobile-tasks.png");
await mobile.close();
await browser.close();

console.log(JSON.stringify({ screenshots: notes }, null, 2));
