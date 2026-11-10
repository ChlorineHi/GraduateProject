import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import * as echarts from "echarts";
import { api, download, setToken, type Frame, type User } from "./api";
import { CityMap } from "./CityMap";

type Dash = {
  active_tasks: number;
  online_participants: number;
  human_online: number;
  machine_online: number;
  coverage: number;
  budget_total: number;
  budget_used: number;
  budget_left: number;
  samples_today: number;
  mean_noise_db: number | null;
  success_rate: number | null;
  data_quality: number | null;
  trend: { slot: number; label: string; samples: number; mean_db: number }[];
  events: string[];
  scenario: string | null;
  clock: string | null;
  status: string | null;
};

const NAV = [
  ["01", "总览", "/app"],
  ["02", "噪声地图", "/app/map"],
  ["03", "任务发布", "/app/tasks"],
  ["04", "我的任务", "/app/mine"],
  ["05", "智能分配", "/app/assign"],
  ["06", "轨迹", "/app/tracks"],
  ["07", "预测", "/app/predict"],
  ["08", "仿真", "/app/sim"],
  ["09", "实验", "/app/experiments"],
  ["10", "数据", "/app/data"],
  ["11", "管理", "/app/admin"],
];

function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const refresh = useCallback(async () => {
    const me = await api<User>("/api/auth/me");
    setUser(me);
  }, []);
  useEffect(() => {
    const saved = localStorage.getItem("unlab-token");
    if (!saved) {
      setReady(true);
      return;
    }
    refresh().catch(() => setToken(null)).finally(() => setReady(true));
  }, [refresh]);
  return { user, ready, setUser, refresh };
}

function Chart({ option, height = 240 }: { option: echarts.EChartsOption; height?: number }) {
  const [node, setNode] = useState<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!node) return;
    const chart = echarts.init(node);
    const paint = () => {
      chart.resize();
      chart.setOption(option, true);
    };
    paint();
    const observer = new ResizeObserver(paint);
    observer.observe(node);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [node, option]);
  return <div ref={setNode} style={{ height }} />;
}

function Shell({ user, onLogout }: { user: User; onLogout: () => void }) {
  const location = useLocation();
  const [dash, setDash] = useState<Dash | null>(null);
  const [theme, setTheme] = useState(localStorage.getItem("unlab-theme") || "light");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("unlab-theme", theme);
  }, [theme]);
  useEffect(() => {
    let stop = false;
    const pull = () => api<Dash>("/api/dashboard").then((data) => { if (!stop) setDash(data); }).catch(() => { if (!stop) setDash(null); });
    void pull();
    const timer = window.setInterval(pull, 2000);
    return () => { stop = true; window.clearInterval(timer); };
  }, [location.pathname]);
  return (
    <div className="shell">
      <aside className="rail">
        <div className="mark">
          <b>声</b>
          <span>UrbanNoiseLab<br />虚拟城市测站</span>
        </div>
        <nav className="nav">
          {NAV.map(([index, label, path]) => (
            <NavLink key={path} to={path} end={path === "/app"}>
              <em>{index}</em>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="note">当前身份 {user.display_name}<br />演示账号不能用于生产环境。</div>
      </aside>
      <section className="main">
        <header className="topbar">
          <div className="clock">
            {dash?.clock || "—"} · {dash?.scenario || "未加载"} · {dash?.status || ""}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-ghost" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? "浅色" : "深色"}
            </button>
            <button className="btn-ghost" onClick={onLogout}>退出</button>
          </div>
        </header>
        <Outlet />
      </section>
    </div>
  );
}

function Page({ title, lede, children, extra }: { title: string; lede: string; children: ReactNode; extra?: ReactNode }) {
  return (
    <div className="page">
      <div className="page-title">
        <div>
          <h1>{title}</h1>
          <p>{lede}</p>
        </div>
        {extra}
      </div>
      {children}
    </div>
  );
}

function Dashboard() {
  const [data, setData] = useState<Dash | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Dash>("/api/dashboard").then(setData).catch((reason: Error) => setError(reason.message));
  }, []);
  const option = useMemo<echarts.EChartsOption>(() => ({
    grid: { left: 40, right: 16, top: 24, bottom: 32 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: data?.trend.map((item) => item.label) || [], axisLabel: { color: "#5e6c64", fontSize: 10 } },
    yAxis: { type: "value", name: "dB", axisLabel: { color: "#5e6c64" }, splitLine: { lineStyle: { color: "#eadfcb" } } },
    series: [{ type: "line", smooth: true, showSymbol: true, symbolSize: 7, data: data?.trend.map((item) => Number(item.mean_db.toFixed(2))) || [], areaStyle: { color: "rgba(29,107,93,0.18)" }, lineStyle: { color: "#1d6b5d", width: 2 }, itemStyle: { color: "#a56b32" } }],
  }), [data]);
  if (error) return <Page title="总览" lede="测站当前状态"><p className="error">{error}</p></Page>;
  if (!data) return <Page title="总览" lede="正在读取测站数据。"><p className="note">加载中</p></Page>;
  return (
    <Page title="总览" lede="这是虚拟城市的运行台。覆盖率、预算和采样都来自数据库里的真实记录，不是静态卡片。">
      <section className="instrument">
        <article>
          <span className="kicker">场景</span>
          <b>{data.scenario}</b>
          <span className="note">时钟 {data.clock} · 状态 {data.status}</span>
        </article>
        <article><span className="kicker">活跃任务</span><b>{data.active_tasks}</b></article>
        <article><span className="kicker">在线参与者</span><b>{data.online_participants}</b><span className="note">人 {data.human_online} / 机 {data.machine_online}</span></article>
        <article><span className="kicker">覆盖率</span><b>{(data.coverage * 100).toFixed(1)}%</b></article>
        <article><span className="kicker">预算剩余</span><b>{data.budget_left.toFixed(1)}</b><span className="note">已用 {data.budget_used.toFixed(1)} / {data.budget_total.toFixed(1)}</span></article>
      </section>
      <div className="grid-2">
        <section className="panel">
          <h2>声能平均趋势</h2>
          <Chart option={option} />
          <p className="note">纵轴是各时间片观测的能量平均声级，不是分贝的算术平均。</p>
        </section>
        <section className="panel">
          <h2>运行摘记</h2>
          <div className="grid-3" style={{ marginBottom: 12 }}>
            <div className="stat"><span>观测条数</span><b>{data.samples_today}</b></div>
            <div className="stat"><span>能量平均</span><b>{data.mean_noise_db?.toFixed(1) ?? "—"}</b></div>
            <div className="stat"><span>完成率</span><b>{data.success_rate === null ? "—" : `${(data.success_rate * 100).toFixed(0)}%`}</b></div>
          </div>
          <ul className="tape">
            {data.events.length === 0 && <li>还没有审计事件。</li>}
            {data.events.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
          </ul>
        </section>
      </div>
    </Page>
  );
}

function MapPage({ role }: { role: string }) {
  const [slot, setSlot] = useState(48);
  const [frame, setFrame] = useState<Frame | null>(null);
  const [mode, setMode] = useState<"prediction" | "uncertainty" | "zone" | "truth">("prediction");
  const [showPeople, setShowPeople] = useState(true);
  const [showTasks, setShowTasks] = useState(true);
  const [showObs, setShowObs] = useState(true);
  const [truth, setTruth] = useState(false);
  const [selected, setSelected] = useState<Frame["cells"][number] | null>(null);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const load = useCallback(async (nextSlot: number, withTruth: boolean) => {
    try {
      const data = await api<Frame>(`/api/map/frame?slot=${nextSlot}&include_truth=${withTruth}`);
      setFrame(data);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "地图加载失败");
    }
  }, []);
  useEffect(() => { void load(slot, truth); }, [load, slot, truth]);
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setSlot((value) => (value + 1) % (frame?.height ? 96 : 48)), 700);
    return () => window.clearInterval(timer);
  }, [playing, frame?.height]);
  return (
    <Page title="噪声地图" lede="网格颜色使用固定 32–80 dB 标尺。YJMob 只显示匿名虚拟网格。GeoLife 与 NoiseCapture 才使用 WGS84，而且不会叠成同一次真实实验。">
      {error && <p className="error">{error}</p>}
      <div className="checks">
        {(["prediction", "uncertainty", "zone"] as const).map((item) => (
          <label key={item}><input type="radio" checked={mode === item} onChange={() => setMode(item)} /> {item === "prediction" ? "预测" : item === "uncertainty" ? "不确定性" : "用地"}</label>
        ))}
        <label><input type="checkbox" checked={showPeople} onChange={(event) => setShowPeople(event.target.checked)} /> 参与者</label>
        <label><input type="checkbox" checked={showTasks} onChange={(event) => setShowTasks(event.target.checked)} /> 任务</label>
        <label><input type="checkbox" checked={showObs} onChange={(event) => setShowObs(event.target.checked)} /> 观测</label>
        {(role === "admin" || role === "publisher") && (
          <label><input type="checkbox" checked={truth} onChange={(event) => { setTruth(event.target.checked); if (event.target.checked) setMode("truth"); }} /> 评估真值</label>
        )}
        <button className="btn-ghost" onClick={() => setPlaying((value) => !value)}>{playing ? "暂停" : "播放"}</button>
      </div>
      <div className="map-layout">
        <div className="canvas-wrap">
          <div className="legend"><i /> {frame?.slot_label} · {frame?.label || frame?.data_origin} · {frame?.coordinate_system} · 用户 {frame?.user_count ?? "—"} · {frame?.algorithm || "—"} · 预算 {frame?.budget ?? "—"}</div>
          {frame && <CityMap frame={frame} mode={truth && mode === "truth" ? "truth" : mode === "truth" ? "prediction" : mode} showPeople={showPeople} showTasks={showTasks} showObs={showObs} selected={selected} onSelect={setSelected} />}
          <input type="range" min={0} max={95} value={slot} onChange={(event) => setSlot(Number(event.target.value))} style={{ width: "100%" }} />
          <p className="note">{frame?.warning}</p>
        </div>
        <aside className="panel">
          <h2>网格详情</h2>
          {!selected && <p className="note">点击网格查看预测、不确定性和用地。</p>}
          {selected && (
            <div>
              <p>坐标 {selected.x}, {selected.y}</p>
              <p>用地 {selected.zone}</p>
              <p>预测 {selected.prediction.toFixed(1)} dB</p>
              <p>不确定性 {selected.uncertainty.toFixed(1)} dB</p>
              {selected.truth !== undefined && <p>评估真值 {selected.truth.toFixed(1)} dB</p>}
            </div>
          )}
          <h2>图例</h2>
          <p className="note">圆点：人（墨色）与机器（潮绿）。方块：该时间片观测。红框：任务。</p>
        </aside>
      </div>
    </Page>
  );
}

type Task = {
  id: number;
  title: string;
  grid_x: number;
  grid_y: number;
  zone: string;
  slot_start: number;
  slot_end: number;
  slot_label: string;
  status: string;
  assignee_name: string | null;
  algorithm: string;
  origin: string;
  priority: number;
};

function TasksPage({ role }: { role: string }) {
  const [items, setItems] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ title: "新采样任务", grid_x: 4, grid_y: 4, slot_start: 52, slot_end: 56, priority: 1, budget_cost: 1, algorithm: "mupsa" });
  const load = useCallback(() => api<{ items: Task[] }>("/api/tasks").then((data) => setItems(data.items)).catch((reason: Error) => setError(reason.message)), []);
  useEffect(() => { void load(); }, [load]);
  async function createTask() {
    setError("");
    try {
      await api("/api/tasks", { method: "POST", body: JSON.stringify(form) });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建失败");
    }
  }
  async function transition(id: number, to_status: string) {
    setError("");
    try {
      await api(`/api/tasks/${id}/transition`, { method: "POST", body: JSON.stringify({ to_status }) });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "状态更新失败");
    }
  }
  return (
    <Page title="任务发布" lede="创建、发布和取消都会调用后端状态机。草稿不会因为只点一个没有接口的按钮而改变。">
      {error && <p className="error">{error}</p>}
      {(role === "admin" || role === "publisher") && (
        <section className="panel">
          <h2>新任务</h2>
          <div className="form-grid">
            <label className="field">标题<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label>
            <label className="field">网格 X<input type="number" value={form.grid_x} onChange={(event) => setForm({ ...form, grid_x: Number(event.target.value) })} /></label>
            <label className="field">网格 Y<input type="number" value={form.grid_y} onChange={(event) => setForm({ ...form, grid_y: Number(event.target.value) })} /></label>
            <label className="field">开始片<input type="number" value={form.slot_start} onChange={(event) => setForm({ ...form, slot_start: Number(event.target.value) })} /></label>
            <label className="field">结束片<input type="number" value={form.slot_end} onChange={(event) => setForm({ ...form, slot_end: Number(event.target.value) })} /></label>
            <label className="field">优先级<input type="number" step="0.1" value={form.priority} onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })} /></label>
            <label className="field">预算成本<input type="number" step="0.1" value={form.budget_cost} onChange={(event) => setForm({ ...form, budget_cost: Number(event.target.value) })} /></label>
            <label className="field">算法
              <select value={form.algorithm} onChange={(event) => setForm({ ...form, algorithm: event.target.value })}>
                {["eer_reach", "mupsa", "reach_nearest", "greedy", "uncertainty", "nearest", "random", "min_cost"].map((item) => <option key={item}>{item}</option>)}
              </select>
            </label>
          </div>
          <div style={{ marginTop: 12 }}><button className="btn" onClick={() => void createTask()}>创建草稿</button></div>
        </section>
      )}
          <section className="panel">
        <h2>任务队列</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>标题</th><th>位置</th><th>时间</th><th>状态</th><th>执行人</th><th></th></tr></thead>
          <tbody>
            {items.map((task) => (
              <tr key={task.id}>
                <td>{task.title}<div className="note">{task.origin} · {task.algorithm}</div></td>
                <td>{task.grid_x},{task.grid_y}<div className="note">{task.zone}</div></td>
                <td>{task.slot_label}<div className="note">{task.slot_start}–{task.slot_end}</div></td>
                <td><span className="tag">{task.status}</span></td>
                <td>{task.assignee_name || "—"}</td>
                <td>
                  {task.status === "draft" && (role === "admin" || role === "publisher") && <button className="btn" onClick={() => void transition(task.id, "published")}>发布</button>}
                  {["draft", "published", "assigned"].includes(task.status) && (role === "admin" || role === "publisher") && <button className="btn-ghost" onClick={() => void transition(task.id, "cancelled")}>取消</button>}
                  {task.status === "submitted" && (role === "admin" || role === "publisher") && <button className="btn" onClick={() => void transition(task.id, "verified")}>核验</button>}
                  {task.status === "verified" && (role === "admin" || role === "publisher") && <button className="btn" onClick={() => void transition(task.id, "completed")}>完成</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {items.length === 0 && <p className="note">任务队列是空的。</p>}
      </section>
    </Page>
  );
}

function MinePage() {
  const [items, setItems] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [level, setLevel] = useState(55);
  const load = useCallback(() => api<{ items: Task[] }>("/api/tasks?mine=true").then((data) => setItems(data.items)).catch((reason: Error) => setError(reason.message)), []);
  useEffect(() => { void load(); }, [load]);
  async function act(id: number, body: object) {
    setError("");
    try {
      await api(`/api/tasks/${id}/transition`, { method: "POST", body: JSON.stringify(body) });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "操作失败");
    }
  }
  async function simulate(id: number) {
    setError("");
    try {
      await api(`/api/tasks/${id}/simulate-sample`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "仿真采样失败");
    }
  }
  return (
    <Page title="我的任务" lede="采集参与者只能操作分配给自己的任务。手工填写的是测量值；仿真采样只有人在任务网格上时才会读取仿真真值。">
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="note">当前没有分配给你的任务。</p>}
      <div className="grid-2">
        {items.map((task) => (
          <article className="panel" key={task.id}>
            <h2>{task.title}</h2>
            <p>{task.zone} · 网格 {task.grid_x},{task.grid_y}</p>
            <p className="note">{task.slot_label} · {task.status}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {task.status === "assigned" && <button className="btn" onClick={() => void act(task.id, { to_status: "accepted" })}>接收</button>}
              {task.status === "assigned" && <button className="btn-ghost" onClick={() => void act(task.id, { to_status: "rejected", note: "参与者拒绝" })}>拒绝</button>}
              {task.status === "accepted" && <button className="btn" onClick={() => void act(task.id, { to_status: "in_progress" })}>开始</button>}
              {task.status === "in_progress" && <button className="btn" onClick={() => void simulate(task.id)}>仿真采样</button>}
            </div>
            {task.status === "in_progress" && (
              <div className="field" style={{ marginTop: 12 }}>
                手工测量值 dB
                <input type="number" value={level} onChange={(event) => setLevel(Number(event.target.value))} />
                <button className="btn" onClick={() => void act(task.id, { to_status: "submitted", measurement_db: level })}>提交测量</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </Page>
  );
}

function AssignPage({ role }: { role: string }) {
  const [algorithm, setAlgorithm] = useState("mupsa");
  const [limit, setLimit] = useState(3);
  const [result, setResult] = useState<{ assignments: { title?: string; reach_prob: number; score: number; value: number; assignee_name?: string; slot_label?: string }[]; reasons: string[]; budget_left: number } | null>(null);
  const [rows, setRows] = useState<{ id: number; task_id: number; participant_id: number; participant_name?: string | null; reach_prob: number; estimated_cost: number; score: number; status: string }[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(() => api<{ items: typeof rows }>("/api/assignments").then((data) => setRows(data.items)).catch((reason: Error) => setError(reason.message)), []);
  useEffect(() => { void load(); }, [load]);
  async function run() {
    setError("");
    try {
      const data = await api<NonNullable<typeof result>>("/api/assignments/run", { method: "POST", body: JSON.stringify({ algorithm, limit }) });
      setResult(data);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "分配失败");
    }
  }
  return (
    <Page title="智能分配" lede="分配使用当前观测和历史轨迹预测下一时间片的到达概率。到达概率、接受概率和执行成功被分开计算。">
      {error && <p className="error">{error}</p>}
      {(role === "admin" || role === "publisher") && (
        <section className="panel">
          <div className="form-grid">
            <label className="field">策略
              <select value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}>
                {["eer_reach", "mupsa", "mupsa_constrained", "greedy", "uncertainty", "nearest", "random", "min_cost", "bandit"].map((item) => <option key={item}>{item}</option>)}
              </select>
            </label>
            <label className="field">本轮上限<input type="number" min={1} max={8} value={limit} onChange={(event) => setLimit(Number(event.target.value))} /></label>
          </div>
          <button className="btn" onClick={() => void run()}>执行分配</button>
          {result && <p className="note">剩余预算 {result.budget_left.toFixed(2)}。{result.reasons.join("；") || `新分配 ${result.assignments.length} 条。`}</p>}
        </section>
      )}
      <section className="panel">
        <h2>分配记录</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>任务</th><th>参与者</th><th>到达概率</th><th>成本</th><th>分数</th><th>状态</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.task_id}</td><td>{row.participant_name || row.participant_id}</td><td>{row.reach_prob.toFixed(2)}</td><td>{row.estimated_cost.toFixed(2)}</td><td>{row.score.toFixed(2)}</td><td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {rows.length === 0 && <p className="note">还没有分配记录。</p>}
      </section>
    </Page>
  );
}

function TracksPage() {
  const [people, setPeople] = useState<{ id: number; name: string; participant_type: string }[]>([]);
  const [person, setPerson] = useState<number | null>(null);
  const [points, setPoints] = useState<{ slot: number; grid_id: number | null; timestamp: string; quality_flags: string }[]>([]);
  const [stats, setStats] = useState<{ by_timeslot: number[]; hot_grids: { grid_id: number; count: number }[] } | null>(null);
  const [forecast, setForecast] = useState<{ top: { x: number; y: number; probability: number }[]; note: string } | null>(null);
  const [slot, setSlot] = useState(48);
  const [error, setError] = useState("");
  useEffect(() => {
    api<{ items: { id: number; name: string; participant_type: string }[] }>("/api/participants").then((data) => {
      setPeople(data.items);
      setPerson(data.items[0]?.id ?? null);
    }).catch((reason: Error) => setError(reason.message));
    api<{ by_timeslot: number[]; hot_grids: { grid_id: number; count: number }[] }>("/api/mobility/stats").then(setStats).catch(() => setStats(null));
  }, []);
  useEffect(() => {
    if (!person) return;
    api<{ items: { slot: number; grid_id: number | null; timestamp: string; quality_flags: string }[] }>(`/api/trajectories?participant_id=${person}&limit=200`).then((data) => setPoints(data.items)).catch((reason: Error) => setError(reason.message));
  }, [person]);
  const option = useMemo<echarts.EChartsOption>(() => ({
    grid: { left: 36, right: 10, top: 20, bottom: 28 },
    xAxis: { type: "category", data: stats?.by_timeslot.map((_, index) => String(index)) || [] },
    yAxis: { type: "value" },
    series: [{ type: "bar", data: stats?.by_timeslot || [], itemStyle: { color: "#1d6b5d" } }],
  }), [stats]);
  return (
    <Page title="轨迹分析" lede="热点和分时段计数来自当前世界写入数据库的轨迹点。合成演示、YJMob 匿名网格和 GeoLife 不会互相冒充，来源以仿真控制台为准。预测只使用目标时间片之前的历史。">
      {error && <p className="error">{error}</p>}
      <div className="grid-2">
        <section className="panel">
          <label className="field">参与者
            <select value={person ?? ""} onChange={(event) => setPerson(Number(event.target.value))}>
              {people.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.participant_type}</option>)}
            </select>
          </label>
          <label className="field">回放时间片 {slot}
            <input type="range" min={0} max={Math.max(1, points.length - 1)} value={Math.min(slot, Math.max(0, points.length - 1))} onChange={(event) => setSlot(Number(event.target.value))} />
          </label>
          <p>{points[slot] ? `${points[slot].timestamp} · 网格 ${points[slot].grid_id ?? "缺失"} · ${points[slot].quality_flags}` : "这个时间片没有点。"}</p>
          <button className="btn" onClick={() => person && api<{ top: { x: number; y: number; probability: number }[]; note: string }>(`/api/predictions/mobility?participant_id=${person}&slot=${Math.min(95, slot + 1)}`).then(setForecast).catch((reason: Error) => setError(reason.message))}>预测下一位置</button>
          {forecast && (
            <ul className="tape">
              {forecast.top.map((item) => <li key={`${item.x}-${item.y}`}>{item.x},{item.y} · {(item.probability * 100).toFixed(1)}%</li>)}
              <li>{forecast.note}</li>
            </ul>
          )}
        </section>
        <section className="panel">
          <h2>一天中的出现次数</h2>
          <Chart option={option} />
          <h2>热点网格</h2>
          <ul className="tape">{stats?.hot_grids.map((item) => <li key={item.grid_id}>网格 {item.grid_id} · {item.count} 次</li>)}</ul>
        </section>
      </div>
    </Page>
  );
}

function PredictPage() {
  const [slot, setSlot] = useState(50);
  const [model, setModel] = useState("idw");
  const [data, setData] = useState<{ backend: string; mean_db: number; mean_uncertainty: number; observation_count: number; disclaimer: string; values: number[][]; uncertainty: number[][] } | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setError("");
    try {
      setData(await api(`/api/predictions/noise?slot=${slot}&model=${model}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "预测失败");
    }
  }
  useEffect(() => { void load(); }, []);
  return (
    <Page title="噪声预测" lede="可以在反距离加权、随机森林和固定核高斯过程之间切换。页面上的不确定性没有被声称成已经校准的置信区间。">
      {error && <p className="error">{error}</p>}
      <section className="panel">
        <div className="form-grid">
          <label className="field">模型
            <select value={model} onChange={(event) => setModel(event.target.value)}>
              <option value="idw">IDW 能量插值</option>
              <option value="random_forest">随机森林</option>
              <option value="gaussian_process">高斯过程</option>
            </select>
          </label>
          <label className="field">时间片<input type="number" value={slot} onChange={(event) => setSlot(Number(event.target.value))} /></label>
        </div>
        <button className="btn" onClick={() => void load()}>更新预测</button>
        {data && <p className="note">后端 {data.backend} · 平均 {data.mean_db.toFixed(2)} dB · 平均不确定性 {data.mean_uncertainty.toFixed(2)} · 观测 {data.observation_count}。{data.disclaimer}</p>}
      </section>
      {data && (
        <div className="grid-2">
          <Heat title="预测声级" matrix={data.values} />
          <Heat title="不确定性" matrix={data.uncertainty} />
        </div>
      )}
    </Page>
  );
}

function Heat({ title, matrix }: { title: string; matrix: number[][] }) {
  const flat = matrix.flat();
  const min = Math.min(...flat);
  const max = Math.max(...flat);
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(${matrix[0]?.length || 1}, 1fr)`, gap: 2 }}>
        {matrix.flatMap((row, y) => row.map((value, x) => (
          <div key={`${x}-${y}`} title={`${x},${y} ${value.toFixed(1)}`} style={{ aspectRatio: "1", background: mixColor((value - min) / Math.max(0.001, max - min)) }} />
        )))}
      </div>
    </section>
  );
}

function mixColor(t: number) {
  const clamped = Math.max(0, Math.min(1, t));
  const r = Math.round(23 + clamped * 150);
  const g = Math.round(90 - clamped * 30);
  const b = Math.round(80 - clamped * 40);
  return `rgb(${r},${g},${b})`;
}

function SimPage({ role }: { role: string }) {
  const [state, setState] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [keptPreviousWorld, setKeptPreviousWorld] = useState(false);
  const [form, setForm] = useState({
    scenario: "complex",
    seed: 7,
    algorithm: "mupsa",
    budget: 24,
    n_human: 14,
    n_machine: 4,
    accept_human: 0.72,
    mode: "synthetic",
    mobility_source: "yjmob_dataset1",
    noise_source: "synthetic_field",
    n_users: 10,
    grid_m: 500,
    noise_country: "France",
    day_min: 0,
  });
  const [busy, setBusy] = useState(false);
  const dirty = useRef(false);
  const load = useCallback(() => api<Record<string, unknown>>("/api/simulation").then(setState).catch((reason: Error) => setError(reason.message)), []);
  useEffect(() => { void load(); }, [load]);
  function applyServerForm(next: Record<string, unknown>) {
    const config = (next.config || {}) as Record<string, unknown>;
    const knownMobility = ["yjmob_dataset1", "yjmob_dataset2", "geolife"];
    const mobility = String(config.mobility_source || "");
    setForm((current) => ({
      ...current,
      mode: String(next.mode || current.mode),
      mobility_source: knownMobility.includes(mobility) ? mobility : current.mobility_source,
      noise_source: String(next.noise_source || current.noise_source),
      algorithm: String(next.algorithm || current.algorithm),
      scenario: String(next.scenario || current.scenario),
      seed: Number(next.seed ?? current.seed),
      budget: Number(next.budget_total ?? current.budget),
    }));
  }
  useEffect(() => {
    if (!state || dirty.current) return;
    applyServerForm(state);
  }, [state]);
  async function control(action: string, steps = 1) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const next = await api<Record<string, unknown>>("/api/simulation/control", { method: "POST", body: JSON.stringify({ action, steps, ...form }) });
      dirty.current = false;
      setState(next);
      applyServerForm(next);
      setKeptPreviousWorld(false);
    } catch (reason) {
      setKeptPreviousWorld(action === "reset");
      setError(reason instanceof Error ? reason.message : "仿真操作失败");
    } finally {
      setBusy(false);
    }
  }
  const metrics = (state?.metrics || {}) as { mae_current_slot?: number; coverage?: number };
  const log = (state?.log || []) as string[];
  return (
    <Page title="仿真控制台" lede="重置会按所选数据源重建世界，而不是只改标签。单步推进执行到期任务。决策不读取未来轨迹；真值只在采样成功或评估时使用。">
      {error && (
        <p className="error">
          {error}
          {keptPreviousWorld && " 画面仍是上一次成功加载的世界。缺失的真实数据不会被悄悄换成合成轨迹。"}
        </p>
      )}
      <section className="panel" onChange={() => { dirty.current = true; }}>
        <div className="form-grid">
          <label className="field">数据模式
            <select value={form.mode} onChange={(event) => setForm({ ...form, mode: event.target.value, noise_source: event.target.value === "real_noise" ? "NoiseCapture" : "synthetic_field", mobility_source: event.target.value === "synthetic" ? "synthetic" : form.mobility_source })}>
              <option value="synthetic">Synthetic Demo</option>
              <option value="real_mobility">Real-Mobility</option>
              <option value="real_noise">Real-Noise</option>
              <option value="fully_real">Fully-Real</option>
            </select>
          </label>
          {form.mode === "real_mobility" && (
            <label className="field">移动来源
              <select value={form.mobility_source} onChange={(event) => setForm({ ...form, mobility_source: event.target.value })}>
                <option value="yjmob_dataset1">YJMob dataset1 匿名网格</option>
                <option value="yjmob_dataset2">YJMob dataset2 匿名网格</option>
                <option value="geolife">GeoLife WGS84</option>
              </select>
            </label>
          )}
          {form.mode === "real_noise" && (
            <label className="field">噪声国家<input value={form.noise_country} onChange={(event) => setForm({ ...form, noise_country: event.target.value })} /></label>
          )}
          <label className="field">场景<select value={form.scenario} onChange={(event) => setForm({ ...form, scenario: event.target.value })}><option>regular</option><option>complex</option><option>shift</option></select></label>
          <label className="field">种子<input type="number" value={form.seed} onChange={(event) => setForm({ ...form, seed: Number(event.target.value) })} /></label>
          <label className="field">算法<select value={form.algorithm} onChange={(event) => setForm({ ...form, algorithm: event.target.value })}>{["eer_reach", "mupsa", "reach_nearest", "reach_greedy", "reach_random", "greedy", "uncertainty", "nearest", "random", "min_cost"].map((item) => <option key={item}>{item}</option>)}</select></label>
          <label className="field">预算<input type="number" value={form.budget} onChange={(event) => setForm({ ...form, budget: Number(event.target.value) })} /></label>
          <label className="field">{form.mode === "synthetic" ? "人数" : "真实用户上限"}<input type="number" value={form.mode === "synthetic" ? form.n_human : form.n_users} onChange={(event) => setForm(form.mode === "synthetic" ? { ...form, n_human: Number(event.target.value) } : { ...form, n_users: Number(event.target.value) })} /></label>
          <label className="field">机器数<input type="number" value={form.n_machine} onChange={(event) => setForm({ ...form, n_machine: Number(event.target.value) })} /></label>
          <label className="field">接受概率<input type="number" step="0.05" value={form.accept_human} onChange={(event) => setForm({ ...form, accept_human: Number(event.target.value) })} /></label>
        </div>
        {(role === "admin" || role === "publisher") && (
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            <button className="btn" disabled={busy} onClick={() => void control("step", 1)}>单步</button>
            <button className="btn" disabled={busy} onClick={() => void control("step", 4)}>前进 4 步</button>
            <button className="btn-ghost" disabled={busy} onClick={() => void control("pause")}>暂停</button>
            <button className="btn-ghost" disabled={busy} onClick={() => void control("resume")}>继续</button>
            <button className="btn-danger" disabled={busy} onClick={() => void control("reset")}>按参数重置</button>
          </div>
        )}
      </section>
      {state && (
        <div className="grid-2">
          <section className="panel">
            <h2>{String(state.current_label || "")}</h2>
            <p>来源 {String(state.mode || "synthetic")} · 移动 {String(state.mobility_source || "—")} · 噪声 {String(state.noise_source || "—")} · 用户 {String(state.user_count ?? "—")}</p>
            <p>状态 {String(state.status)} · 算法 {String(state.algorithm || form.algorithm)} · 预算剩余 {Number(state.budget_left).toFixed(2)} · 已花费 {Number(state.budget_spent).toFixed(2)}</p>
            <p>当前片 MAE {metrics.mae_current_slot?.toFixed(2) ?? "尚未计算"} · 覆盖 {metrics.coverage ? `${(metrics.coverage * 100).toFixed(1)}%` : "—"}</p>
          </section>
          <section className="panel">
            <h2>日志</h2>
            <ul className="tape">{log.slice(-12).map((line, index) => <li key={`${line}-${index}`}>{line}</li>)}</ul>
            {log.length === 0 && <p className="note">还没有步进日志。</p>}
          </section>
        </div>
      )}
    </Page>
  );
}

type SummaryRow = { scenario: string; method: string; budget: number; mae_causal_mean: number; coverage_mean: number; successful_tasks_mean: number };
type Archived = { path?: string; protocol?: string | { name?: string }; summary: SummaryRow[]; mobility?: { top1: number; top3: number; nll: number } } | null;

function ExperimentsPage({ role }: { role: string }) {
  const [payload, setPayload] = useState<{ items: { id: number; name: string; status: string; profile: string }[]; archived: Archived; legacy?: Archived; phase2?: Archived } | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => api<NonNullable<typeof payload>>("/api/experiments").then(setPayload).catch((reason: Error) => setError(reason.message)), []);
  useEffect(() => { void load(); }, [load]);
  async function run(profile: string) {
    setError("");
    try {
      await api("/api/experiments", { method: "POST", body: JSON.stringify({ profile }) });
      window.setTimeout(() => void load(), 1500);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法启动实验");
    }
  }
  const phase2 = payload?.phase2;
  const legacy = payload?.legacy || payload?.archived;
  const summary = (phase2?.summary?.length ? phase2.summary : []) as SummaryRow[];
  const focus = summary.filter((row) => row.scenario === "regular");
  const methods = [...new Set(focus.map((row) => row.method))];
  const option = useMemo<echarts.EChartsOption>(() => ({
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", top: 0, textStyle: { fontSize: 11 } },
    grid: { left: 48, right: 16, top: 48, bottom: 36 },
    xAxis: { type: "category", name: "预算", data: [...new Set(focus.map((row) => String(row.budget)))] },
    yAxis: { type: "value", name: "MAE" },
    series: methods.map((method) => ({
      name: method,
      type: "line",
      data: focus.filter((row) => row.method === method).sort((a, b) => a.budget - b.budget).map((row) => Number(row.mae_causal_mean.toFixed(3))),
    })),
  }), [focus, methods]);
  return (
    <Page title="算法实验" lede="公平协议曲线读取 experiments/results/phase2 的结果文件。旧协议数字单独标为 legacy，页面不会覆盖那份归档。">
      {error && <p className="error">{error}</p>}
      {(role === "admin" || role === "publisher") && (
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn" onClick={() => void run("phase2")}>运行 phase2</button>
          <button className="btn-ghost" onClick={() => void run("smoke")}>运行 smoke</button>
          <button className="btn-ghost" onClick={() => void load()}>刷新</button>
        </div>
      )}
      <p className="note">当前图：{summary.length ? "phase2 / mae_available_at_t（历史列名 mae_causal）" : "phase2 结果文件还不存在。"} 旧协议文件 {legacy?.path || "experiments/results/main/summary.json"} 保留，不参与这张图。图中的 bandit 仍是到达门控修订前的主表，修订后的复核不在这张图里。</p>
      <section className="panel"><h2>公平协议 MAE</h2>{summary.length ? <Chart option={option} height={300} /> : <p className="note">还没有 phase2 summary。命令行跑完 scripts/run_phase2_episodes.py 后点刷新。</p>}</section>
      <section className="panel">
        <h2>运行记录</h2>
        <div className="table-wrap"><table>
          <thead><tr><th>编号</th><th>名称</th><th>配置</th><th>状态</th><th></th></tr></thead>
          <tbody>
            {payload?.items.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td><td>{item.name}</td><td>{item.profile}</td><td>{item.status}</td>
                <td><button className="btn-ghost" onClick={() => void download(`/api/experiments/${item.id}/export`, `experiment-${item.id}.csv`)}>导出</button></td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {payload?.items.length === 0 && <p className="note">还没有从页面启动的实验。下方曲线如果存在，来自命令行已经生成的归档结果。</p>}
      </section>
    </Page>
  );
}

type DownloadRow = { dataset?: string; name?: string; status?: string; bytes?: number; sha256?: string; error?: string | null; license?: string };
type Platform = { data_dir?: string; downloads?: DownloadRow[] | null; processed?: Record<string, { status?: string; rows?: number; users?: number; point_rows?: number }> };

function DataPage({ role }: { role: string }) {
  const [items, setItems] = useState<{ id: number; kind: string; name: string; source: string; is_synthetic: boolean; license: string; record_count: number; missing_rate: number; spatial_desc: string; time_start: string; time_end: string; status: string; notes: string; coordinate_system: string }[]>([]);
  const [platform, setPlatform] = useState<Platform | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api<{ items: typeof items }>("/api/datasets").then((data) => setItems(data.items)).catch((reason: Error) => setError(reason.message));
    api<Platform>("/api/data/platform").then(setPlatform).catch((reason: Error) => setError(reason.message));
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function upload(file: File) {
    const body = new FormData();
    body.append("file", file);
    setError("");
    try {
      await api("/api/datasets/import", { method: "POST", body });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "导入失败");
    }
  }
  return (
    <Page title="数据管理" lede="下载和预处理状态来自 data/manifests。YJMob 是匿名虚拟网格，不会标成北京或东京。原始轨迹不进入页面上的合成城市。">
      {error && <p className="error">{error}</p>}
      <section className="panel">
        <h2>数据平台</h2>
        <p className="note">目录 {platform?.data_dir || "—"}。下面的字节数和状态来自下载清单，不是论文里的数字。</p>
        <div className="table-wrap"><table>
          <thead><tr><th>数据集</th><th>文件</th><th>状态</th><th>字节</th><th>sha256</th><th>错误</th></tr></thead>
          <tbody>
            {(platform?.downloads || []).map((row) => (
              <tr key={`${row.dataset}-${row.name}`}>
                <td>{row.dataset}</td>
                <td>{row.name}</td>
                <td>{row.status}</td>
                <td>{row.bytes ?? "—"}</td>
                <td className="note">{row.sha256 ? `${row.sha256.slice(0, 12)}…` : "—"}</td>
                <td>{row.error || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
        {!platform?.downloads && <p className="note">还没有 download_manifest.json。</p>}
      </section>
      {(role === "admin" || role === "publisher") && (
        <label className="btn-ghost">导入文件
          <input hidden type="file" accept=".csv,.geojson,.json,.plt,.txt" onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
        </label>
      )}
      {items.map((item) => (
        <article className="panel" key={`${item.kind}-${item.id}`}>
          <h2>{item.name} {item.is_synthetic ? <span className="tag warn">Synthetic Demo</span> : <span className="tag ok">{item.source}</span>}</h2>
          <p className="note">{item.notes}</p>
          <p>记录 {item.record_count} · 缺失率 {(item.missing_rate * 100).toFixed(1)}% · {item.coordinate_system}</p>
          <p className="note">{item.spatial_desc} · {item.time_start} → {item.time_end} · {item.license}</p>
        </article>
      ))}
    </Page>
  );
}

function AdminPage({ role }: { role: string }) {
  const [users, setUsers] = useState<{ id: number; username: string; display_name: string; role: string }[]>([]);
  const [devices, setDevices] = useState<{ id: number; name: string; kind: string; status: string }[]>([]);
  const [people, setPeople] = useState<{ id: number; name: string; participant_type: string; online: boolean; accept_prob: number; cost: number }[]>([]);
  const [audit, setAudit] = useState<{ id: number; action: string; detail: string; created_at: string }[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ username: "", password: "ChangeMe#2026demo", display_name: "", role: "collector" });
  const load = useCallback(async () => {
    if (role !== "admin") return;
    try {
      const [userRows, deviceRows, personRows, auditRows] = await Promise.all([
        api<{ items: typeof users }>("/api/users"),
        api<{ items: typeof devices }>("/api/devices"),
        api<{ items: typeof people }>("/api/participants"),
        api<{ items: typeof audit }>("/api/audit"),
      ]);
      setUsers(userRows.items);
      setDevices(deviceRows.items);
      setPeople(personRows.items);
      setAudit(auditRows.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "管理数据加载失败");
    }
  }, [role]);
  useEffect(() => { void load(); }, [load]);
  if (role !== "admin") return <Page title="系统管理" lede="只有管理员可以进入用户、设备和审计。"><p className="note">当前账号没有管理权限。</p></Page>;
  return (
    <Page title="系统管理" lede="用户、设备在线状态和审计日志都写在数据库里。新用户的密码只在创建时提交，之后以 PBKDF2 哈希保存。">
      {error && <p className="error">{error}</p>}
      <section className="panel">
        <h2>新建用户</h2>
        <div className="form-grid">
          <label className="field">用户名<input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
          <label className="field">显示名<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label>
          <label className="field">密码<input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
          <label className="field">角色<select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}><option>collector</option><option>publisher</option><option>admin</option></select></label>
        </div>
        <button className="btn" onClick={() => void api("/api/users", { method: "POST", body: JSON.stringify(form) }).then(() => load()).catch((reason: Error) => setError(reason.message))}>创建</button>
      </section>
      <div className="grid-2">
        <section className="panel">
          <h2>用户</h2>
          <ul className="tape">{users.map((item) => <li key={item.id}>{item.display_name} · {item.username} · {item.role}</li>)}</ul>
          <h2>设备</h2>
          <ul className="tape">{devices.map((item) => <li key={item.id}>{item.name} · {item.kind} · {item.status}</li>)}</ul>
        </section>
        <section className="panel">
          <h2>参与者在线</h2>
          <ul className="tape">
            {people.map((item) => (
              <li key={item.id}>
                {item.name} · {item.participant_type} · 接受 {item.accept_prob} · 成本 {item.cost}
                <button className="btn-ghost" onClick={() => void api(`/api/participants/${item.id}`, { method: "PATCH", body: JSON.stringify({ online: !item.online }) }).then(() => load())}>{item.online ? "下线" : "上线"}</button>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <section className="panel">
        <h2>审计</h2>
        <ul className="tape">{audit.map((item) => <li key={item.id}>{item.created_at} · {item.action} · {item.detail}</li>)}</ul>
      </section>
    </Page>
  );
}

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, ready, setUser } = useUser();
  useEffect(() => {
    if (user && !location.pathname.startsWith("/app")) {
      navigate(user.role === "collector" ? "/app/mine" : "/app", { replace: true });
    }
  }, [user, location.pathname, navigate]);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("DemoAdmin#2026");
  const [error, setError] = useState("");
  async function login(nextUser = username, nextPassword = password) {
    setError("");
    try {
      const data = await api<{ token: string; user: User }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username: nextUser, password: nextPassword }) });
      setToken(data.token);
      setUser(data.user);
      navigate(data.user.role === "collector" ? "/app/mine" : "/app");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    }
  }
  if (!ready) return <p className="page note">正在连接测站…</p>;
  if (!user) {
    return (
      <div className="login">
        <section className="login-hero">
          <div>
            <span className="kicker">BEIJING UNIVERSITY OF POSTS AND TELECOMMUNICATIONS</span>
            <h1>人机混合<br />城市噪声测站</h1>
          <p>在有限预算下，把移动预测、噪声不确定性和任务约束放进同一次分配。演示城市是虚拟网格，不是北京或东京的真实街区。</p>
        </div>
        <div className="login-facts">
          <article><b>三类角色</b><span>管理员、任务发布者、采集参与者。</span></article>
          <article><b>闭环采样</b><span>预测、分配、执行、回写、再规划。</span></article>
          <article><b>Synthetic Demo</b><span>离线可启动。外部数据按许可证导入。</span></article>
        </div>
        </section>
        <section className="login-card panel">
          <h2>登录</h2>
          <div className="field">用户名<input value={username} onChange={(event) => setUsername(event.target.value)} /></div>
          <div className="field" style={{ marginTop: 8 }}>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></div>
          {error && <p className="error">{error}</p>}
          <button className="btn" style={{ marginTop: 12 }} onClick={() => void login()}>进入测站</button>
          <div className="accounts" style={{ marginTop: 16 }}>
            {[
              ["admin", "DemoAdmin#2026", "管理员"],
              ["publisher", "DemoPublish#2026", "任务发布者"],
              ["collector", "DemoCollect#2026", "采集参与者"],
            ].map(([name, secret, label]) => (
              <button key={name} onClick={() => { setUsername(name); setPassword(secret); void login(name, secret); }}>{label} · {name}</button>
            ))}
          </div>
          <p className="note">这些密码只用于本地演示。</p>
        </section>
      </div>
    );
  }
  return (
    <Routes>
      <Route path="/app" element={<Shell user={user} onLogout={() => { setToken(null); setUser(null); navigate("/"); }} />}>
        <Route index element={<Dashboard />} />
        <Route path="map" element={<MapPage role={user.role} />} />
        <Route path="tasks" element={<TasksPage role={user.role} />} />
        <Route path="mine" element={<MinePage />} />
        <Route path="assign" element={<AssignPage role={user.role} />} />
        <Route path="tracks" element={<TracksPage />} />
        <Route path="predict" element={<PredictPage />} />
        <Route path="sim" element={<SimPage role={user.role} />} />
        <Route path="experiments" element={<ExperimentsPage role={user.role} />} />
        <Route path="data" element={<DataPage role={user.role} />} />
        <Route path="admin" element={<AdminPage role={user.role} />} />
      </Route>
    </Routes>
  );
}
