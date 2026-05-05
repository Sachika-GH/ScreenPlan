// ScreenPlan Web UI — SPA Application
const API = `${location.protocol}//${location.host}/api`;
let AUTH = { token: '', userId: 0, displayName: '', email: '' };

// ─── Theme ──────────────────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('screenplan_theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem('screenplan_theme')) {
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
  });
})();

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('screenplan_theme', next);
}

document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

// ─── Helpers ───────────────────────────────────────────
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function api(url, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (AUTH.token) headers['Authorization'] = `Bearer ${AUTH.token}`;
  return fetch(API + url, { ...opts, headers }).then(r => {
    if (!r.ok) return r.json().then(e => { throw new Error(e.error || r.statusText); });
    return r.json();
  });
}
function fmtTime(iso) {
  // Parse with Asia/Shanghai timezone if no timezone present
  const d = parseTz(iso);
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}
function fmtDate(iso) { return iso?.split('T')[0] || ''; }
function fmtMinutes(m) { return m >= 60 ? `${(m/60).toFixed(1)}h` : `${m}min`; }
function escHtml(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

// Parse ISO timestamp assuming Asia/Shanghai if no timezone given
function parseTz(iso) {
  if (!iso) return new Date();
  if (iso.includes('+') || iso.includes('Z') || iso.endsWith('z')) return new Date(iso);
  return new Date(iso + '+08:00');
}

// Platform icon map
const PLATFORM_ICONS = { macos: '&#9000;', windows: '&#9634;', ios: '&#9743;', android: '&#128241;', linux: '&#128187;' };

// ─── Auth ──────────────────────────────────────────────
$('#login-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    const r = await api('/auth/login', { method: 'POST', body: JSON.stringify({
      email: $('#login-email').value, password: $('#login-password').value
    })});
    setAuth(r);
  } catch (err) { $('#login-error').textContent = err.message; }
});

$('#register-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    const r = await api('/auth/register', { method: 'POST', body: JSON.stringify({
      family_name: $('#reg-family').value,
      display_name: $('#reg-display').value,
      email: $('#reg-email').value,
      password: $('#reg-password').value,
    })});
    setAuth(r);
  } catch (err) { $('#reg-error').textContent = err.message; }
});

function setAuth(data) {
  AUTH = { token: data.access_token, userId: data.user_id, displayName: data.display_name, email: '' };
  $('#user-name').textContent = AUTH.displayName;
  $('#login-page').classList.remove('active');
  $('#main-page').classList.add('active');
  sessionStorage.setItem('screenplan_token', data.access_token);
  sessionStorage.setItem('screenplan_user', JSON.stringify({ userId: data.user_id, displayName: data.display_name }));
  loadDashboard();
}
$('#logout-btn').addEventListener('click', () => {
  AUTH = { token: '', userId: 0, displayName: '' };
  sessionStorage.clear();
  $('#main-page').classList.remove('active');
  $('#login-page').classList.add('active');
});

// ─── Tabs ──────────────────────────────────────────────
$$('#login-tabs .tab').forEach(t => t.addEventListener('click', () => {
  $$('#login-tabs .tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  $$('.auth-form').forEach(f => f.classList.remove('active'));
  $(`#${t.dataset.tab}`).classList.add('active');
  $('#login-error').textContent = '';
  $('#reg-error').textContent = '';
}));

// ─── Navigation ────────────────────────────────────────
$$('.nav-link').forEach(l => l.addEventListener('click', e => {
  e.preventDefault();
  $$('.nav-link').forEach(x => x.classList.remove('active'));
  l.classList.add('active');
  $$('.content').forEach(c => c.classList.remove('active'));
  $(`#page-${l.dataset.page}`).classList.add('active');
  const loaders = { dashboard: loadDashboard, timeline: loadTimeline, devices: loadDevices, schedule: loadSchedule, friends: loadFriends };
  if (loaders[l.dataset.page]) loaders[l.dataset.page]();
}));

// ─── Login persistence ─────────────────────────────────
(function() {
  const tok = sessionStorage.getItem('screenplan_token');
  const usr = JSON.parse(sessionStorage.getItem('screenplan_user') || 'null');
  if (tok && usr) {
    AUTH = { token: tok, userId: usr.userId, displayName: usr.displayName };
    $('#user-name').textContent = AUTH.displayName;
    $('#login-page').classList.remove('active');
    $('#main-page').classList.add('active');
    loadDashboard();
  }
})();

// ═══════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════

async function loadDashboard() {
  try {
    const summary = await api('/usage/summary');
    renderSummary(summary);
    renderDeviceCards(summary);
  } catch (e) { console.error(e); }
}

function renderSummary(s) {
  const total = s.total_minutes_all_devices || 0;
  const devCount = s.devices?.length || 0;
  const overlap = s.overlap_minutes || 0;
  let lPct = 0, ePct = 0;
  if (s.devices?.length) {
    const tl = s.devices.reduce((a,d) => a + d.total_minutes, 0) || 1;
    s.devices.forEach(d => {
      lPct += (d.learning_pct || 0) * (d.total_minutes / tl);
      ePct += (d.entertainment_pct || 0) * (d.total_minutes / tl);
    });
  }

  let overlayHtml = '';
  if (overlap > 0) {
    overlayHtml = `<div class="card">
      <div class="label">重叠时间</div>
      <div class="value" style="color:#2563EB">${overlap.toFixed(0)}<span>min</span></div>
      <div class="sub">多设备同时使用</div>
      <div class="accent-line blue-light"></div>
    </div>`;
  }

  $('#dashboard-summary').innerHTML = `
    <div class="card">
      <div class="label">设备数</div>
      <div class="value">${devCount}</div>
      <div class="accent-line blue"></div>
    </div>
    <div class="card">
      <div class="label">总使用时间</div>
      <div class="value">${(total/60).toFixed(1)}<span> h</span></div>
      <div class="accent-line blue"></div>
    </div>
    ${overlayHtml}
    <div class="card">
      <div class="label">学习占比</div>
      <div class="value" style="color:#2563EB">${lPct.toFixed(0)}<span>%</span></div>
      <div class="sub">娱乐 ${ePct.toFixed(0)}%</div>
      <div class="accent-line blue"></div>
    </div>
  `;
}

function renderDeviceCards(s) {
  $('#dashboard-devices').innerHTML = (s.devices || []).map(d => `
    <div class="device-card">
      <div class="device-header">
        <span class="device-name">
          <span>${PLATFORM_ICONS[d.platform] || '&#9673;'}</span>
          ${escHtml(d.device_name)}
        </span>
        <span class="platform-badge">${d.platform}</span>
      </div>
      <div class="device-bar">
        <div class="learning" style="width:${d.learning_pct||0}%"></div>
        <div class="entertainment" style="width:${d.entertainment_pct||0}%"></div>
        <div class="other" style="width:${d.other_pct||0}%"></div>
      </div>
      <div style="font-size:13px;color:#64748B;margin-bottom:8px">
        ${d.total_minutes} 分钟 &middot; 最长专注 ${d.longest_focus_minutes}min
      </div>
      <div class="top-apps">${(d.top_apps||[]).slice(0,5).map(a => `
        <div class="app-row"><span class="app-name">${escHtml(a.app_name)}</span><span>${a.total_minutes}min</span></div>
      `).join('')}</div>
    </div>
  `).join('') || `
    <div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:#94A3B8">
      <div style="font-size:36px;margin-bottom:12px;opacity:0.4">&#9673;</div>
      <div style="font-size:15px;font-weight:500">暂无设备数据</div>
      <div style="font-size:13px;margin-top:4px">请在设备上运行 ScreenPlan Agent 开始采集</div>
    </div>`;
}

// ═══════════════════════════════════════════════════════
// Timeline
// ═══════════════════════════════════════════════════════

const ZOOM_LEVELS = [3, 6, 12, 24];
let currentZoomIdx = 3; // default: 24h
let timelineDate = '';

$('#timeline-date').value = new Date().toISOString().split('T')[0];
$('#timeline-refresh').addEventListener('click', loadTimeline);

// Date navigation
$('#date-prev').addEventListener('click', () => navigateDay(-1));
$('#date-next').addEventListener('click', () => navigateDay(1));

// Zoom controls
$('#zoom-in').addEventListener('click', () => changeZoom(-1));
$('#zoom-out').addEventListener('click', () => changeZoom(1));
$('#zoom-now').addEventListener('click', scrollToNow);

function changeZoom(delta) {
  currentZoomIdx = Math.max(0, Math.min(ZOOM_LEVELS.length - 1, currentZoomIdx + delta));
  updateZoomUI();
  if (timelineDate) loadTimeline();
}

function updateZoomUI() {
  $('#zoom-label').textContent = ZOOM_LEVELS[currentZoomIdx] + 'h';
  $('#zoom-in').disabled = currentZoomIdx === 0;
  $('#zoom-out').disabled = currentZoomIdx === ZOOM_LEVELS.length - 1;
  $('#zoom-now').style.display = currentZoomIdx < 3 ? 'flex' : 'none';
}

function scrollToNow() {
  const body = document.querySelector('.timeline-chart-body');
  if (!body) return;
  const now = new Date();
  const nowHour = now.getHours() + now.getMinutes() / 60;
  const zoomHours = ZOOM_LEVELS[currentZoomIdx];
  const totalWidth = body.scrollWidth - body.clientWidth;
  const targetHour = Math.max(0, nowHour - zoomHours / 2);
  const maxHour = 24 - zoomHours;
  const clamped = Math.max(0, Math.min(maxHour, targetHour));
  body.scrollLeft = (clamped / (24 - zoomHours)) * totalWidth;
}

function navigateDay(delta) {
  const input = $('#timeline-date');
  const d = new Date(input.value + 'T00:00:00');
  if (isNaN(d.getTime())) return;
  d.setDate(d.getDate() + delta);
  input.value = d.toISOString().split('T')[0];
  loadTimeline();
}

async function loadTimeline() {
  const date = $('#timeline-date').value;
  timelineDate = date;
  updateZoomUI();
  try {
    const data = await api('/usage/timeline/full?date=' + date);
    renderTimeline(data, date);
  } catch (e) {
    $('#timeline-summary').innerHTML = '';
    $('#timeline-chart-wrap').innerHTML = `
      <div class="timeline-empty">
        <div class="empty-icon">&#9888;</div>
        <div class="empty-title">加载失败</div>
        <div class="empty-desc">${escHtml(e.message)}</div>
      </div>`;
  }
}

// Merge consecutive events of the same category
function mergeTimelineEvents(events) {
  if (!events || !events.length) return [];
  const sorted = [...events].sort((a,b) => parseTz(a.timestamp) - parseTz(b.timestamp));
  const merged = [];
  const MERGE_GAP_MIN = 4; // merge if gap <= 4 minutes

  let current = {
    start: sorted[0].timestamp,
    end: sorted[0].timestamp,
    category: sorted[0].category,
    apps: [sorted[0].app_name]
  };

  for (let i = 1; i < sorted.length; i++) {
    const evt = sorted[i];
    const prevEnd = parseTz(current.end);
    const thisStart = parseTz(evt.timestamp);
    const gapMin = (thisStart - prevEnd) / 60000;

    if (evt.category === current.category && gapMin <= MERGE_GAP_MIN) {
      current.end = evt.timestamp;
      if (!current.apps.includes(evt.app_name)) {
        current.apps.push(evt.app_name);
      }
    } else {
      merged.push(current);
      current = {
        start: evt.timestamp,
        end: evt.timestamp,
        category: evt.category,
        apps: [evt.app_name]
      };
    }
  }
  merged.push(current);
  return merged;
}

// Per-app color palette for unique identification
const APP_COLORS = [
  '#3B82F6', '#8B5CF6', '#EC4899', '#F59E0B', '#22C55E',
  '#06B6D4', '#EF4444', '#F97316', '#14B8A6', '#6366F1',
  '#84CC16', '#0EA5E9', '#D946EF', '#EAB308', '#10B981'
];

function getAppColor(appName, index) {
  let hash = 0;
  for (let i = 0; i < appName.length; i++) {
    hash = ((hash << 5) - hash) + appName.charCodeAt(i);
    hash |= 0;
  }
  return APP_COLORS[Math.abs(hash) % APP_COLORS.length];
}

function computeDeviceStats(events) {
  if (!events || !events.length) return { total: 0, learning: 0, entertainment: 0, other: 0, appCount: 0 };
  const cats = { learning: 0, entertainment: 0, other: 0 };
  const appSet = new Set();
  let firstTs = null, lastTs = null;

  events.forEach(evt => {
    cats[evt.category] = (cats[evt.category] || 0) + 1;
    appSet.add(evt.app_name);
    if (!firstTs || evt.timestamp < firstTs) firstTs = evt.timestamp;
    if (!lastTs || evt.timestamp > lastTs) lastTs = evt.timestamp;
  });

  const total = cats.learning + cats.entertainment + cats.other;
  const gapMinutes = firstTs && lastTs
    ? Math.max(0, (parseTz(lastTs) - parseTz(firstTs)) / 60000)
    : 0;

  return {
    total: total * 3, // ~3 min per record
    learning: cats.learning,
    entertainment: cats.entertainment,
    other: cats.other,
    appCount: appSet.size,
    spanMinutes: gapMinutes
  };
}

function renderTimeline(data, date) {
  const devices = data.devices || [];
  const zoomHours = ZOOM_LEVELS[currentZoomIdx];
  const isZoomed = zoomHours < 24;
  // Scale factor: how many px per hour relative to the 24h view
  // Base: 24h occupies 100% of container. Zoomed: zoomHours occupies 100%.
  const scale = 24 / zoomHours;

  // Show/hide legend
  const legend = $('#timeline-legend');
  legend.style.display = devices.length ? 'flex' : 'none';

  if (!devices.length) {
    $('#timeline-summary').innerHTML = '';
    $('#timeline-chart-wrap').innerHTML = `
      <div class="timeline-empty">
        <div class="empty-icon">&#9716;</div>
        <div class="empty-title">当日暂无活动数据</div>
        <div class="empty-desc">${date} — 等待设备上报使用记录</div>
      </div>`;
    return;
  }

  // Render per-device summary cards
  let summaryHtml = '';
  for (const dev of devices) {
    const stats = computeDeviceStats(dev.events || []);
    const total = stats.total;
    const lPct = total > 0 ? (stats.learning * 100 / (stats.learning + stats.entertainment + stats.other)) : 0;
    const ePct = total > 0 ? (stats.entertainment * 100 / (stats.learning + stats.entertainment + stats.other)) : 0;
    const oPct = total > 0 ? (stats.other * 100 / (stats.learning + stats.entertainment + stats.other)) : 0;
    const icon = PLATFORM_ICONS[dev.platform] || '&#9673;';

    summaryHtml += `
      <div class="timeline-device-card">
        <div class="tdc-header">
          <div class="tdc-icon">${icon}</div>
          <div>
            <div class="tdc-name">${escHtml(dev.device_name)}</div>
            <div class="tdc-platform">${dev.platform}</div>
          </div>
        </div>
        <div class="tdc-stats">
          <div class="tdc-stat">
            <span class="tdc-stat-val">${fmtMinutes(total)}</span>
            <span class="tdc-stat-lbl">总时长</span>
          </div>
          <div class="tdc-stat">
            <span class="tdc-stat-val">${stats.appCount}</span>
            <span class="tdc-stat-lbl">应用数</span>
          </div>
          <div class="tdc-stat">
            <span class="tdc-stat-val">${Math.round(lPct)}%</span>
            <span class="tdc-stat-lbl">学习占比</span>
          </div>
        </div>
        <div class="tdc-bar">
          <div class="learning" style="width:${lPct}%"></div>
          <div class="entertainment" style="width:${ePct}%"></div>
          <div class="other" style="width:${oPct}%"></div>
        </div>
      </div>`;
  }
  $('#timeline-summary').innerHTML = summaryHtml;

  // Build the swimlane chart
  const TOTAL_HOURS = 24;
  let chartHtml = '';

  // Header with time axis — ticks cover full 24h scaled
  chartHtml += '<div class="timeline-chart-header">';
  chartHtml += '<div class="timeline-label">设备</div>';
  chartHtml += `<div class="timeline-axis" style="min-width:${scale * 600}px">`;
  for (let h = 0; h <= TOTAL_HOURS; h++) {
    const pct = (h / TOTAL_HOURS * 100);
    const isMajor = h % (zoomHours <= 6 ? zoomHours : 3) === 0;
    chartHtml += `<div class="tick ${isMajor ? 'major' : 'minor'}" style="left:${pct}%"></div>`;
    if (isMajor) {
      chartHtml += `<div class="tick-label" style="left:${pct}%">${String(h).padStart(2,'0')}:00</div>`;
    }
  }
  chartHtml += '</div></div>';

  // Device rows
  chartHtml += '<div class="timeline-chart-body">';

  // Is viewing today? Show "now" marker
  const today = new Date().toISOString().split('T')[0];
  const isToday = (date === today);

  for (const dev of devices) {
    const icon = PLATFORM_ICONS[dev.platform] || '&#9673;';
    const merged = mergeTimelineEvents(dev.events || []);

    chartHtml += `<div class="timeline-row">`;
    chartHtml += `<div class="timeline-label"><span class="dev-icon">${icon}</span><span class="dev-name-text">${escHtml(dev.device_name)}</span></div>`;
    chartHtml += `<div class="timeline-track" style="min-width:${scale * 600}px">`;

    // Today marker line
    if (isToday) {
      const now = new Date();
      const nowFrac = (now.getHours() + now.getMinutes() / 60 + now.getSeconds() / 3600);
      const nowLeft = (nowFrac / TOTAL_HOURS * 100);
      chartHtml += `<div class="today-marker" style="left:${nowLeft.toFixed(2)}%"></div>`;
    }

    for (const block of merged) {
      const startD = parseTz(block.start);
      const endD = parseTz(block.end);
      const startFrac = startD.getHours() + startD.getMinutes() / 60 + startD.getSeconds() / 3600;
      const endFrac = endD.getHours() + endD.getMinutes() / 60 + endD.getSeconds() / 3600;
      const left = (startFrac / TOTAL_HOURS * 100);
      const widthPct = Math.max(0.3, (endFrac - startFrac) / TOTAL_HOURS * 100);
      const cat = block.category || 'other';

      const label = block.apps.length <= 2
        ? block.apps.join(', ')
        : block.apps.slice(0,2).join(', ') + ' +' + (block.apps.length - 2);

      const appList = block.apps.join(' / ');
      const timeRange = fmtTime(block.start) + ' — ' + fmtTime(block.end);
      const duration = Math.round((endD - startD) / 60000);
      const durText = duration > 0 ? ` (${duration}min)` : '';
      const catLabel = cat === 'learning' ? '学习' : cat === 'entertainment' ? '娱乐' : '其他';

      const detail = `<span class="tip-title">${escHtml(appList)}</span>
${escHtml(catLabel)}${escHtml(durText)}
<span class="tip-time">${escHtml(timeRange)}</span>`;

      chartHtml += `<div class="timeline-block ${cat}"
        style="left:${left.toFixed(2)}%;width:${widthPct.toFixed(2)}%"
        data-tooltip="${detail.replace(/"/g, '&quot;')}"
        onmouseenter="showTooltip(event,this)" onmouseleave="hideTooltip()">
        <span class="block-dot"></span>
        <span class="block-label">${escHtml(label)}</span>
      </div>`;
    }

    chartHtml += '</div></div>';
  }

  chartHtml += '</div>';
  $('#timeline-chart-wrap').innerHTML = chartHtml;

  // Auto-scroll to "now" if zoomed and viewing today
  if (isZoomed && isToday) {
    setTimeout(scrollToNow, 100);
  }

  // Update axis min-width after render
  if (isZoomed) {
    const headers = $('#timeline-chart-wrap').querySelectorAll('.timeline-axis');
    headers.forEach(h => h.style.minWidth = (scale * 600) + 'px');
  }
}

// Tooltip
function showTooltip(e, el) {
  const tip = $('#timeline-tooltip');
  tip.innerHTML = el.dataset.tooltip;
  tip.classList.add('visible');
  positionTooltip(e);
}

function hideTooltip() {
  $('#timeline-tooltip').classList.remove('visible');
}

function positionTooltip(e) {
  const tip = $('#timeline-tooltip');
  const pad = 12;
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  // Keep in viewport
  const r = tip.getBoundingClientRect();
  if (x + r.width > window.innerWidth) x = e.clientX - r.width - pad;
  if (y + r.height > window.innerHeight) y = e.clientY - r.height - pad;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

document.addEventListener('mousemove', e => {
  if ($('#timeline-tooltip').classList.contains('visible')) {
    positionTooltip(e);
  }
});

// ═══════════════════════════════════════════════════════
// Schedule
// ═══════════════════════════════════════════════════════

async function loadSchedule() {
  // First check API key status
  try {
    const status = await api('/user/llm-key/status');
    if (status.configured) {
      showApiKeyConfigured();
    } else {
      showApiKeyMissing();
    }
  } catch (e) {
    // If endpoint not available (older backend), show the key input
    showApiKeyMissing();
  }

  // Try to load latest analysis
  try {
    const r = await api('/schedule/latest');
    renderSchedule(r.plan_markdown);
  } catch (e) {
    $('#schedule-content').innerHTML = '<p class="empty">暂无分析报告，点击上方按钮生成。</p>';
  }
  loadFriendSchedules();
}

function showApiKeyMissing() {
  $('#schedule-api-key-section').style.display = 'block';
  $('#schedule-api-key-status').style.display = 'none';
  $('#schedule-actions').style.display = 'none';
}

function showApiKeyConfigured() {
  $('#schedule-api-key-section').style.display = 'none';
  $('#schedule-api-key-status').style.display = 'flex';
  $('#schedule-actions').style.display = 'flex';
}

$('#save-api-key-btn').addEventListener('click', async () => {
  const key = $('#api-key-input').value.trim();
  if (!key) {
    alert('请输入您的 DeepSeek API Key');
    return;
  }
  try {
    await api('/user/llm-key', { method: 'PUT', body: JSON.stringify({ api_key: key }) });
    $('#api-key-input').value = '';
    showApiKeyConfigured();
  } catch (e) {
    alert('保存失败：' + e.message);
  }
});

$('#remove-api-key-btn').addEventListener('click', async () => {
  if (!confirm('确认移除 API Key？移除后将无法使用 AI 行为分析功能。')) return;
  try {
    await api('/user/llm-key', { method: 'DELETE' });
    showApiKeyMissing();
  } catch (e) {
    alert('移除失败：' + e.message);
  }
});

$('#generate-schedule-btn').addEventListener('click', async () => {
  const btn = $('#generate-schedule-btn');
  btn.textContent = '分析中 ...';
  btn.disabled = true;
  try {
    const r = await api('/schedule/generate', { method: 'POST', body: JSON.stringify({ include_calendar: false }) });
    renderSchedule(r.plan_markdown);
  } catch (e) {
    $('#schedule-content').innerHTML = `<p class="error">${escHtml(e.message)}</p>`;
  }
  btn.textContent = '生成行为分析';
  btn.disabled = false;
});

function renderSchedule(md) {
  if (!md) {
    $('#schedule-content').innerHTML = '<p class="empty">暂无分析报告</p>';
    return;
  }
  let html = md
    .replace(/### (.*)/g, '<h3>$1</h3>')
    .replace(/## (.*)/g, '<h2>$1</h2>')
    .replace(/---/g, '<hr>')
    .replace(/> (.*)/g, '<blockquote>$1</blockquote>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/- \[ \] (.*)/g, '<li>&#9744; $1</li>')
    .replace(/- (.*)/g, '<li>$1</li>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  html = '<p>' + html + '</p>';
  $('#schedule-content').innerHTML = html;
}

async function loadFriendSchedules() {
  try {
    const friends = await api('/friends');
    if (!friends.friends?.length) { $('#view-friend-schedule-btn').style.display = 'none'; return; }
    let btnHtml = '';
    for (const f of friends.friends) {
      if (f.share_schedule) btnHtml += `<button class="btn-sm" style="margin:4px" onclick="viewFriendSchedule(${f.friend_id},'${escHtml(f.display_name)}')">${escHtml(f.display_name)}</button>`;
    }
    if (btnHtml) {
      $('#view-friend-schedule-btn').style.display = 'inline-flex';
      $('#view-friend-schedule-btn').innerHTML = btnHtml;
    } else {
      $('#view-friend-schedule-btn').style.display = 'none';
    }
  } catch (e) {}
}

window.viewFriendSchedule = async (friendId, name) => {
  try {
    const r = await api(`/friends/${friendId}/schedule`);
    renderSchedule(`### ${name} 的报告\n\n` + r.plan_markdown);
  } catch (e) { alert(e.message); }
};

// ═══════════════════════════════════════════════════════
// Friends
// ═══════════════════════════════════════════════════════

$('#send-friend-request').addEventListener('click', async () => {
  const email = $('#friend-email').value.trim();
  if (!email) return;
  try {
    await api('/friends/request', { method: 'POST', body: JSON.stringify({ email }) });
    alert('好友请求已发送！');
    $('#friend-email').value = '';
    loadFriends();
  } catch (e) { alert(e.message); }
});

async function loadFriends() {
  try {
    const [reqs, friends] = await Promise.all([
      api('/friends/requests'),
      api('/friends')
    ]);

    $('#received-requests').innerHTML = (reqs.received || []).map(r => `
      <div class="request-card">
        <div class="info"><span class="name">${escHtml(r.display_name)}</span><span class="email">${escHtml(r.email)}</span></div>
        <div class="actions">
          <button class="btn-sm btn-accept" onclick="acceptRequest(${r.id})">接受</button>
          <button class="btn-sm btn-deny" onclick="denyRequest(${r.id})">拒绝</button>
        </div>
      </div>`).join('') || '<p class="muted" style="padding:16px;text-align:center">暂无待处理的请求</p>';

    $('#sent-requests').innerHTML = (reqs.sent || []).map(r => `
      <div class="request-card">
        <div class="info"><span class="name">${escHtml(r.display_name)}</span><span class="email">${escHtml(r.email)}</span></div>
        <span class="muted">等待回应</span>
      </div>`).join('') || '<p class="muted" style="padding:16px;text-align:center">暂无已发送的请求</p>';

    $('#friends-list').innerHTML = (friends.friends || []).map(f => `
      <div class="friend-card">
        <div class="info"><span class="name">${escHtml(f.display_name)}</span><span class="email">${escHtml(f.email)}</span></div>
        <div class="share-toggles">
          <label><input type="checkbox" ${f.share_usage?'checked':''} onchange="updateShare(${f.friend_id},{share_usage:this.checked})"> 共享使用</label>
          <label><input type="checkbox" ${f.share_schedule?'checked':''} onchange="updateShare(${f.friend_id},{share_schedule:this.checked})"> 共享计划</label>
        </div>
        <div class="actions">
          <button class="btn-sm btn-accept" onclick="viewFriendTimeline(${f.friend_id},'${escHtml(f.display_name)}')">时间线</button>
          <button class="btn-sm btn-remove" onclick="removeFriend(${f.friend_id})">删除</button>
        </div>
      </div>`).join('') || '<p class="muted" style="padding:16px;text-align:center">暂无好友</p>';
  } catch (e) { console.error(e); }
}

window.acceptRequest = async id => { await api(`/friends/accept/${id}`, { method:'POST' }); loadFriends(); };
window.denyRequest = async id => { await api(`/friends/deny/${id}`, { method:'POST' }); loadFriends(); };
window.removeFriend = async id => { if (confirm('确认删除该好友？')) { await api(`/friends/remove/${id}`, { method:'DELETE' }); loadFriends(); } };
window.updateShare = async (friendId, data) => { await api(`/friends/share/${friendId}`, { method:'PUT', body: JSON.stringify(data) }); };

window.viewFriendTimeline = async (friendId, name) => {
  const date = $('#timeline-date').value || new Date().toISOString().split('T')[0];
  try {
    const data = await api(`/friends/${friendId}/timeline?date=${date}`);
    data.devices = (data.devices||[]).map(d => ({...d, device_name: `[${name}] ${d.device_name}`}));
    renderTimeline(data, date);
    $$('.nav-link').forEach(x => x.classList.remove('active'));
    $('[data-page="timeline"]').classList.add('active');
    $$('.content').forEach(c => c.classList.remove('active'));
    $('#page-timeline').classList.add('active');
    document.querySelector('#timeline-summary')?.scrollIntoView({ behavior: 'smooth' });
  } catch (e) { alert(e.message); }
};

// ═══════════════════════════════════════════════════════
// Device Management
// ═══════════════════════════════════════════════════════

$('#register-device-btn').addEventListener('click', async () => {
  const name = $('#new-device-name').value.trim();
  const platform = $('#new-device-platform').value;
  if (!name) return alert('请输入设备名称');
  try {
    await api('/devices', { method: 'POST', body: JSON.stringify({ name, platform }) });
    $('#new-device-name').value = '';
    loadDevices();
  } catch (e) { alert(e.message); }
});

async function loadDevices() {
  try {
    const devices = await api('/devices');
    renderDeviceList(devices);
  } catch (e) {
    $('#device-list').innerHTML = '<p class="muted" style="text-align:center;padding:40px">加载失败</p>';
  }
}

function renderDeviceList(devices) {
  if (!devices || !devices.length) {
    $('#device-list').innerHTML = `
      <div style="text-align:center;padding:60px 20px;color:#94A3B8">
        <div style="font-size:36px;margin-bottom:12px;opacity:0.4">&#9776;</div>
        <div style="font-size:15px;font-weight:500">暂无注册设备</div>
        <div style="font-size:13px;margin-top:4px">使用上方表单注册您的第一台设备</div>
      </div>`;
    return;
  }
  const esc = s => s.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  $('#device-list').innerHTML = devices.map(d => `
    <div class="device-item" data-id="${d.id}">
      <div class="device-item-info">
        <span style="font-size:20px">${PLATFORM_ICONS[d.platform] || '&#9673;'}</span>
        <span class="device-item-name" id="dev-name-${d.id}">${escHtml(d.name)}</span>
        <span class="platform-badge">${d.platform}</span>
        <span class="device-item-date">${fmtDate(d.registered_at)}</span>
      </div>
      <div class="device-item-actions">
        <button class="btn-sm" onclick="editDevice(${d.id}, '${esc(d.name)}', '${d.platform}')">编辑</button>
        <button class="btn-sm btn-remove" onclick="deleteDevice(${d.id}, '${esc(d.name)}')">删除</button>
      </div>
    </div>
  `).join('');
}

window.editDevice = async (id, oldName, platform) => {
  const name = prompt('修改设备名称：', oldName);
  if (!name || name === oldName) return;
  try {
    const r = await api(`/devices/${id}`, { method: 'PUT', body: JSON.stringify({ name }) });
    $(`#dev-name-${id}`).textContent = r.name;
  } catch (e) { alert(e.message); }
};

window.deleteDevice = async (id, name) => {
  if (!confirm(`确认删除设备「${name}」？\n该设备的所有使用记录也将被删除。`)) return;
  try {
    await api(`/devices/${id}`, { method: 'DELETE' });
    loadDevices();
  } catch (e) { alert(e.message); }
};
