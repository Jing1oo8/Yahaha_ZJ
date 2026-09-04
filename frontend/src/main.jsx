import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArchiveX,
  BarChart3,
  Bookmark,
  ChevronRight,
  Compass,
  Download,
  Eye,
  Flame,
  Heart,
  LogOut,
  Play,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  UserPlus,
  UserRound,
  Zap,
} from "lucide-react";
import "./styles.css";

const errorTranslations = {
  "Invalid username or password": "用户名或密码错误",
  "Username already exists": "该用户名已被注册",
  "Not authenticated": "请先登录",
  "Session expired": "登录已过期，请重新登录",
  "Administrator role required": "只有管理员可以执行此操作",
  "ends_at must follow starts_at": "失效时间必须晚于生效时间",
  "Only online items can be boosted": "只能强推当前在线的内容",
  "Target user not found": "目标用户不存在",
};

function validationMessage(issue) {
  const field = issue.loc?.at(-1);
  if (field === "username") {
    if (issue.type === "string_too_short") return "用户名至少需要 3 个字符";
    if (issue.type === "string_too_long") return "用户名不能超过 32 个字符";
    if (issue.type === "string_pattern_mismatch") return "用户名只能包含英文字母、数字和下划线";
    return "请输入有效的用户名";
  }
  if (field === "password") {
    if (issue.type === "string_too_short") return "密码至少需要 8 个字符";
    if (issue.type === "string_too_long") return "密码不能超过 128 个字符";
    return "请输入有效的密码";
  }
  return issue.msg ? `提交内容有误：${issue.msg}` : "提交内容有误，请检查后重试";
}

function apiErrorMessage(detail, status) {
  if (Array.isArray(detail)) return validationMessage(detail[0] || {});
  if (typeof detail === "string") return errorTranslations[detail] || detail;
  return `请求失败 (${status})`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(apiErrorMessage(body.detail, response.status));
  return body;
}

function Auth({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("alice123");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const presets = {
    alice: "alice123",
    bob: "bob12345",
    carol: "carol123",
    admin: "admin123",
  };

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        if (username.length < 3) throw new Error("用户名至少需要 3 个字符");
        if (username.length > 32) throw new Error("用户名不能超过 32 个字符");
        if (!/^[A-Za-z0-9_]+$/.test(username)) throw new Error("用户名只能包含英文字母、数字和下划线");
        if (password.length < 8) throw new Error("密码至少需要 8 个字符");
        if (password.length > 128) throw new Error("密码不能超过 128 个字符");
        if (password !== confirmation) throw new Error("两次输入的密码不一致");
      }
      const path = mode === "register" ? "/api/auth/register" : "/api/auth/login";
      onLogin(await api(path, { method: "POST", body: JSON.stringify({ username, password }) }));
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-panel">
        <div className="brand-mark"><Sparkles size={22} /> Y</div>
        <h1>{mode === "register" ? "加入 YAHAHA" : "欢迎回来"}</h1>
        <p className="login-copy">登录后发现更懂你的精彩视频。</p>
        <div className="account-switcher auth-mode" role="tablist">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}><ShieldCheck size={16} />登录</button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setUsername(""); setPassword(""); }}><UserPlus size={16} />注册</button>
        </div>
        {mode === "login" && <div className="account-switcher" aria-label="测试账号">
          {Object.entries(presets).map(([name, secret]) => (
            <button key={name} type="button" className={username === name ? "active" : ""} onClick={() => { setUsername(name); setPassword(secret); }}>
              {name}
            </button>
          ))}
        </div>}
        <form onSubmit={submit} noValidate>
          <label>用户名<input required minLength={mode === "register" ? 3 : undefined} maxLength={mode === "register" ? 32 : undefined} pattern={mode === "register" ? "[A-Za-z0-9_]+" : undefined} value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
          <label>密码<input required type="password" minLength={mode === "register" ? 8 : undefined} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "register" ? "new-password" : "current-password"} /></label>
          {mode === "register" && <label>确认密码<input required type="password" minLength={8} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" /></label>}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary command" disabled={busy}>{busy ? "提交中..." : mode === "register" ? "创建账号" : "登录"}</button>
        </form>
      </section>
    </main>
  );
}

const recommendationBadges = {
  operator_boost: { label: "精选", className: "boosted" },
  popular_fallback: { label: "热门", className: "popular-fill" },
};

function VideoCover({ item }) {
  const badge = recommendationBadges[item.source];
  const sourceBadge = badge
    ? <span className={`recommendation-badge ${badge.className}`}>{badge.label}</span>
    : null;
  if (item.cover_url) {
    return <div className="cover image-cover"><img src={item.cover_url} alt="" />{sourceBadge}<span className="video-id"><Play size={14} fill="currentColor" />#{item.item_id}</span></div>;
  }
  return <div className={`cover cover-${item.item_id % 6}`}>{sourceBadge}<span className="video-id"><Play size={14} fill="currentColor" />#{item.item_id}</span></div>;
}

const feeds = [
  { id: "personalized", label: "个性化", icon: Sparkles },
  { id: "popular", label: "热门", icon: Flame },
  { id: "explore", label: "探索", icon: Compass },
];

function Feed({ notify }) {
  const [type, setType] = useState("personalized");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load(cursor = 0, append = false) {
    setLoading(true);
    setError("");
    try {
      const result = await api(`/api/feed?type=${type}&limit=12&cursor=${cursor}`);
      setData((previous) => append ? { ...result, items: [...previous.items, ...result.items] } : result);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [type]);

  async function action(item, eventType) {
    try {
      await api("/api/events", {
        method: "POST",
        body: JSON.stringify({
          event_id: crypto.randomUUID(),
          request_id: data.request_id,
          item_id: item.item_id,
          event_type: eventType,
          position: item.position,
        }),
      });
      const messages = {
        click: "已记录本次播放",
        like: "已标记为喜欢",
        favorite: "已收藏，可以在“我的”中查看",
        not_interested: "将减少推荐相似内容",
      };
      notify(messages[eventType] || "已记录你的选择");
    } catch (reason) {
      notify(reason.message, true);
    }
  }

  return (
    <section>
      <div className="section-heading">
        <div><h2>发现精彩内容</h2><p className="section-copy">为你挑选值得一看的新鲜视频</p></div>
      </div>
      <div className="segmented" role="tablist">
        {feeds.map(({ id, label, icon: Icon }) => (
          <button key={id} role="tab" aria-selected={type === id} onClick={() => setType(id)}><Icon size={17} />{label}</button>
        ))}
      </div>
      {error && <div className="empty-state"><p>{error}</p><button onClick={() => load()}>重试</button></div>}
      {!data && loading && <div className="empty-state">正在加载候选...</div>}
      {data && data.items.length === 0 && <div className="empty-state">当前没有可返回内容</div>}
      <div className="feed-grid">
        {data?.items.map((item) => (
          <article className="content-card" key={`${data.request_id}-${item.item_id}`}>
            <VideoCover item={item} />
            <div className="card-body">
              <h3>{item.title}</h3>
              <div className="stats"><span><Heart size={14} />{item.source_likes.toLocaleString()}</span><span><Activity size={14} />{item.source_views.toLocaleString()}</span></div>
              <div className="item-actions">
                <button aria-label="播放" title="播放" onClick={() => action(item, "click")}><Play size={18} fill="currentColor" /></button>
                <button aria-label="喜欢" title="喜欢" onClick={() => action(item, "like")}><Heart size={18} /></button>
                <button aria-label="收藏" title="收藏" onClick={() => action(item, "favorite")}><Bookmark size={18} /></button>
                <button aria-label="减少推荐" title="减少推荐" onClick={() => action(item, "not_interested")}><ThumbsDown size={18} /></button>
              </div>
            </div>
          </article>
        ))}
      </div>
      {data?.next_cursor != null && <button className="load-more" disabled={loading} onClick={() => load(data.next_cursor, true)}>{loading ? "加载中..." : "加载更多"}</button>}
    </section>
  );
}

function Profile() {
  const [profile, setProfile] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  useEffect(() => { api("/api/profile").then(setProfile); }, []);
  if (!profile) return <div className="empty-state">正在整理你的内容...</div>;
  const histories = [
    { title: "观看历史", items: profile.clicked_details || [], icon: Play, empty: "播放过的视频会出现在这里。", className: "watched-list" },
    { title: "最近喜欢", items: profile.liked_details || [], icon: Heart, empty: "还没有喜欢的内容，去“发现”逛逛吧。", className: "liked-list" },
    { title: "最近收藏", items: profile.favorite_details || [], icon: Bookmark, empty: "收藏喜欢的视频，之后可以从这里找到。", className: "saved-list" },
  ];
  return (
    <section>
      <div className="section-heading"><div><h2>我的空间</h2><p className="section-copy">你与内容的每次互动，都会让推荐更合心意</p></div></div>
      <div className="profile-band"><div><span>观看过</span><strong>{profile.clicked_items?.length || 0}</strong></div><div><span>喜欢</span><strong>{profile.liked_items?.length || 0}</strong></div><div><span>收藏</span><strong>{profile.favorite_items?.length || 0}</strong></div><div><span>不感兴趣</span><strong>{profile.not_interested_items.length}</strong></div></div>
      <div className="profile-layout">
        {histories.map(({ title, items, icon: Icon, empty, className }) => <div key={title}><h3 className="subheading">{title}</h3><div className={`profile-history ${className}`}>{items.length ? items.map((item) => <button type="button" key={item.item_id} onClick={() => setSelectedItem(item)}><Icon size={16} fill={title === "观看历史" ? "none" : "currentColor"} /><span>{item.title}</span><ChevronRight size={16} /></button>) : <p>{empty}</p>}</div></div>)}
      </div>
      {selectedItem && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedItem(null); }}><div className="item-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="item-detail-title"><VideoCover item={selectedItem} /><div className="item-detail-content"><div className="panel-heading"><span className="detail-id">视频 #{selectedItem.item_id}</span><button type="button" onClick={() => setSelectedItem(null)}>关闭</button></div><h3 id="item-detail-title">{selectedItem.title}</h3><div className="detail-stats"><span><Heart size={17} />{selectedItem.source_likes.toLocaleString()} 喜欢</span><span><Activity size={17} />{selectedItem.source_views.toLocaleString()} 次观看</span></div></div></div></div>}
    </section>
  );
}

const rangeOptions = [
  ["1h", "最近 1 小时"],
  ["24h", "最近 24 小时"],
  ["7d", "最近 7 天"],
  ["30d", "最近 30 天"],
  ["all", "全部时间"],
];

function TrendChart({ data }) {
  const width = 800;
  const height = 220;
  const padding = 28;
  const series = [
    ["requests", "请求", "#25835c"],
    ["exposures", "曝光", "#17211d"],
    ["clicks", "点击", "#d29500"],
    ["likes", "点赞", "#b83b4b"],
  ];
  const maxValue = Math.max(1, ...data.flatMap((point) => series.map(([key]) => point[key])));
  const points = (key) => data.map((point, index) => {
    const x = data.length === 1 ? width / 2 : padding + index * (width - padding * 2) / (data.length - 1);
    const y = height - padding - point[key] * (height - padding * 2) / maxValue;
    return `${x},${y}`;
  }).join(" ");
  return (
    <div className="trend-wrap">
      <div className="chart-legend">{series.map(([key, label, color]) => <span key={key}><i style={{ background: color }} />{label}</span>)}</div>
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="请求、曝光、点击与点赞趋势">
        {[0, 1, 2, 3, 4].map((line) => <line key={line} x1={padding} x2={width - padding} y1={padding + line * (height - padding * 2) / 4} y2={padding + line * (height - padding * 2) / 4} />)}
        {series.map(([key, , color]) => <polyline key={key} points={points(key)} fill="none" stroke={color} strokeWidth="3" vectorEffect="non-scaling-stroke" />)}
      </svg>
      <div className="chart-axis"><span>{data[0]?.bucket}</span><span>{data.at(-1)?.bucket}</span></div>
    </div>
  );
}

function ProfileItemList({ title, items, empty }) {
  return <div className="debug-column"><h4>{title}</h4>{items.length ? items.map((item) => <div className="debug-item" key={item.item_id}><strong>#{item.item_id}</strong><span>{item.title}</span>{item.source && <code>{item.source} · {item.score.toFixed(5)}</code>}</div>) : <p>{empty}</p>}</div>;
}

function localDateTime(hoursFromNow = 0) {
  const date = new Date(Date.now() + hoursFromNow * 60 * 60 * 1000);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function displayDateTime(value) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function displayDuration(seconds) {
  const hours = Math.max(1, Math.round(seconds / 3600));
  if (hours % 24 === 0) return `${hours / 24} 天`;
  if (hours > 24) return `${Math.floor(hours / 24)} 天 ${hours % 24} 小时`;
  return `${hours} 小时`;
}

const boostStatusLabels = {
  active: "生效中",
  scheduled: "待生效",
  expired: "已结束",
  item_offline: "内容已下线",
  disabled: "已停用",
};

function Admin({ notify }) {
  const [dashboard, setDashboard] = useState(null);
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [query, setQuery] = useState("");
  const [range, setRange] = useState("24h");
  const [trace, setTrace] = useState(null);
  const [debugProfile, setDebugProfile] = useState(null);
  const [contentView, setContentView] = useState("all");
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [boostRules, setBoostRules] = useState([]);
  const [boostItems, setBoostItems] = useState([]);
  const [batchBusy, setBatchBusy] = useState(false);
  const [boostForm, setBoostForm] = useState({ target_user_id: "", feed_type: "", reason: "内容运营强推", starts_at: localDateTime(), ends_at: localDateTime(24), priority: 300 });

  async function refresh(selectedRange = range, selectedView = contentView) {
    const statusQuery = selectedView === "offline" ? "&status=offline" : "";
    const [nextDashboard, nextItems, nextUsers, nextBoostRules] = await Promise.all([
      api(`/api/admin/dashboard?range=${selectedRange}`),
      api(`/api/admin/items?query=${encodeURIComponent(query)}&limit=30${statusQuery}`),
      api("/api/admin/users"),
      api("/api/admin/boosts"),
    ]);
    setDashboard(nextDashboard);
    setItems(nextItems);
    setUsers(nextUsers);
    setBoostRules(nextBoostRules);
  }
  useEffect(() => { refresh(range); }, [range]);

  async function inspectRequest(requestId) {
    setTrace(await api(`/api/admin/requests/${requestId}`));
  }

  async function inspectUser(userId) {
    setDebugProfile(await api(`/api/admin/users/${userId}/profile`));
  }

  async function changeContentView(nextView) {
    setContentView(nextView);
    setSelectedIds(new Set());
    await refresh(range, nextView);
  }

  async function statusChange(item) {
    const next = item.status === "online" ? "offline" : "online";
    await api(`/api/admin/items/${item.item_id}/status`, { method: "PATCH", body: JSON.stringify({ status: next, reason: `dashboard ${next}` }) });
    notify(next === "offline" ? "内容已从所有服务端候选下线" : "内容已恢复");
    refresh();
  }

  function toggleSelected(itemId) {
    setSelectedIds((current) => {
      const next = new Set(current);
      next.has(itemId) ? next.delete(itemId) : next.add(itemId);
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds(selectedIds.size === items.length ? new Set() : new Set(items.map((item) => item.item_id)));
  }

  async function batchStatus(nextStatus) {
    const targets = items.filter((item) => selectedIds.has(item.item_id) && item.status !== nextStatus);
    if (!targets.length) return;
    if (nextStatus === "offline" && !window.confirm(`确认下线选中的 ${targets.length} 条内容吗？`)) return;
    setBatchBusy(true);
    try {
      const results = await Promise.allSettled(targets.map((item) => api(`/api/admin/items/${item.item_id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus, reason: `dashboard batch ${nextStatus}` }),
      })));
      const succeeded = results.filter((result) => result.status === "fulfilled").length;
      const failed = results.length - succeeded;
      setSelectedIds(new Set());
      await refresh();
      notify(failed ? `已处理 ${succeeded} 条，${failed} 条失败` : `已${nextStatus === "offline" ? "下线" : "恢复"} ${succeeded} 条内容`, failed > 0);
    } catch (reason) {
      notify(reason.message, true);
    } finally {
      setBatchBusy(false);
    }
  }

  function openBoost(targets) {
    setBoostItems(targets);
    setBoostForm({ target_user_id: "", feed_type: "", reason: "内容运营强推", starts_at: localDateTime(), ends_at: localDateTime(24), priority: 300 });
  }

  async function submitBoost(event) {
    event.preventDefault();
    try {
      const results = await Promise.allSettled(boostItems.map((item) => api("/api/admin/boosts", {
        method: "POST",
        body: JSON.stringify({
          item_id: item.item_id,
          target_user_id: boostForm.target_user_id ? Number(boostForm.target_user_id) : null,
          feed_type: boostForm.feed_type || null,
          reason: boostForm.reason,
          starts_at: new Date(boostForm.starts_at).toISOString(),
          ends_at: new Date(boostForm.ends_at).toISOString(),
          priority: Number(boostForm.priority),
        }),
      })));
      const succeeded = results.filter((result) => result.status === "fulfilled").length;
      const failed = results.length - succeeded;
      notify(failed ? `已创建 ${succeeded} 条强推规则，${failed} 条失败` : `已创建 ${succeeded} 条强推规则`, failed > 0);
      if (!failed) {
        setBoostItems([]);
        setSelectedIds(new Set());
        await refresh(range, contentView);
      }
    } catch (reason) {
      notify(reason.message, true);
    }
  }

  if (!dashboard) return <div className="empty-state">正在聚合真实事件指标...</div>;
  const metrics = [["总用户", dashboard.users], ["活跃用户", dashboard.active_users], ["请求", dashboard.requests], ["曝光", dashboard.exposures], ["点击", dashboard.clicks], ["CTR", `${(dashboard.ctr * 100).toFixed(2)}%`], ["点赞", dashboard.likes], ["下线", dashboard.offline_items]];
  const selectedItems = items.filter((item) => selectedIds.has(item.item_id));
  const selectedOnline = selectedItems.filter((item) => item.status === "online");
  const selectedOffline = selectedItems.filter((item) => item.status === "offline");
  const allSelected = items.length > 0 && selectedIds.size === items.length;
  const normalizedQuery = query.trim().toLowerCase();
  const filteredBoostRules = boostRules.filter((rule) => !normalizedQuery
    || String(rule.item_id).includes(normalizedQuery)
    || rule.title.toLowerCase().includes(normalizedQuery));
  return (
    <section>
      <div className="section-heading"><div><h2>运营看板</h2><p className="section-copy">查看推荐表现并管理内容</p></div><div className="dashboard-controls"><label>时间范围<select value={range} onChange={(event) => setRange(event.target.value)}>{rangeOptions.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><a className="icon-command" href={`/api/admin/dashboard/export?range=${range}`} title="导出 CSV"><Download size={18} /></a><span className="model-pill">{dashboard.model_version}</span></div></div>
      <div className="metric-strip">{metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="analytics-layout">
        <div className="analytics-panel wide"><div className="panel-heading"><h3>趋势</h3><span>{rangeOptions.find(([value]) => value === range)?.[1]}</span></div><TrendChart data={dashboard.trend} /></div>
        <div className="analytics-panel"><div className="panel-heading"><h3>信息流占比</h3><span>按请求数</span></div><div className="share-list">{dashboard.feed_shares.map((feed) => <div key={feed.feed_type}><span>{feed.feed_type}</span><div><i style={{ width: `${feed.share * 100}%` }} /></div><strong>{(feed.share * 100).toFixed(1)}%</strong></div>)}</div></div>
        <div className="analytics-panel"><div className="panel-heading"><h3>热门内容</h3><span>真实行为</span></div><div className="compact-list">{dashboard.popular_items.slice(0, 5).map((item) => <div key={item.item_id}><strong>#{item.item_id}</strong><p>{item.title}</p><span>{item.exposures} 曝光 · {item.clicks} 点击 · {item.likes} 赞</span></div>)}</div></div>
      </div>
      <div className="user-debugger">
        <div className="panel-heading"><div><h3>用户画像调试</h3></div><span>{users.length} 个账号</span></div>
        <div className="user-debug-layout">
          <div className="user-list">{users.map((entry) => <button className={debugProfile?.user_id === entry.user_id ? "active" : ""} key={entry.user_id} onClick={() => inspectUser(entry.user_id)}><span><strong>{entry.username}</strong><small>{entry.dataset_user_id == null ? "冷启动" : `MicroLens ${entry.dataset_user_id}`}</small></span><code>{entry.requests} 请求 · {entry.events} 行为</code></button>)}</div>
          {!debugProfile && <div className="debug-empty">选择一个用户查看画像和候选解释</div>}
          {debugProfile && <div className="debug-detail"><div className="debug-summary"><span>离线历史<strong>{debugProfile.history_count}</strong></span><span>曝光内容<strong>{debugProfile.exposure_count}</strong></span><span>正反馈<strong>{debugProfile.positive_items.length}</strong></span><span>负反馈<strong>{debugProfile.not_interested_items.length}</strong></span></div><div className="debug-grid"><ProfileItemList title="离线历史（最近）" items={debugProfile.history_details} empty="冷启动用户没有离线历史" /><ProfileItemList title="在线正反馈" items={debugProfile.positive_details} empty="暂无点赞或收藏" /><ProfileItemList title="不感兴趣" items={debugProfile.negative_details} empty="暂无负反馈" /><ProfileItemList title="个性化候选预览" items={debugProfile.recommendation_preview} empty="暂无可用候选" /></div></div>}
        </div>
      </div>
      <div className="request-section"><div className="panel-heading"><h3>最近推荐请求</h3><span>点击查看完整链路</span></div><div className="request-table"><div className="request-row header"><span>请求</span><span>用户</span><span>Feed</span><span>曝光 / 行为</span><span /></div>{dashboard.recent_requests.map((request) => <div className="request-row" key={request.request_id}><code>{request.request_id.slice(0, 8)}</code><span>{request.username}</span><span>{request.feed_type}</span><span>{request.exposures} / {request.events}</span><button title="查看请求链路" onClick={() => inspectRequest(request.request_id)}><Eye size={17} /></button></div>)}</div></div>
      {trace && <div className="trace-panel"><div className="panel-heading"><div><h3>{trace.request_id}</h3></div><button onClick={() => setTrace(null)}>关闭</button></div><div className="trace-meta"><span>{trace.username}</span><span>{trace.feed_type}</span><span>{trace.model_version}</span></div><div className="trace-columns"><div><h4>曝光</h4>{trace.exposures.map((entry) => <div className="trace-row" key={`${entry.position}-${entry.item_id}`}><strong>#{entry.item_id}</strong><span>位置 {entry.position}</span><span>{entry.source}</span><code>{entry.score.toFixed(5)}</code></div>)}</div><div><h4>事件</h4>{trace.events.map((event) => <div className="trace-row" key={event.event_id}><strong>#{event.item_id}</strong><span>位置 {event.position}</span><span>{event.event_type}</span><code>{event.source}</code></div>)}</div></div></div>}
      <div className="ops-heading"><h3>内容运营</h3><form onSubmit={(event) => { event.preventDefault(); setSelectedIds(new Set()); refresh(range, contentView); }}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按 ID 或标题搜索" /></form></div>
      <div className="bulk-toolbar"><div><strong>{contentView === "boosted" ? `共 ${filteredBoostRules.length} 条强推规则` : `已选择 ${selectedItems.length} 条`}</strong><span>{contentView === "boosted" ? "查看规则范围、优先级与有效时间" : "支持批量调整状态或创建相同强推规则"}</span></div><div className="toolbar-groups"><div className="content-view-tabs" role="tablist"><button type="button" role="tab" aria-selected={contentView === "all"} onClick={() => changeContentView("all")}>全部内容</button><button type="button" role="tab" aria-selected={contentView === "boosted"} onClick={() => changeContentView("boosted")}>已强推 <span>{boostRules.length}</span></button><button type="button" role="tab" aria-selected={contentView === "offline"} onClick={() => changeContentView("offline")}>已下线 <span>{dashboard.offline_items}</span></button></div><div className="batch-buttons"><button type="button" disabled={contentView === "boosted" || !selectedOnline.length || batchBusy} onClick={() => openBoost(selectedOnline)}><Zap size={16} />批量强推</button><button type="button" disabled={contentView === "boosted" || !selectedOnline.length || batchBusy} onClick={() => batchStatus("offline")}><ArchiveX size={16} />批量下线</button><button type="button" disabled={contentView === "boosted" || !selectedOffline.length || batchBusy} onClick={() => batchStatus("online")}><RotateCcw size={16} />批量恢复</button><button type="button" disabled={contentView === "boosted" || !selectedItems.length || batchBusy} onClick={() => setSelectedIds(new Set())}>清空选择</button></div></div></div>
      {contentView !== "boosted" && <div className="ops-table"><div className="ops-row header"><input type="checkbox" aria-label="选择当前页全部内容" checked={allSelected} onChange={toggleAll} /><span>全选</span><span>热度</span><span>状态</span><span>操作</span></div>{items.map((item) => <div className={`ops-row ${selectedIds.has(item.item_id) ? "selected" : ""}`} key={item.item_id}><input type="checkbox" aria-label={`选择内容 ${item.item_id}`} checked={selectedIds.has(item.item_id)} onChange={() => toggleSelected(item.item_id)} /><div><strong>#{item.item_id}</strong><p>{item.title}</p></div><span>{item.source_views.toLocaleString()}</span><span className={`status ${item.status}`}>{item.status === "online" ? "在线" : "已下线"}</span><div className="row-actions"><button title="配置强推" disabled={item.status !== "online"} onClick={() => openBoost([item])}><Zap size={17} /></button><button onClick={() => statusChange(item)}>{item.status === "online" ? "下线" : "恢复"}</button></div></div>)}</div>}
      {contentView === "boosted" && <div className="boost-rules-table"><div className="boost-rule-row header"><span>强推内容</span><span>作用范围</span><span>优先级</span><span>有效时间</span><span>状态</span></div>{filteredBoostRules.length ? filteredBoostRules.map((rule) => <div className="boost-rule-row" key={rule.boost_id}><div><strong>#{rule.item_id} {rule.title}</strong><p>{rule.reason}</p></div><div className="rule-scope"><span>{rule.target_username || "全部用户"}</span><span>{feeds.find((feed) => feed.id === rule.feed_type)?.label || "全部信息流"}</span></div><strong className="rule-priority">{rule.priority}</strong><div className="rule-time"><span>{displayDateTime(rule.starts_at)} - {displayDateTime(rule.ends_at)}</span><small>持续 {displayDuration(rule.duration_seconds)}</small></div><span className={`rule-status ${rule.rule_status}`}>{boostStatusLabels[rule.rule_status] || rule.rule_status}</span></div>) : <div className="table-empty">没有符合条件的强推规则</div>}</div>}
      {boostItems.length > 0 && <div className="modal-backdrop" role="presentation"><div className="boost-dialog" role="dialog" aria-modal="true" aria-labelledby="boost-title"><div className="panel-heading"><div><h3 id="boost-title">{boostItems.length === 1 ? `配置强推 #${boostItems[0].item_id}` : `批量配置强推（${boostItems.length} 条）`}</h3></div><button type="button" onClick={() => setBoostItems([])}>关闭</button></div><p className="dialog-item-title">{boostItems.length === 1 ? boostItems[0].title : `将为已选择的 ${boostItems.length} 条在线内容创建相同规则`}</p><form onSubmit={submitBoost}><div className="form-grid"><label>目标用户<select value={boostForm.target_user_id} onChange={(event) => setBoostForm({ ...boostForm, target_user_id: event.target.value })}><option value="">全部用户</option>{users.filter((entry) => entry.role === "user").map((entry) => <option key={entry.user_id} value={entry.user_id}>{entry.username}</option>)}</select></label><label>目标信息流<select value={boostForm.feed_type} onChange={(event) => setBoostForm({ ...boostForm, feed_type: event.target.value })}><option value="">全部信息流</option>{feeds.map((feed) => <option key={feed.id} value={feed.id}>{feed.label}</option>)}</select></label><label>生效时间<input type="datetime-local" required value={boostForm.starts_at} onChange={(event) => setBoostForm({ ...boostForm, starts_at: event.target.value })} /></label><label>失效时间<input type="datetime-local" required value={boostForm.ends_at} onChange={(event) => setBoostForm({ ...boostForm, ends_at: event.target.value })} /></label><label>优先级<input type="number" min="1" max="1000" required value={boostForm.priority} onChange={(event) => setBoostForm({ ...boostForm, priority: event.target.value })} /></label><label className="reason-field">原因<input required minLength="3" maxLength="300" value={boostForm.reason} onChange={(event) => setBoostForm({ ...boostForm, reason: event.target.value })} /></label></div><div className="dialog-actions"><button type="button" onClick={() => setBoostItems([])}>取消</button><button className="primary" type="submit"><Zap size={16} />创建 {boostItems.length} 条规则</button></div></form></div></div>}
    </section>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("feed");
  const [toast, setToast] = useState(null);
  const [checking, setChecking] = useState(true);
  useEffect(() => { api("/api/auth/me").then(setUser).catch(() => {}).finally(() => setChecking(false)); }, []);
  function notify(message, error = false) { setToast({ message, error }); setTimeout(() => setToast(null), 2600); }
  async function logout() { await api("/api/auth/logout", { method: "POST" }); setUser(null); setView("feed"); }
  if (checking) return <div className="app-loading">YAHAHA</div>;
  if (!user) return <Auth onLogin={setUser} />;
  return (
    <div className="app-shell">
      <header><div className="brand"><div className="brand-mark"><Sparkles size={18} />Y</div><div><strong>YAHAHA</strong><span>视频社区</span></div></div><nav><button className={view === "feed" ? "active" : ""} onClick={() => setView("feed")}><Compass size={17} />发现</button><button className={view === "profile" ? "active" : ""} onClick={() => setView("profile")}><UserRound size={17} />我的</button>{user.role === "admin" && <button className={view === "admin" ? "active" : ""} onClick={() => setView("admin")}><BarChart3 size={17} />管理</button>}</nav><div className="user-menu"><span><ShieldCheck size={16} />{user.username}</span><button aria-label="退出登录" title="退出登录" onClick={logout}><LogOut size={18} /></button></div></header>
      <main className="workspace">{view === "feed" && <Feed notify={notify} />}{view === "profile" && <Profile />}{view === "admin" && <Admin notify={notify} />}</main>
      {toast && <div className={`toast ${toast.error ? "error-toast" : ""}`}>{toast.message}</div>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
