/* QVS 多云监控告警中心 v3.2 — 宝玉设计前端交互引擎（草稿保护 + 多云支持 + 逻辑自洽） */
const state = {
  token: localStorage.getItem("qvs_token") || "",
  user: null,
  currentPage: "dashboard",
  logTab: "tasks",
  sources: [],
  notifications: [],
  tasks: [],
  hideOnboarding: localStorage.getItem("qvs_hide_onboarding") === "1",
  theme: localStorage.getItem("qvs_theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  drafts: {}, // 弹窗草稿缓存：点击空白处关闭时保留，点取消/×/保存成功时清空
};

let activeModalMeta = { draftKey: null, collectDraft: null };

const PAGE_META = {
  dashboard: ["总览仪表盘", "实时掌握多云设备在线状态、巡检进度与告警健康度"],
  tasks: ["监控任务", "可视化配置巡检频率、防误报重试、冷却防轰炸与恢复通知"],
  sources: ["多云监控源", "统一接入七牛云 QVS、腾讯云视联、阿里云 VCS、自定义 HTTP 与演示源"],
  notifications: ["通知渠道", "配置钉钉、企业微信、飞书、NTFY 或自定义 Webhook 并一键测试"],
  logs: ["巡检与告警日志", "追踪每一次巡检明细与告警送达状态"],
  settings: ["系统自愈与设置", "查看数据库健康、调度器看门狗、一键备份恢复与账号管理"],
};

const PROVIDER_LABELS = {
  qiniu: "七牛云 QVS",
  tencent: "腾讯云视联",
  aliyun: "阿里云 VCS",
  custom: "自定义 HTTP",
  demo: "演示模拟源",
};

const NOTIF_LABELS = {
  dingtalk: "钉钉机器人",
  wecom: "企业微信机器人",
  feishu: "飞书机器人",
  ntfy: "NTFY 手机推送",
  webhook: "自定义 Webhook",
};

// ==================== 主题切换 ====================

function applyTheme(theme) {
  state.theme = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", state.theme);
  localStorage.setItem("qvs_theme", state.theme);
  const btn = document.getElementById("btn-theme-toggle");
  if (btn) btn.textContent = state.theme === "dark" ? "☀️ 浅色" : "🌙 深色";
}
applyTheme(state.theme);
document.getElementById("btn-theme-toggle").onclick = () => applyTheme(state.theme === "dark" ? "light" : "dark");

// ==================== 通用工具 ====================

function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

function toast(msg, type = "info") {
  const box = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    setTimeout(() => el.remove(), 220);
  }, 3600);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const resp = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  let data = null;
  try {
    data = await resp.json();
  } catch {
    data = { detail: `请求失败 (HTTP ${resp.status})` };
  }
  if (resp.status === 401 && state.token && !path.includes("/api/auth/login")) {
    logout(false);
    toast(data.detail || "登录已过期，请重新登录", "error");
    throw new Error(data.detail || "未登录");
  }
  if (!resp.ok) {
    throw new Error(data.detail || data.message || `操作失败 (HTTP ${resp.status})`);
  }
  return data;
}

// ==================== 智能弹窗（点击空白处保留草稿，点取消/×才清空） ====================

function openModal(title, bodyHtml, footerHtml = "", options = {}) {
  activeModalMeta = {
    draftKey: options.draftKey || null,
    collectDraft: options.collectDraft || null,
  };
  document.getElementById("modal-title").textContent = title;
  document.getElementById("modal-body").innerHTML = bodyHtml;
  document.getElementById("modal-footer").innerHTML = footerHtml;
  document.getElementById("modal-backdrop").classList.remove("hidden");
}

function hideModal({ preserveDraft = false } = {}) {
  if (activeModalMeta.draftKey) {
    if (preserveDraft && typeof activeModalMeta.collectDraft === "function") {
      try {
        state.drafts[activeModalMeta.draftKey] = activeModalMeta.collectDraft();
        toast("已保留未保存的填写内容，再次打开可继续编辑", "info");
      } catch {
        // ignore
      }
    } else {
      delete state.drafts[activeModalMeta.draftKey];
    }
  }
  activeModalMeta = { draftKey: null, collectDraft: null };
  document.getElementById("modal-backdrop").classList.add("hidden");
}

// 供弹窗内联 onclick="closeModal(true)" 调用（注意不再与顶层函数同名，彻底避免递归）
window.closeModal = (clear = true) => hideModal({ preserveDraft: !clear });

document.getElementById("modal-close").onclick = () => hideModal({ preserveDraft: false });
document.getElementById("modal-backdrop").addEventListener("click", (e) => {
  // 点击弹窗外部空白处：收起弹窗但完整保留已填草稿
  if (e.target.id === "modal-backdrop") hideModal({ preserveDraft: true });
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !document.getElementById("modal-backdrop").classList.contains("hidden")) {
    hideModal({ preserveDraft: true });
  }
});

// ==================== 视图切换与认证 ====================

function showScreen(name) {
  ["view-setup", "view-login", "view-app"].forEach((id) => {
    document.getElementById(id).classList.toggle("hidden", id !== name);
  });
}

function logout(showMsg = true) {
  state.token = "";
  state.user = null;
  localStorage.removeItem("qvs_token");
  showScreen("view-login");
  if (showMsg) toast("已安全退出登录", "info");
}

async function boot() {
  try {
    const sys = await api("/api/system/status");
    document.getElementById("app-version").textContent = `v${sys.version || "3.2.0"}`;
    if (!sys.initialized) {
      showScreen("view-setup");
      return;
    }
    if (!state.token) {
      showScreen("view-login");
      return;
    }
    const me = await api("/api/auth/me");
    enterApp(me);
  } catch {
    showScreen("view-login");
  }
}

function enterApp(user) {
  state.user = user;
  document.getElementById("current-username").textContent = user.username;
  document.getElementById("current-user-role").textContent = user.role === "admin" ? "管理员" : "普通成员";
  const adminCard = document.getElementById("users-admin-card");
  if (adminCard) adminCard.classList.toggle("hidden", user.role !== "admin");
  showScreen("view-app");
  switchPage("dashboard");
}

document.getElementById("btn-gen-pwd").onclick = () => {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$";
  let pwd = "";
  for (let i = 0; i < 12; i++) pwd += chars[Math.floor(Math.random() * chars.length)];
  const p1 = document.getElementById("setup-password");
  const p2 = document.getElementById("setup-password2");
  p1.type = "text";
  p2.type = "text";
  p1.value = pwd;
  p2.value = pwd;
  document.getElementById("setup-pwd-hint").textContent = `已生成强密码：${pwd}（请妥善记下）`;
};

document.getElementById("setup-form").onsubmit = async (e) => {
  e.preventDefault();
  const errBox = document.getElementById("setup-error");
  errBox.classList.add("hidden");
  const username = document.getElementById("setup-username").value.trim();
  const password = document.getElementById("setup-password").value;
  const password2 = document.getElementById("setup-password2").value;
  if (password !== password2) {
    errBox.textContent = "两次输入的密码不一致，请核对后重试。";
    errBox.classList.remove("hidden");
    return;
  }
  const btn = document.getElementById("btn-setup-submit");
  btn.disabled = true;
  try {
    const res = await api("/api/setup/init", { method: "POST", body: { username, password } });
    state.token = res.access_token;
    localStorage.setItem("qvs_token", state.token);
    toast(res.message || "初始化成功！", "ok");
    enterApp(res.user);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
};

document.getElementById("login-form").onsubmit = async (e) => {
  e.preventDefault();
  const errBox = document.getElementById("login-error");
  errBox.classList.add("hidden");
  const btn = document.getElementById("btn-login-submit");
  btn.disabled = true;
  try {
    const res = await api("/api/auth/login", {
      method: "POST",
      body: {
        username: document.getElementById("login-username").value.trim(),
        password: document.getElementById("login-password").value,
      },
    });
    state.token = res.access_token;
    localStorage.setItem("qvs_token", state.token);
    toast("登录成功", "ok");
    enterApp(res.user);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
};

document.getElementById("btn-logout").onclick = () => logout(true);
document.getElementById("btn-global-refresh").onclick = () => loadCurrentPage();
document.getElementById("btn-hide-onboarding").onclick = () => {
  state.hideOnboarding = true;
  localStorage.setItem("qvs_hide_onboarding", "1");
  document.getElementById("onboarding-banner").classList.add("hidden");
};

document.querySelectorAll("#sidebar-nav .nav-item").forEach((btn) => {
  btn.onclick = () => switchPage(btn.dataset.page);
});

window.switchPage = function (page) {
  state.currentPage = page;
  document.querySelectorAll("#sidebar-nav .nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === page);
  });
  document.querySelectorAll(".page-section").forEach((s) => {
    s.classList.toggle("hidden", s.id !== `page-${page}`);
  });
  const [title, sub] = PAGE_META[page] || ["控制台", ""];
  document.getElementById("page-title").textContent = title;
  document.getElementById("page-subtitle").textContent = sub;
  loadCurrentPage();
};

async function loadCurrentPage() {
  try {
    if (state.currentPage === "dashboard") await renderDashboard();
    else if (state.currentPage === "tasks") await renderTasks();
    else if (state.currentPage === "sources") await renderSources();
    else if (state.currentPage === "notifications") await renderNotifications();
    else if (state.currentPage === "logs") await renderLogs();
    else if (state.currentPage === "settings") await renderSettings();
  } catch (err) {
    toast(err.message, "error");
  }
}

// ==================== 页面 A：总览仪表盘 ====================

async function renderDashboard() {
  const data = await api("/api/dashboard/overview");
  const { onboarding, stats, scheduler, db_health, devices, recent_logs } = data;

  const pill = document.getElementById("sidebar-scheduler-pill");
  pill.innerHTML = scheduler.running
    ? `<span class="status-dot ok"></span><span>调度器运行中（${scheduler.enabled_tasks} 个任务）</span>`
    : `<span class="status-dot err"></span><span>调度器已暂停</span>`;

  const allDone = onboarding.has_source && onboarding.has_notification && onboarding.has_task;
  const obEl = document.getElementById("onboarding-banner");
  if (!allDone && !state.hideOnboarding) {
    obEl.classList.remove("hidden");
    const steps = [
      {
        done: onboarding.has_source,
        title: "第 1 步：添加监控源",
        desc: "接入七牛 / 腾讯 / 阿里 / 自定义接口，或直接用演示模拟源。",
        btn: "去配置监控源",
        page: "sources",
      },
      {
        done: onboarding.has_notification,
        title: "第 2 步：添加通知渠道",
        desc: "接入钉钉、企业微信、飞书或 NTFY，一键测试推送是否送达。",
        btn: "去配置通知",
        page: "notifications",
      },
      {
        done: onboarding.has_task,
        title: "第 3 步：新建巡检任务",
        desc: "选好巡检频率与防骚扰策略，开启后自动值守并推送恢复通知。",
        btn: "去新建任务",
        page: "tasks",
      },
    ];
    document.getElementById("onboarding-steps").innerHTML = steps
      .map(
        (s) => `
      <div class="step-box ${s.done ? "done" : ""}">
        <div>
          <div class="step-title">${s.done ? "✅" : "⭕"} ${s.title}</div>
          <div class="step-desc">${s.desc}</div>
        </div>
        <div>
          ${
            s.done
              ? `<span class="badge badge-ok">已完成</span>`
              : `<button class="btn btn-primary btn-sm" onclick="switchPage('${s.page}')">${s.btn}</button>`
          }
        </div>
      </div>`
      )
      .join("");
  } else {
    obEl.classList.add("hidden");
  }

  const healthOk = db_health.data_db_ok && db_health.logs_db_ok && scheduler.running;
  document.getElementById("dashboard-kpis").innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">设备在线 / 总数</div>
      <div class="kpi-value ${stats.offline_devices > 0 ? "danger" : "ok"}">${stats.online_devices} / ${stats.total_devices}</div>
      <div class="kpi-sub">当前离线异常：${stats.offline_devices} 台</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">自动巡检任务</div>
      <div class="kpi-value primary">${stats.enabled_task_count} / ${stats.task_count}</div>
      <div class="kpi-sub">监控源 ${stats.source_count} 个 · 通知渠道 ${stats.notification_count} 个</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">今日巡检 / 发送告警</div>
      <div class="kpi-value">${stats.today_checks} / ${stats.today_alerts}</div>
      <div class="kpi-sub">已启用防误报与冷却防轰炸保护</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">系统自愈健康状态</div>
      <div class="kpi-value ${healthOk ? "ok" : "danger"}">${healthOk ? "健康" : "需检查"}</div>
      <div class="kpi-sub">SQLite ${esc(db_health.journal_mode)} · 剩余空间 ${db_health.disk_free_mb} MB</div>
    </div>
  `;

  document.getElementById("device-count-badge").textContent = `${devices.length} 台`;
  const devWrap = document.getElementById("dashboard-devices");
  if (!devices.length) {
    devWrap.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <div class="empty-icon">📹</div>
      <div>暂无设备状态记录。创建监控任务并点击「立即巡检」后，所有摄像头状态将显示在这里。</div>
    </div>`;
  } else {
    devWrap.innerHTML = devices
      .map((d) => {
        const isOnline = d.current_state === "online";
        return `
        <div class="device-chip ${isOnline ? "online" : "offline"}">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:6px">
            <div class="device-chip-name">${esc(d.device_name || d.device_key)}</div>
            <span class="badge ${isOnline ? "badge-ok" : "badge-danger"}">${isOnline ? "在线" : "离线"}</span>
          </div>
          <div class="device-chip-id">${esc(d.device_key)}</div>
          <div style="font-size:11.5px;color:var(--text-muted);margin-top:6px">
            任务：${esc(d.task_name || "—")}<br/>
            更新：${fmtTime(d.updated_at)}
          </div>
        </div>`;
      })
      .join("");
  }

  const logWrap = document.getElementById("dashboard-recent-logs");
  if (!recent_logs.length) {
    logWrap.innerHTML = `<div class="empty-state"><div class="empty-icon">🕒</div><div>还没有执行过巡检任务</div></div>`;
  } else {
    logWrap.innerHTML = recent_logs
      .map((l) => {
        const bCls = l.status === "success" ? "badge-ok" : l.status === "failed" ? "badge-danger" : "badge-warn";
        const bTxt = l.status === "success" ? "成功" : l.status === "failed" ? "失败" : l.status;
        return `
        <div class="timeline-item">
          <div class="timeline-top">
            <strong>${esc(l.task_name)}</strong>
            <span class="badge ${bCls}">${bTxt}</span>
          </div>
          <div>${esc(l.message || "—")}</div>
          <div class="timeline-time">${fmtTime(l.started_at)} · 耗时 ${l.duration_ms || 0} ms</div>
        </div>`;
      })
      .join("");
  }
}

// ==================== 页面 B：监控任务 ====================

async function renderTasks() {
  const [tasks, sources, notifs] = await Promise.all([
    api("/api/tasks"),
    api("/api/source-channels"),
    api("/api/notification-channels"),
  ]);
  state.tasks = tasks;
  state.sources = sources;
  state.notifications = notifs;

  const box = document.getElementById("tasks-list");
  if (!tasks.length) {
    box.innerHTML = `<div class="card empty-state" style="grid-column:1/-1">
      <div class="empty-icon">⏱️</div>
      <div style="margin-bottom:12px">还没有监控任务。点击右上角「新建监控任务」即可开启自动巡检。</div>
      <button class="btn btn-primary" onclick="openTaskModal()">+ 立即新建监控任务</button>
    </div>`;
    return;
  }

  box.innerHTML = tasks
    .map((t) => {
      const statusBadge = t.is_enabled
        ? `<span class="badge badge-ok">自动运行中</span>`
        : `<span class="badge badge-muted">已暂停</span>`;
      const notifNames = t.notification_channel_names.length
        ? t.notification_channel_names.map((n) => `<span class="badge badge-primary">${esc(n)}</span>`).join(" ")
        : `<span class="badge badge-warn">未绑定通知渠道（仅记录日志）</span>`;
      return `
      <div class="item-card">
        <div class="item-head">
          <div>
            <h4 class="item-title">${esc(t.name)}</h4>
            <div style="margin-top:6px">${statusBadge} <span class="badge badge-muted">${esc(t.schedule_text)}</span></div>
          </div>
        </div>
        <div class="item-meta">
          <div>📡 监控源：<strong>${esc(t.source_channel_name)}</strong> ${t.gb_id ? `（单设备: ${esc(t.gb_id)}）` : "（监控全部设备）"}</div>
          <div>🔔 通知渠道：${notifNames}</div>
          <div>🛡️ 防误报：连续离线 <strong>${t.fail_threshold}</strong> 次告警 · 冷却 <strong>${t.cooldown_minutes === 0 ? "仅告警一次" : t.cooldown_minutes + " 分钟"}</strong> · 恢复通知：${t.notify_online ? "开" : "关"}</div>
          <div>🕒 上次巡检：${t.last_run_at ? `${fmtTime(t.last_run_at)} — ${esc(t.last_summary)}` : "尚未运行"}</div>
        </div>
        <div class="item-actions">
          <button class="btn btn-primary btn-sm" onclick="runTaskNow(${t.id}, this)">▶ 立即巡检</button>
          <button class="btn btn-secondary btn-sm" onclick="toggleTask(${t.id})">${t.is_enabled ? "暂停" : "启用"}</button>
          <button class="btn btn-secondary btn-sm" onclick="openTaskModal(${t.id})">编辑</button>
          <button class="btn btn-danger btn-sm" onclick="deleteTask(${t.id}, '${esc(t.name)}')">删除</button>
        </div>
      </div>`;
    })
    .join("");
}

document.getElementById("btn-add-task").onclick = () => openTaskModal();

window.openTaskModal = function (taskId = null) {
  if (!state.sources.length) {
    toast("请先在【多云监控源】里添加一个监控源（或演示模拟源）！", "info");
    switchPage("sources");
    return;
  }
  const draftKey = taskId ? `task_edit_${taskId}` : "task_new";
  const savedDraft = state.drafts[draftKey];
  const base = taskId ? state.tasks.find((x) => x.id === taskId) : null;
  const t = savedDraft || base;
  const mode = t?.schedule_mode || "interval";

  const srcOpts = state.sources
    .map((s) => `<option value="${s.id}" ${Number(t?.source_channel_id) === s.id ? "selected" : ""}>${esc(s.name)} (${PROVIDER_LABELS[s.provider] || s.provider})</option>`)
    .join("");

  const notifChecks = state.notifications.length
    ? state.notifications
        .map((n) => {
          const checked = t ? (t.notification_channel_ids || []).includes(n.id) : true;
          return `<label class="check-pill">
            <input type="checkbox" name="task-notif" value="${n.id}" ${checked ? "checked" : ""} />
            ${esc(n.name)} (${NOTIF_LABELS[n.type] || n.type})
          </label>`;
        })
        .join("")
    : `<div class="field-hint">暂无通知渠道，可先保存任务，稍后再到【通知渠道】添加并绑定。</div>`;

  const draftNotice = savedDraft
    ? `<div class="inline-alert info"><span>📝 已为您恢复上次未保存的草稿</span><button type="button" class="link-btn" id="btn-clear-draft">清空草稿</button></div>`
    : "";

  const body = `
    <div class="form-stack">
      ${draftNotice}
      <div class="field">
        <label>任务名称</label>
        <input type="text" id="tf-name" value="${esc(t?.name ?? "园区监控自动巡检")}" placeholder="例如：一楼摄像头巡检" />
      </div>
      <div class="form-row">
        <div class="field">
          <label>选择监控源</label>
          <select id="tf-source">${srcOpts}</select>
        </div>
        <div class="field">
          <label>指定单台设备 ID（选填）</label>
          <input type="text" id="tf-gbid" value="${esc(t?.gb_id || "")}" placeholder="留空则巡检全部设备" />
        </div>
      </div>

      <div class="form-row">
        <div class="field">
          <label>巡检频率方式</label>
          <select id="tf-mode">
            <option value="interval" ${mode === "interval" ? "selected" : ""}>每隔固定分钟（推荐）</option>
            <option value="daily" ${mode === "daily" ? "selected" : ""}>每天固定时间</option>
            <option value="cron" ${mode === "cron" ? "selected" : ""}>高级自定义 Cron</option>
          </select>
        </div>
        <div class="field" id="tf-interval-wrap">
          <label>每隔多久巡检一次</label>
          <select id="tf-interval">
            ${[1, 3, 5, 10, 15, 30, 60, 120]
              .map((m) => `<option value="${m}" ${Number(t?.interval_minutes || 5) === m ? "selected" : ""}>每 ${m >= 60 ? m / 60 + " 小时" : m + " 分钟"}</option>`)
              .join("")}
          </select>
        </div>
        <div class="field hidden" id="tf-daily-wrap">
          <label>每天几点执行</label>
          <input type="time" id="tf-daily" value="${esc(t?.daily_time || "09:00")}" />
        </div>
        <div class="field hidden" id="tf-cron-wrap">
          <label>Cron 表达式（5段）</label>
          <input type="text" id="tf-cron" value="${esc(t?.cron_expression || "*/5 * * * *")}" placeholder="*/5 * * * *" />
        </div>
      </div>

      <div class="field">
        <label>告警通知渠道（可多选）</label>
        <div class="checkbox-group">${notifChecks}</div>
      </div>

      <div class="form-row">
        <div class="field">
          <label>连续离线几次才告警（防误报）</label>
          <select id="tf-threshold">
            <option value="1" ${Number(t?.fail_threshold ?? 2) === 1 ? "selected" : ""}>1 次（立刻告警，适合演示/高敏）</option>
            <option value="2" ${Number(t?.fail_threshold ?? 2) === 2 ? "selected" : ""}>2 次（推荐，防瞬断误报）</option>
            <option value="3" ${Number(t?.fail_threshold ?? 2) === 3 ? "selected" : ""}>3 次（严格确认）</option>
          </select>
        </div>
        <div class="field">
          <label>持续离线重复提醒间隔</label>
          <select id="tf-cooldown">
            <option value="0" ${Number(t?.cooldown_minutes ?? 60) === 0 ? "selected" : ""}>仅首次离线告警，不再重复</option>
            <option value="30" ${Number(t?.cooldown_minutes ?? 60) === 30 ? "selected" : ""}>每 30 分钟提醒一次</option>
            <option value="60" ${Number(t?.cooldown_minutes ?? 60) === 60 ? "selected" : ""}>每 1 小时提醒一次（推荐）</option>
            <option value="240" ${Number(t?.cooldown_minutes ?? 60) === 240 ? "selected" : ""}>每 4 小时提醒一次</option>
            <option value="1440" ${Number(t?.cooldown_minutes ?? 60) === 1440 ? "selected" : ""}>每 24 小时提醒一次</option>
          </select>
        </div>
      </div>

      <div class="checkbox-group">
        <label class="checkbox-row"><input type="checkbox" id="tf-notify-off" ${t ? (t.notify_offline ? "checked" : "") : "checked"} /> 设备离线时发送告警</label>
        <label class="checkbox-row"><input type="checkbox" id="tf-notify-on" ${t ? (t.notify_online ? "checked" : "") : "checked"} /> 设备恢复在线时发送通知</label>
        <label class="checkbox-row"><input type="checkbox" id="tf-quiet" ${t?.quiet_hours_enabled ? "checked" : ""} /> 开启夜间免打扰时段</label>
      </div>
      <div id="tf-logic-warn" class="inline-alert warn hidden"></div>

      <div class="form-row ${t?.quiet_hours_enabled ? "" : "hidden"}" id="tf-quiet-row">
        <div class="field"><label>免打扰开始</label><input type="time" id="tf-qstart" value="${esc(t?.quiet_start || "23:00")}" /></div>
        <div class="field"><label>免打扰结束</label><input type="time" id="tf-qend" value="${esc(t?.quiet_end || "07:00")}" /></div>
      </div>
    </div>
  `;

  const collectTask = () => ({
    name: document.getElementById("tf-name").value.trim(),
    source_channel_id: Number(document.getElementById("tf-source").value),
    gb_id: document.getElementById("tf-gbid").value.trim(),
    schedule_mode: document.getElementById("tf-mode").value,
    interval_minutes: Number(document.getElementById("tf-interval").value),
    daily_time: document.getElementById("tf-daily").value,
    cron_expression: document.getElementById("tf-cron").value.trim(),
    is_enabled: base ? base.is_enabled : true,
    notification_channel_ids: Array.from(document.querySelectorAll('input[name="task-notif"]:checked')).map((el) => Number(el.value)),
    notify_offline: document.getElementById("tf-notify-off").checked,
    notify_online: document.getElementById("tf-notify-on").checked,
    fail_threshold: Number(document.getElementById("tf-threshold").value),
    cooldown_minutes: Number(document.getElementById("tf-cooldown").value),
    quiet_hours_enabled: document.getElementById("tf-quiet").checked,
    quiet_start: document.getElementById("tf-qstart").value,
    quiet_end: document.getElementById("tf-qend").value,
  });

  openModal(
    base ? "编辑监控任务" : "新建监控任务",
    body,
    `<button class="btn btn-secondary" onclick="closeModal(true)">取消</button>
     <button class="btn btn-primary" id="btn-save-task">保存任务</button>`,
    { draftKey, collectDraft: collectTask }
  );

  const clearBtn = document.getElementById("btn-clear-draft");
  if (clearBtn) {
    clearBtn.onclick = () => {
      delete state.drafts[draftKey];
      openTaskModal(taskId);
    };
  }

  const syncModeUI = () => {
    const m = document.getElementById("tf-mode").value;
    document.getElementById("tf-interval-wrap").classList.toggle("hidden", m !== "interval");
    document.getElementById("tf-daily-wrap").classList.toggle("hidden", m !== "daily");
    document.getElementById("tf-cron-wrap").classList.toggle("hidden", m !== "cron");
  };
  document.getElementById("tf-mode").onchange = syncModeUI;
  syncModeUI();

  const checkLogicWarn = () => {
    const warn = document.getElementById("tf-logic-warn");
    const off = document.getElementById("tf-notify-off").checked;
    const on = document.getElementById("tf-notify-on").checked;
    const qEn = document.getElementById("tf-quiet").checked;
    const qs = document.getElementById("tf-qstart").value;
    const qe = document.getElementById("tf-qend").value;
    if (!off && !on) {
      warn.textContent = "⚠️ 提示：离线告警与恢复通知均已关闭，此任务将仅记录巡检日志，不会推送任何消息。";
      warn.classList.remove("hidden");
    } else if (qEn && qs === qe) {
      warn.textContent = "⚠️ 提示：免打扰开始时间与结束时间相同，请修改为不同时间。";
      warn.classList.remove("hidden");
    } else {
      warn.classList.add("hidden");
    }
  };
  ["tf-notify-off", "tf-notify-on", "tf-quiet", "tf-qstart", "tf-qend"].forEach((id) => {
    document.getElementById(id).onchange = () => {
      document.getElementById("tf-quiet-row").classList.toggle("hidden", !document.getElementById("tf-quiet").checked);
      checkLogicWarn();
    };
  });
  checkLogicWarn();

  document.getElementById("btn-save-task").onclick = async () => {
    const payload = collectTask();
    if (!payload.name) return toast("请填写任务名称", "error");
    if (payload.quiet_hours_enabled && payload.quiet_start === payload.quiet_end) {
      return toast("免打扰开始时间与结束时间不能相同", "error");
    }
    try {
      if (base) await api(`/api/tasks/${base.id}`, { method: "PUT", body: payload });
      else await api("/api/tasks", { method: "POST", body: payload });
      hideModal({ preserveDraft: false });
      toast(base ? "任务已更新" : "监控任务已创建并自动启用", "ok");
      renderTasks();
    } catch (err) {
      toast(err.message, "error");
    }
  };
};

window.runTaskNow = async function (id, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = "巡检中...";
  try {
    const res = await api(`/api/tasks/${id}/run`, { method: "POST" });
    toast(res.message || "巡检完成", res.ok ? "ok" : "error");
    renderTasks();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
};

window.toggleTask = async function (id) {
  try {
    const res = await api(`/api/tasks/${id}/toggle`, { method: "PATCH" });
    toast(res.is_enabled ? "任务已启用" : "任务已暂停", "ok");
    renderTasks();
  } catch (err) {
    toast(err.message, "error");
  }
};

window.deleteTask = async function (id, name) {
  if (!confirm(`确定要删除监控任务「${name}」吗？`)) return;
  try {
    await api(`/api/tasks/${id}`, { method: "DELETE" });
    toast("任务已删除", "ok");
    renderTasks();
  } catch (err) {
    toast(err.message, "error");
  }
};

// ==================== 页面 C：多云监控源配置 ====================

async function renderSources() {
  const sources = await api("/api/source-channels");
  state.sources = sources;
  const box = document.getElementById("sources-list");
  if (!sources.length) {
    box.innerHTML = `<div class="card empty-state" style="grid-column:1/-1">
      <div class="empty-icon">📡</div>
      <div style="margin-bottom:12px">还没有配置监控源。支持七牛云、腾讯云、阿里云、自定义 HTTP 接口，也可先建演示模拟源体验！</div>
      <button class="btn btn-primary" onclick="openSourceModal()">+ 添加监控源</button>
    </div>`;
    return;
  }

  box.innerHTML = sources
    .map((s) => {
      const pLabel = PROVIDER_LABELS[s.provider] || s.provider;
      const pBadgeCls = s.provider === "demo" ? "badge-warn" : "badge-primary";
      const testBadge =
        s.last_test_status === "ok"
          ? `<span class="badge badge-ok">连通正常</span>`
          : s.last_test_status === "failed"
          ? `<span class="badge badge-danger">连接异常</span>`
          : `<span class="badge badge-muted">未测试</span>`;

      let detailHtml = "";
      if (s.provider === "demo") {
        detailHtml = `<div>模拟设备总数：<strong>${s.config.demo_total_count ?? 4}</strong> 台（其中模拟离线 <strong>${s.config.demo_offline_count ?? 1}</strong> 台）</div>`;
      } else if (s.provider === "qiniu") {
        detailHtml = `<div>Namespace ID：<code>${esc(s.namespace_id || "—")}</code></div>
                      <div>Access Key：<code>${esc(s.config.access_key || "—")}</code></div>`;
      } else if (s.provider === "tencent") {
        detailHtml = `<div>区域 / 接口：<code>${esc(s.config.region || "ap-guangzhou")}</code> · <code>${esc(s.config.action || "DescribeAllDeviceList")}</code></div>
                      <div>SecretId：<code>${esc(s.config.secret_id || "—")}</code></div>`;
      } else if (s.provider === "aliyun") {
        detailHtml = `<div>接口域名：<code>${esc(s.config.endpoint || "vcs.cn-shanghai.aliyuncs.com")}</code></div>
                      <div>AccessKey ID：<code>${esc(s.config.access_key_id || "—")}</code></div>`;
      } else {
        detailHtml = `<div style="word-break:break-all">接口地址：<code>${esc(s.config.method || "GET")} ${esc(s.config.url || "—")}</code></div>`;
      }

      return `
      <div class="item-card">
        <div class="item-head">
          <div>
            <h4 class="item-title">${esc(s.name)}</h4>
            <div style="margin-top:6px"><span class="badge ${pBadgeCls}">${esc(pLabel)}</span> ${testBadge}</div>
          </div>
        </div>
        <div class="item-meta">
          ${detailHtml}
          ${s.last_test_message ? `<div>最近测试：${esc(s.last_test_message)}</div>` : ""}
        </div>
        <div class="item-actions">
          <button class="btn btn-primary btn-sm" onclick="testSavedSource(${s.id}, this)">🔍 测试并预览设备</button>
          <button class="btn btn-secondary btn-sm" onclick="openSourceModal(${s.id})">编辑</button>
          <button class="btn btn-danger btn-sm" onclick="deleteSource(${s.id}, '${esc(s.name)}')">删除</button>
        </div>
      </div>`;
    })
    .join("");
}

document.getElementById("btn-add-source").onclick = () => openSourceModal();

window.openSourceModal = function (sourceId = null) {
  const draftKey = sourceId ? `source_edit_${sourceId}` : "source_new";
  const savedDraft = state.drafts[draftKey];
  const base = sourceId ? state.sources.find((x) => x.id === sourceId) : null;
  const s = savedDraft || base;
  let selectedProvider = s?.provider || "qiniu";

  // 独立保留各平台已填配置，切换平台再切回不丢数据
  const perProviderCfg = {};
  if (s?.provider && s?.config) perProviderCfg[s.provider] = { ...s.config };

  const platforms = [
    ["qiniu", "☁️ 七牛云 QVS"],
    ["tencent", "🐧 腾讯云视联"],
    ["aliyun", "🟠 阿里云 VCS"],
    ["custom", "🔌 自定义 HTTP"],
    ["demo", "🧪 演示模拟源"],
  ];

  const draftNotice = savedDraft
    ? `<div class="inline-alert info"><span>📝 已为您恢复上次未保存的草稿</span><button type="button" class="link-btn" id="btn-clear-src-draft">清空草稿</button></div>`
    : "";

  const body = `
    <div class="form-stack">
      ${draftNotice}
      <div class="field">
        <label>监控源名称</label>
        <input type="text" id="sf-name" value="${esc(s?.name || "")}" placeholder="例如：总部门店七牛监控空间" />
      </div>
      <div class="field">
        <label>选择监控服务商</label>
        <div class="platform-grid">
          ${platforms
            .map(([k, lbl]) => `<div class="platform-opt ${selectedProvider === k ? "active" : ""}" data-sp="${k}">${lbl}</div>`)
            .join("")}
        </div>
      </div>
      <div id="sf-dynamic" class="form-stack"></div>
      <div id="sf-test-result" class="inline-alert hidden"></div>
    </div>
  `;

  const snapshotCurrentProviderFields = () => {
    const cfg = {};
    if (selectedProvider === "qiniu") {
      cfg.access_key = document.getElementById("sf-ak")?.value.trim() || "";
      cfg.secret_key = document.getElementById("sf-sk")?.value.trim() || "";
      cfg._ns = document.getElementById("sf-ns")?.value.trim() || "";
    } else if (selectedProvider === "tencent") {
      cfg.secret_id = document.getElementById("sf-tc-id")?.value.trim() || "";
      cfg.secret_key = document.getElementById("sf-tc-key")?.value.trim() || "";
      cfg.region = document.getElementById("sf-tc-region")?.value.trim() || "ap-guangzhou";
      cfg.endpoint = document.getElementById("sf-tc-ep")?.value.trim() || "iotvideoindustry.tencentcloudapi.com";
      cfg.action = document.getElementById("sf-tc-action")?.value.trim() || "DescribeAllDeviceList";
      cfg.api_version = document.getElementById("sf-tc-ver")?.value.trim() || "2020-12-01";
      cfg._ns = document.getElementById("sf-tc-group")?.value.trim() || "";
    } else if (selectedProvider === "aliyun") {
      cfg.access_key_id = document.getElementById("sf-ali-ak")?.value.trim() || "";
      cfg.access_key_secret = document.getElementById("sf-ali-sk")?.value.trim() || "";
      cfg.endpoint = document.getElementById("sf-ali-ep")?.value.trim() || "vcs.cn-shanghai.aliyuncs.com";
      cfg.action = document.getElementById("sf-ali-action")?.value.trim() || "ListDevices";
      cfg.api_version = document.getElementById("sf-ali-ver")?.value.trim() || "2020-05-15";
      cfg._ns = document.getElementById("sf-ali-corp")?.value.trim() || "";
    } else if (selectedProvider === "custom") {
      cfg.url = document.getElementById("sf-cu-url")?.value.trim() || "";
      cfg.method = document.getElementById("sf-cu-method")?.value || "GET";
      cfg.headers = document.getElementById("sf-cu-headers")?.value.trim() || "";
      cfg.items_path = document.getElementById("sf-cu-path")?.value.trim() || "";
      cfg.id_field = document.getElementById("sf-cu-id")?.value.trim() || "gbId";
      cfg.name_field = document.getElementById("sf-cu-name")?.value.trim() || "name";
      cfg.state_field = document.getElementById("sf-cu-state")?.value.trim() || "state";
      cfg.online_values = document.getElementById("sf-cu-online")?.value.trim() || "online,1,true,ON";
    } else if (selectedProvider === "demo") {
      const totalRaw = Number(document.getElementById("sf-demo-total")?.value || 4);
      const total = Math.max(1, Math.min(50, Math.floor(isNaN(totalRaw) ? 4 : totalRaw)));
      const offRaw = Number(document.getElementById("sf-demo-off")?.value ?? 1);
      const offline = Math.max(0, Math.min(total, Math.floor(isNaN(offRaw) ? 0 : offRaw)));
      cfg.demo_total_count = total;
      cfg.demo_offline_count = offline;
      cfg._ns = "demo-ns";
    }
    perProviderCfg[selectedProvider] = cfg;
    return cfg;
  };

  const collectSource = () => {
    const cfg = { ...snapshotCurrentProviderFields() };
    const ns = cfg._ns ?? (s?.namespace_id || "");
    delete cfg._ns;
    return {
      name: document.getElementById("sf-name").value.trim(),
      provider: selectedProvider,
      namespace_id: ns,
      config: cfg,
      is_active: true,
    };
  };

  openModal(
    base ? "编辑监控源" : "添加监控源",
    body,
    `<button class="btn btn-secondary" onclick="closeModal(true)">取消</button>
     <button class="btn btn-secondary" id="btn-test-source-form">🔍 先测试连接</button>
     <button class="btn btn-primary" id="btn-save-source">保存监控源</button>`,
    { draftKey, collectDraft: collectSource }
  );

  const clearBtn = document.getElementById("btn-clear-src-draft");
  if (clearBtn) {
    clearBtn.onclick = () => {
      delete state.drafts[draftKey];
      openSourceModal(sourceId);
    };
  }

  const renderProviderFields = () => {
    const cfg = perProviderCfg[selectedProvider] || (s?.provider === selectedProvider ? s.config : {}) || {};
    const nsVal = cfg._ns ?? (s?.provider === selectedProvider ? s.namespace_id : "");
    const wrap = document.getElementById("sf-dynamic");

    if (selectedProvider === "qiniu") {
      wrap.innerHTML = `
        <details class="help-details">
          <summary>❓ 小白指引：如何获取七牛云 AK / SK 和 Namespace ID？</summary>
          <ol>
            <li>登录七牛云控制台，点击右上角头像 →「密钥管理」，复制 <strong>AccessKey (AK)</strong> 和 <strong>SecretKey (SK)</strong>。</li>
            <li>左侧菜单进入「视频监控 QVS」→「空间管理」，复制对应空间的 <strong>空间 ID (Namespace ID)</strong>。</li>
          </ol>
        </details>
        <div class="field">
          <label>Namespace ID（空间 ID）</label>
          <input type="text" id="sf-ns" value="${esc(nsVal || "")}" placeholder="例如：2xenzw5o8..." />
        </div>
        <div class="field">
          <label>Access Key (AK)</label>
          <input type="text" id="sf-ak" value="${esc(cfg.access_key || "")}" placeholder="粘贴七牛云 Access Key" />
        </div>
        <div class="field">
          <label>Secret Key (SK)</label>
          <input type="password" id="sf-sk" value="${esc(cfg.secret_key || "")}" placeholder="${base ? "留空或保持星号则不修改原密钥" : "粘贴七牛云 Secret Key"}" />
        </div>`;
    } else if (selectedProvider === "tencent") {
      wrap.innerHTML = `
        <details class="help-details">
          <summary>❓ 小白指引：如何接入腾讯云视联 / IoT Video？</summary>
          <ol>
            <li>登录腾讯云控制台 →「访问管理 CAM」→「API 密钥管理」，获取 <strong>SecretId</strong> 和 <strong>SecretKey</strong>。</li>
            <li>系统内置标准 TC3-HMAC-SHA256 签名，默认调用视联接口 <code>iotvideoindustry.tencentcloudapi.com</code>（也支持修改为 <code>iotvideo.tencentcloudapi.com</code>）。</li>
          </ol>
        </details>
        <div class="form-row">
          <div class="field">
            <label>SecretId</label>
            <input type="text" id="sf-tc-id" value="${esc(cfg.secret_id || "")}" placeholder="AKID..." />
          </div>
          <div class="field">
            <label>SecretKey</label>
            <input type="password" id="sf-tc-key" value="${esc(cfg.secret_key || "")}" placeholder="${base ? "保持星号则不修改原密钥" : "粘贴 SecretKey"}" />
          </div>
        </div>
        <div class="form-row">
          <div class="field">
            <label>地域 Region</label>
            <input type="text" id="sf-tc-region" value="${esc(cfg.region || "ap-guangzhou")}" placeholder="ap-guangzhou" />
          </div>
          <div class="field">
            <label>分组 GroupId（选填）</label>
            <input type="text" id="sf-tc-group" value="${esc(nsVal || "")}" placeholder="留空查询全部设备" />
          </div>
        </div>
        <div class="form-row">
          <div class="field">
            <label>API 域名 Endpoint</label>
            <input type="text" id="sf-tc-ep" value="${esc(cfg.endpoint || "iotvideoindustry.tencentcloudapi.com")}" />
          </div>
          <div class="field">
            <label>Action / Version</label>
            <div style="display:flex;gap:6px">
              <input type="text" id="sf-tc-action" value="${esc(cfg.action || "DescribeAllDeviceList")}" />
              <input type="text" id="sf-tc-ver" value="${esc(cfg.api_version || "2020-12-01")}" style="max-width:110px" />
            </div>
          </div>
        </div>`;
    } else if (selectedProvider === "aliyun") {
      wrap.innerHTML = `
        <details class="help-details">
          <summary>❓ 小白指引：如何接入阿里云视频监控 VCS？</summary>
          <ol>
            <li>登录阿里云 RAM 控制台创建或复制 <strong>AccessKey ID</strong> 与 <strong>AccessKey Secret</strong>。</li>
            <li>填写对应区域接口域名（默认华东2上海 <code>vcs.cn-shanghai.aliyuncs.com</code>）及空间 CorpId（选填）。</li>
          </ol>
        </details>
        <div class="form-row">
          <div class="field">
            <label>AccessKey ID</label>
            <input type="text" id="sf-ali-ak" value="${esc(cfg.access_key_id || "")}" placeholder="LTAI..." />
          </div>
          <div class="field">
            <label>AccessKey Secret</label>
            <input type="password" id="sf-ali-sk" value="${esc(cfg.access_key_secret || "")}" placeholder="${base ? "保持星号则不修改原密钥" : "粘贴 AccessKey Secret"}" />
          </div>
        </div>
        <div class="form-row">
          <div class="field">
            <label>接口域名 Endpoint</label>
            <input type="text" id="sf-ali-ep" value="${esc(cfg.endpoint || "vcs.cn-shanghai.aliyuncs.com")}" />
          </div>
          <div class="field">
            <label>空间 CorpId（选填）</label>
            <input type="text" id="sf-ali-corp" value="${esc(nsVal || "")}" placeholder="留空按账号默认空间查询" />
          </div>
        </div>
        <div class="form-row">
          <div class="field"><label>接口 Action</label><input type="text" id="sf-ali-action" value="${esc(cfg.action || "ListDevices")}" /></div>
          <div class="field"><label>API Version</label><input type="text" id="sf-ali-ver" value="${esc(cfg.api_version || "2020-05-15")}" /></div>
        </div>`;
    } else if (selectedProvider === "custom") {
      wrap.innerHTML = `
        <div class="inline-alert info">
          <span>适配任意自建监控平台（如 WVP-PRO、ZLMediaKit、海康/大华网关）</span>
          <button type="button" class="link-btn" id="btn-fill-wvp">填充 WVP-PRO 示例</button>
        </div>
        <div class="form-row">
          <div class="field" style="grid-column:span 2">
            <label>设备列表接口 URL</label>
            <input type="text" id="sf-cu-url" value="${esc(cfg.url || "")}" placeholder="http://192.168.1.10:18080/api/device/query/devices?page=1&count=100" />
          </div>
        </div>
        <div class="form-row">
          <div class="field">
            <label>请求方法</label>
            <select id="sf-cu-method">
              <option value="GET" ${(cfg.method || "GET") === "GET" ? "selected" : ""}>GET</option>
              <option value="POST" ${cfg.method === "POST" ? "selected" : ""}>POST</option>
            </select>
          </div>
          <div class="field">
            <label>设备列表 JSON 路径（留空表示根节点）</label>
            <input type="text" id="sf-cu-path" value="${esc(cfg.items_path || "data.list")}" placeholder="例如：data.list 或 items" />
          </div>
        </div>
        <div class="form-row">
          <div class="field"><label>设备 ID 字段名</label><input type="text" id="sf-cu-id" value="${esc(cfg.id_field || "deviceId")}" /></div>
          <div class="field"><label>设备名称字段名</label><input type="text" id="sf-cu-name" value="${esc(cfg.name_field || "name")}" /></div>
        </div>
        <div class="form-row">
          <div class="field"><label>状态字段名</label><input type="text" id="sf-cu-state" value="${esc(cfg.state_field || "onLine")}" /></div>
          <div class="field"><label>代表“在线”的值（逗号分隔）</label><input type="text" id="sf-cu-online" value="${esc(cfg.online_values || "online,1,true,ON")}" /></div>
        </div>
        <div class="field">
          <label>自定义请求头 JSON（选填，例如鉴权 Token）</label>
          <textarea id="sf-cu-headers" rows="2" placeholder='{"Authorization": "Bearer your-token"}'>${esc(cfg.headers || "")}</textarea>
        </div>`;
      document.getElementById("btn-fill-wvp").onclick = () => {
        document.getElementById("sf-cu-path").value = "data.list";
        document.getElementById("sf-cu-id").value = "deviceId";
        document.getElementById("sf-cu-name").value = "name";
        document.getElementById("sf-cu-state").value = "onLine";
        document.getElementById("sf-cu-online").value = "true,1,online";
        toast("已填充 WVP-PRO 常用字段映射", "info");
      };
    } else {
      const initTotal = Math.max(1, Math.min(50, Number(cfg.demo_total_count ?? 4)));
      const initOff = Math.max(0, Math.min(initTotal, Number(cfg.demo_offline_count ?? 1)));
      wrap.innerHTML = `
        <div class="inline-alert info">演示模拟源会生成虚拟摄像头数据，无需云账号即可体验完整离线告警与恢复通知流程。</div>
        <div class="form-row">
          <div class="field">
            <label>模拟设备总数 N（1 ~ 50）</label>
            <input type="number" id="sf-demo-total" min="1" max="50" value="${initTotal}" />
          </div>
          <div class="field">
            <label>模拟离线数量（0 ~ <span id="sf-demo-max-label">${initTotal}</span>）</label>
            <input type="number" id="sf-demo-off" min="0" max="${initTotal}" value="${initOff}" />
          </div>
        </div>
        <div id="sf-demo-hint" class="field-hint">当前模拟：共 ${initTotal} 台设备（在线 ${initTotal - initOff} 台，离线 ${initOff} 台）。将离线数改为 0 可模拟设备恢复上线。</div>`;

      // 实时双向联动防呆：严格保证 1 <= N <= 50 且 0 <= offline <= N
      const totalInput = document.getElementById("sf-demo-total");
      const offInput = document.getElementById("sf-demo-off");
      const maxLbl = document.getElementById("sf-demo-max-label");
      const hintEl = document.getElementById("sf-demo-hint");
      const syncDemoBounds = (showClampNotice = false) => {
        let n = parseInt(totalInput.value, 10);
        if (isNaN(n)) n = 1;
        n = Math.max(1, Math.min(50, n));
        totalInput.value = String(n);

        offInput.max = String(n);
        maxLbl.textContent = String(n);

        let off = parseInt(offInput.value, 10);
        if (isNaN(off)) off = 0;
        let clamped = false;
        if (off > n) {
          off = n;
          clamped = true;
        }
        if (off < 0) {
          off = 0;
          clamped = true;
        }
        offInput.value = String(off);
        hintEl.textContent = clamped && showClampNotice
          ? `已自动调整：离线设备数不能超过总设备数 ${n}（当前：在线 ${n - off} 台，离线 ${off} 台）`
          : `当前模拟：共 ${n} 台设备（在线 ${n - off} 台，离线 ${off} 台）。将离线数改为 0 可模拟设备恢复上线。`;
      };
      totalInput.addEventListener("input", () => syncDemoBounds(true));
      totalInput.addEventListener("change", () => syncDemoBounds(true));
      offInput.addEventListener("input", () => syncDemoBounds(true));
      offInput.addEventListener("change", () => syncDemoBounds(true));
    }
  };

  renderProviderFields();
  document.querySelectorAll("[data-sp]").forEach((el) => {
    el.onclick = () => {
      snapshotCurrentProviderFields();
      selectedProvider = el.dataset.sp;
      document.querySelectorAll("[data-sp]").forEach((x) => x.classList.toggle("active", x === el));
      renderProviderFields();
      if (selectedProvider === "demo" && !document.getElementById("sf-name").value.trim()) {
        document.getElementById("sf-name").value = "演示模拟摄像头空间";
      }
    };
  });

  document.getElementById("btn-test-source-form").onclick = async () => {
    const resBox = document.getElementById("sf-test-result");
    resBox.className = "inline-alert info";
    resBox.textContent = "正在连接测试，请稍候...";
    try {
      const p = collectSource();
      if (base) p.channel_id = base.id; // 编辑态自动携带原 ID 补全脱敏密钥
      const res = await api("/api/source-channels/test", { method: "POST", body: p });
      resBox.className = `inline-alert ${res.ok ? "ok" : "error"}`;
      resBox.textContent = res.message;
    } catch (err) {
      resBox.className = "inline-alert error";
      resBox.textContent = err.message;
    }
  };

  document.getElementById("btn-save-source").onclick = async () => {
    const p = collectSource();
    if (!p.name) return toast("请填写监控源名称", "error");
    try {
      if (base) await api(`/api/source-channels/${base.id}`, { method: "PUT", body: p });
      else await api("/api/source-channels", { method: "POST", body: p });
      hideModal({ preserveDraft: false });
      toast(base ? "监控源已更新" : "监控源已添加", "ok");
      renderSources();
    } catch (err) {
      toast(err.message, "error");
    }
  };
};

window.testSavedSource = async function (id, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = "检测中...";
  try {
    const res = await api(`/api/source-channels/${id}/test`, { method: "POST" });
    renderSources();
    const rows = (res.devices || [])
      .map(
        (d) => `<tr>
        <td>${esc(d.name)}</td>
        <td><code>${esc(d.gb_id)}</code></td>
        <td><span class="badge ${d.state === "online" ? "badge-ok" : "badge-danger"}">${d.state === "online" ? "在线" : d.state}</span></td>
      </tr>`
      )
      .join("");
    openModal(
      "监控源连接测试与设备预览",
      `<div class="inline-alert ${res.ok ? "ok" : "error"}" style="margin-bottom:14px">${esc(res.message)}</div>
       ${
         rows
           ? `<div class="table-wrap"><table><thead><tr><th>设备名称</th><th>设备 ID</th><th>当前状态</th></tr></thead><tbody>${rows}</tbody></table></div>`
           : ""
       }`,
      `<button class="btn btn-primary" onclick="closeModal(true)">知道了</button>`
    );
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
};

window.deleteSource = async function (id, name) {
  if (!confirm(`确定要删除监控源「${name}」吗？`)) return;
  try {
    await api(`/api/source-channels/${id}`, { method: "DELETE" });
    toast("监控源已删除", "ok");
    renderSources();
  } catch (err) {
    toast(err.message, "error");
  }
};

// ==================== 页面 D：通知渠道 ====================

async function renderNotifications() {
  const list = await api("/api/notification-channels");
  state.notifications = list;
  const box = document.getElementById("notifications-list");
  if (!list.length) {
    box.innerHTML = `<div class="card empty-state" style="grid-column:1/-1">
      <div class="empty-icon">🔔</div>
      <div style="margin-bottom:12px">还没有配置通知渠道。支持钉钉、企业微信、飞书、NTFY 与通用 Webhook。</div>
      <button class="btn btn-primary" onclick="openNotifModal()">+ 添加通知渠道</button>
    </div>`;
    return;
  }

  box.innerHTML = list
    .map((n) => {
      const testBadge =
        n.last_test_status === "ok"
          ? `<span class="badge badge-ok">测试通过</span>`
          : n.last_test_status === "failed"
          ? `<span class="badge badge-danger">推送失败</span>`
          : `<span class="badge badge-muted">未测试</span>`;
      const target = n.type === "ntfy" ? `${n.config.server || "https://ntfy.sh"}/${n.config.topic || ""}` : n.config.url || "—";
      return `
      <div class="item-card">
        <div class="item-head">
          <div>
            <h4 class="item-title">${esc(n.name)}</h4>
            <div style="margin-top:6px">
              <span class="badge badge-primary">${NOTIF_LABELS[n.type] || n.type}</span>
              ${testBadge}
            </div>
          </div>
        </div>
        <div class="item-meta">
          <div style="word-break:break-all">目标地址：<code>${esc(target)}</code></div>
          ${n.last_test_message ? `<div>最近测试：${esc(n.last_test_message)}</div>` : ""}
        </div>
        <div class="item-actions">
          <button class="btn btn-primary btn-sm" onclick="testSavedNotif(${n.id}, this)">📨 发送测试消息</button>
          <button class="btn btn-secondary btn-sm" onclick="openNotifModal(${n.id})">编辑</button>
          <button class="btn btn-danger btn-sm" onclick="deleteNotif(${n.id}, '${esc(n.name)}')">删除</button>
        </div>
      </div>`;
    })
    .join("");
}

document.getElementById("btn-add-notif").onclick = () => openNotifModal();

window.openNotifModal = function (notifId = null) {
  const draftKey = notifId ? `notif_edit_${notifId}` : "notif_new";
  const savedDraft = state.drafts[draftKey];
  const base = notifId ? state.notifications.find((x) => x.id === notifId) : null;
  const n = savedDraft || base;
  let selectedType = n?.type || "dingtalk";
  const perTypeCfg = {};
  if (n?.type && n?.config) perTypeCfg[n.type] = { ...n.config };

  const platforms = [
    ["dingtalk", "钉钉机器人"],
    ["wecom", "企业微信"],
    ["feishu", "飞书机器人"],
    ["ntfy", "NTFY 推送"],
    ["webhook", "自定义 Webhook"],
  ];

  const draftNotice = savedDraft
    ? `<div class="inline-alert info"><span>📝 已为您恢复上次未保存的草稿</span><button type="button" class="link-btn" id="btn-clear-nf-draft">清空草稿</button></div>`
    : "";

  const body = `
    <div class="form-stack">
      ${draftNotice}
      <div class="field">
        <label>渠道名称</label>
        <input type="text" id="nf-name" value="${esc(n?.name || "")}" placeholder="例如：运维值班钉钉群" />
      </div>
      <div class="field">
        <label>选择通知平台</label>
        <div class="platform-grid">
          ${platforms
            .map(([k, lbl]) => `<div class="platform-opt ${selectedType === k ? "active" : ""}" data-nt="${k}">${lbl}</div>`)
            .join("")}
        </div>
      </div>
      <div id="nf-dynamic" class="form-stack"></div>
      <div id="nf-test-result" class="inline-alert hidden"></div>
    </div>
  `;

  const snapshotCurrentType = () => {
    const config = {};
    if (selectedType === "ntfy") {
      config.server = document.getElementById("nf-server")?.value.trim() || "https://ntfy.sh";
      config.topic = document.getElementById("nf-topic")?.value.trim() || "";
      config.token = document.getElementById("nf-token")?.value.trim() || "";
    } else {
      config.url = document.getElementById("nf-url")?.value.trim() || "";
      if (document.getElementById("nf-secret")) config.secret = document.getElementById("nf-secret").value.trim();
      if (document.getElementById("nf-keyword")) config.keyword = document.getElementById("nf-keyword").value.trim();
      if (document.getElementById("nf-body")) config.custom_body = document.getElementById("nf-body").value.trim();
    }
    perTypeCfg[selectedType] = config;
    return config;
  };

  const collectNotif = () => ({
    name: document.getElementById("nf-name").value.trim() || NOTIF_LABELS[selectedType],
    type: selectedType,
    config: { ...snapshotCurrentType() },
    is_active: true,
  });

  openModal(
    base ? "编辑通知渠道" : "添加通知渠道",
    body,
    `<button class="btn btn-secondary" onclick="closeModal(true)">取消</button>
     <button class="btn btn-secondary" id="btn-test-notif-form">📨 发送测试消息</button>
     <button class="btn btn-primary" id="btn-save-notif">保存渠道</button>`,
    { draftKey, collectDraft: collectNotif }
  );

  const clearBtn = document.getElementById("btn-clear-nf-draft");
  if (clearBtn) {
    clearBtn.onclick = () => {
      delete state.drafts[draftKey];
      openNotifModal(notifId);
    };
  }

  const renderFields = () => {
    const cfg = perTypeCfg[selectedType] || (n?.type === selectedType ? n.config : {}) || {};
    const wrap = document.getElementById("nf-dynamic");
    if (selectedType === "dingtalk") {
      wrap.innerHTML = `
        <div class="field">
          <label>钉钉机器人 Webhook 地址</label>
          <input type="text" id="nf-url" value="${esc(cfg.url || "")}" placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
        </div>
        <div class="form-row">
          <div class="field">
            <label>加签密钥 Secret（选填，SEC开头）</label>
            <input type="password" id="nf-secret" value="${esc(cfg.secret || "")}" placeholder="使用加签安全设置时填写" />
          </div>
          <div class="field">
            <label>自定义关键词（选填）</label>
            <input type="text" id="nf-keyword" value="${esc(cfg.keyword || "")}" placeholder="如：告警、监控" />
          </div>
        </div>`;
    } else if (selectedType === "wecom") {
      wrap.innerHTML = `
        <div class="field">
          <label>企业微信群机器人 Webhook 地址</label>
          <input type="text" id="nf-url" value="${esc(cfg.url || "")}" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
        </div>`;
    } else if (selectedType === "feishu") {
      wrap.innerHTML = `
        <div class="field">
          <label>飞书自定义机器人 Webhook 地址</label>
          <input type="text" id="nf-url" value="${esc(cfg.url || "")}" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." />
        </div>
        <div class="field">
          <label>签名校验密钥（选填）</label>
          <input type="password" id="nf-secret" value="${esc(cfg.secret || "")}" placeholder="若飞书开启了签名校验请填写" />
        </div>`;
    } else if (selectedType === "ntfy") {
      wrap.innerHTML = `
        <div class="form-row">
          <div class="field">
            <label>NTFY 服务器地址</label>
            <input type="text" id="nf-server" value="${esc(cfg.server || "https://ntfy.sh")}" placeholder="https://ntfy.sh" />
          </div>
          <div class="field">
            <label>订阅主题 Topic（必填）</label>
            <input type="text" id="nf-topic" value="${esc(cfg.topic || "")}" placeholder="例如：my-qvs-alerts-2026" />
          </div>
        </div>
        <div class="field">
          <label>访问令牌 Token（选填，私有服务器用）</label>
          <input type="password" id="nf-token" value="${esc(cfg.token || "")}" placeholder="留空表示公开主题" />
        </div>`;
    } else {
      wrap.innerHTML = `
        <div class="field">
          <label>Webhook URL</label>
          <input type="text" id="nf-url" value="${esc(cfg.url || "")}" placeholder="https://example.com/hook" />
        </div>
        <div class="field">
          <label>自定义 JSON 请求体模板（选填，支持 {title} {message} {timestamp}）</label>
          <textarea id="nf-body" rows="4" placeholder='{"title":"{title}","text":"{message}"}'>${esc(cfg.custom_body || "")}</textarea>
        </div>`;
    }
  };

  renderFields();
  document.querySelectorAll("[data-nt]").forEach((el) => {
    el.onclick = () => {
      snapshotCurrentType();
      selectedType = el.dataset.nt;
      document.querySelectorAll("[data-nt]").forEach((x) => x.classList.toggle("active", x === el));
      renderFields();
    };
  });

  document.getElementById("btn-test-notif-form").onclick = async () => {
    const box = document.getElementById("nf-test-result");
    const p = collectNotif();
    if (p.type === "ntfy" && !p.config.topic) {
      box.className = "inline-alert error";
      box.textContent = "请先填写 NTFY 订阅主题 (Topic) 后再测试。";
      return;
    }
    if (p.type !== "ntfy" && !p.config.url) {
      box.className = "inline-alert error";
      box.textContent = "请先填写 Webhook 地址后再测试。";
      return;
    }
    if (base) p.channel_id = base.id;
    box.className = "inline-alert info";
    box.textContent = "正在发送测试通知...";
    try {
      const res = await api("/api/notification-channels/test", { method: "POST", body: p });
      box.className = `inline-alert ${res.ok ? "ok" : "error"}`;
      box.textContent = res.message;
    } catch (err) {
      box.className = "inline-alert error";
      box.textContent = err.message;
    }
  };

  document.getElementById("btn-save-notif").onclick = async () => {
    const p = collectNotif();
    try {
      if (base) await api(`/api/notification-channels/${base.id}`, { method: "PUT", body: p });
      else await api("/api/notification-channels", { method: "POST", body: p });
      hideModal({ preserveDraft: false });
      toast(base ? "通知渠道已更新" : "通知渠道已添加", "ok");
      renderNotifications();
    } catch (err) {
      toast(err.message, "error");
    }
  };
};

window.testSavedNotif = async function (id, btn) {
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = "发送中...";
  try {
    const res = await api(`/api/notification-channels/${id}/test`, { method: "POST" });
    toast(res.message, res.ok ? "ok" : "error");
    renderNotifications();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
};

window.deleteNotif = async function (id, name) {
  if (!confirm(`确定要删除通知渠道「${name}」吗？引用它的任务会自动解除绑定。`)) return;
  try {
    const res = await api(`/api/notification-channels/${id}`, { method: "DELETE" });
    toast(res.message || "通知渠道已删除", "ok");
    renderNotifications();
  } catch (err) {
    toast(err.message, "error");
  }
};

// ==================== 页面 E：日志中心 ====================

document.querySelectorAll("[data-log-tab]").forEach((btn) => {
  btn.onclick = () => {
    state.logTab = btn.dataset.logTab;
    document.querySelectorAll("[data-log-tab]").forEach((b) => b.classList.toggle("active", b === btn));
    renderLogs();
  };
});
document.getElementById("log-status-filter").onchange = () => renderLogs();
document.getElementById("btn-cleanup-logs").onclick = async () => {
  if (!confirm("确定清理 30 天前的历史日志吗？")) return;
  try {
    const res = await api("/api/logs/cleanup?retention_days=30", { method: "POST" });
    toast(res.message, "ok");
    renderLogs();
  } catch (err) {
    toast(err.message, "error");
  }
};

async function renderLogs() {
  const filterVal = document.getElementById("log-status-filter").value;
  const container = document.getElementById("logs-table-container");
  if (state.logTab === "tasks") {
    const qs = filterVal ? `?status=${encodeURIComponent(filterVal)}&limit=80` : "?limit=80";
    const rows = await api(`/api/logs/tasks${qs}`);
    if (!rows.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📋</div><div>暂无匹配的巡检任务日志</div></div>`;
      return;
    }
    container.innerHTML = `<table>
      <thead><tr><th>时间</th><th>任务名称</th><th>触发</th><th>状态</th><th>在线 / 离线</th><th>发送通知</th><th>结果摘要</th><th>耗时</th></tr></thead>
      <tbody>
        ${rows
          .map((r) => {
            const cls = r.status === "success" ? "badge-ok" : r.status === "failed" ? "badge-danger" : "badge-warn";
            return `<tr>
              <td style="white-space:nowrap">${fmtTime(r.started_at)}</td>
              <td><strong>${esc(r.task_name)}</strong></td>
              <td>${r.trigger_type === "manual" ? "手动" : "定时"}</td>
              <td><span class="badge ${cls}">${esc(r.status)}</span></td>
              <td>${r.online_count} / <strong style="color:${r.offline_count > 0 ? "var(--danger)" : "inherit"}">${r.offline_count}</strong></td>
              <td>${r.alert_sent_count}</td>
              <td>${esc(r.message)}</td>
              <td>${r.duration_ms} ms</td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
  } else {
    const mappedStatus = filterVal === "success" ? "sent" : filterVal;
    const qs = mappedStatus ? `?status=${encodeURIComponent(mappedStatus)}&limit=80` : "?limit=80";
    const rows = await api(`/api/logs/notifications${qs}`);
    if (!rows.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📨</div><div>暂无匹配的通知发送记录</div></div>`;
      return;
    }
    container.innerHTML = `<table>
      <thead><tr><th>时间</th><th>通知渠道</th><th>类型</th><th>状态</th><th>标题</th><th>备注/报错</th></tr></thead>
      <tbody>
        ${rows
          .map((r) => {
            const cls = r.status === "sent" ? "badge-ok" : r.status === "failed" ? "badge-danger" : "badge-warn";
            const txt = r.status === "sent" ? "已送达" : r.status === "failed" ? "失败" : "已静默";
            return `<tr>
              <td style="white-space:nowrap">${fmtTime(r.created_at)}</td>
              <td><strong>${esc(r.channel_name)}</strong></td>
              <td>${esc(NOTIF_LABELS[r.channel_type] || r.channel_type)}</td>
              <td><span class="badge ${cls}">${txt}</span></td>
              <td>${esc(r.title)}</td>
              <td>${esc(r.error_detail || "正常送达")}</td>
            </tr>`;
          })
          .join("")}
      </tbody>
    </table>`;
  }
}

// ==================== 页面 F：系统自愈与设置 ====================

async function renderSettings() {
  const report = await api("/api/system/health-report");
  const { db_health, scheduler, self_heal_events } = report;
  document.getElementById("health-summary").innerHTML = `
    <div class="kv-box"><div class="kv-k">后台调度器</div><div class="kv-v">${scheduler.running ? "✅ 运行中" : "❌ 已停止"}（自动重启 ${scheduler.restart_count} 次）</div></div>
    <div class="kv-box"><div class="kv-k">最近心跳</div><div class="kv-v">${fmtTime(scheduler.last_heartbeat)}</div></div>
    <div class="kv-box"><div class="kv-k">配置库 data.db</div><div class="kv-v">${db_health.data_db_ok ? "✅ 完整" : "❌ 异常"}（${db_health.data_db_size_kb} KB · ${esc(db_health.journal_mode)}）</div></div>
    <div class="kv-box"><div class="kv-k">日志库 logs.db / 剩余空间</div><div class="kv-v">${db_health.logs_db_ok ? "✅ 完整" : "❌ 异常"}（${db_health.logs_db_size_kb} KB · 剩余 ${db_health.disk_free_mb} MB）</div></div>
  `;

  const evBox = document.getElementById("self-heal-events");
  evBox.innerHTML = self_heal_events.length
    ? self_heal_events
        .map(
          (e) => `<div class="timeline-item">
          <div class="timeline-top"><strong>${esc(e.event_type)}</strong><span class="timeline-time">${fmtTime(e.created_at)}</span></div>
          <div>${esc(e.description)}</div>
        </div>`
        )
        .join("")
    : `<div class="empty-state">系统运行平稳，暂无异常自愈事件。</div>`;

  if (state.user?.role === "admin") {
    const users = await api("/api/users");
    document.getElementById("users-list").innerHTML = `<table>
      <thead><tr><th>用户名</th><th>角色</th><th>操作</th></tr></thead>
      <tbody>
        ${users
          .map(
            (u) => `<tr>
            <td><strong>${esc(u.username)}</strong> ${u.is_first_admin ? '<span class="badge badge-primary">初始管理员</span>' : ""}</td>
            <td>${u.role === "admin" ? "管理员" : "成员"}</td>
            <td>${u.is_first_admin || u.id === state.user.id ? "—" : `<button class="btn btn-danger btn-sm" onclick="deleteUser(${u.id}, '${esc(u.username)}')">删除</button>`}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
  }
}

document.getElementById("btn-sched-restart").onclick = async () => {
  try {
    const res = await api("/api/scheduler/control", { method: "POST", body: { action: "restart" } });
    toast(res.message, "ok");
    renderSettings();
  } catch (err) {
    toast(err.message, "error");
  }
};

async function downloadBackup(includeSecrets) {
  try {
    const snap = await api(`/api/system/backup?include_secrets=${includeSecrets}`);
    const blob = new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `qvs-backup-${includeSecrets ? "full" : "safe"}-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast("配置备份文件已开始下载", "ok");
  } catch (err) {
    toast(err.message, "error");
  }
}

document.getElementById("btn-backup-safe").onclick = () => downloadBackup(false);
document.getElementById("btn-backup-full").onclick = () => {
  if (confirm("完整备份包含您的云服务与机器人密钥明文，请务必妥善保管。是否继续下载？")) {
    downloadBackup(true);
  }
};

document.getElementById("input-restore-file").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const snapshot = JSON.parse(text);
    const res = await api("/api/system/restore", { method: "POST", body: { snapshot } });
    toast(res.message, "ok");
    renderSettings();
  } catch (err) {
    toast(`导入失败：${err.message}`, "error");
  } finally {
    e.target.value = "";
  }
};

document.getElementById("change-pwd-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/api/auth/change-password", {
      method: "POST",
      body: {
        old_password: document.getElementById("cp-old").value,
        new_password: document.getElementById("cp-new").value,
      },
    });
    document.getElementById("cp-old").value = "";
    document.getElementById("cp-new").value = "";
    toast("密码修改成功", "ok");
  } catch (err) {
    toast(err.message, "error");
  }
};

document.getElementById("btn-add-user").onclick = () => {
  const draftKey = "user_new";
  const d = state.drafts[draftKey] || {};
  openModal(
    "新建账号",
    `<div class="form-stack">
      <div class="field"><label>用户名</label><input type="text" id="nu-name" minlength="3" value="${esc(d.username || "")}" /></div>
      <div class="field"><label>初始密码（至少 6 位）</label><input type="password" id="nu-pwd" minlength="6" value="${esc(d.password || "")}" /></div>
      <div class="field"><label>角色</label><select id="nu-role"><option value="user" ${d.role === "user" ? "selected" : ""}>普通成员</option><option value="admin" ${d.role === "admin" ? "selected" : ""}>管理员</option></select></div>
    </div>`,
    `<button class="btn btn-secondary" onclick="closeModal(true)">取消</button>
     <button class="btn btn-primary" id="btn-save-new-user">创建</button>`,
    {
      draftKey,
      collectDraft: () => ({
        username: document.getElementById("nu-name").value.trim(),
        password: document.getElementById("nu-pwd").value,
        role: document.getElementById("nu-role").value,
      }),
    }
  );
  document.getElementById("btn-save-new-user").onclick = async () => {
    try {
      await api("/api/users", {
        method: "POST",
        body: {
          username: document.getElementById("nu-name").value.trim(),
          password: document.getElementById("nu-pwd").value,
          role: document.getElementById("nu-role").value,
        },
      });
      hideModal({ preserveDraft: false });
      toast("账号创建成功", "ok");
      renderSettings();
    } catch (err) {
      toast(err.message, "error");
    }
  };
};

window.deleteUser = async function (id, name) {
  if (!confirm(`确定删除账号「${name}」吗？`)) return;
  try {
    await api(`/api/users/${id}`, { method: "DELETE" });
    toast("账号已删除", "ok");
    renderSettings();
  } catch (err) {
    toast(err.message, "error");
  }
};

boot();
