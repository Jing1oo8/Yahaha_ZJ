import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Compass,
  Flame,
  Heart,
  LogOut,
  MousePointerClick,
  Search,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  UserRound,
  Zap,
} from "lucide-react";
import "./styles.css";

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `请求失败 (${response.status})`);
  return body;
}

function Login({ onLogin }) {
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("alice123");
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
      onLogin(await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }));
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
        <p className="eyebrow">RECOMMENDATION ENGINEERING</p>
        <h1>YAHAHA Recsys Lab</h1>
        <p className="login-copy">进入真实数据驱动的推荐、反馈与运营闭环。</p>
        <div className="account-switcher" aria-label="测试账号">
          {Object.entries(presets).map(([name, secret]) => (
            <button key={name} type="button" className={username === name ? "active" : ""} onClick={() => { setUsername(name); setPassword(secret); }}>
              {name}
            </button>
          ))}
        </div>
        <form onSubmit={submit}>
          <label>用户名<input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" /></label>
          <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary command" disabled={busy}>{busy ? "登录中..." : "登录"}</button>
        </form>
      </section>
    </main>
  );
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
      notify(eventType === "not_interested" ? "已降低相似内容偏好" : "反馈已写入用户画像");
    } catch (reason) {
      notify(reason.message, true);
    }
  }

  return (
    <section>
      <div className="section-heading">
        <div><p className="eyebrow">LIVE RANKING</p><h2>推荐信息流</h2></div>
        {data && <span className="request-id">request {data.request_id.slice(0, 8)}</span>}
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
            <div className="cover" aria-hidden="true"><span>{item.item_id}</span></div>
            <div className="card-body">
              <div className="item-meta"><span>#{item.item_id}</span><span>{item.source}</span></div>
              <h3>{item.title}</h3>
              <div className="stats"><span><Heart size={14} />{item.source_likes.toLocaleString()}</span><span><Activity size={14} />{item.source_views.toLocaleString()}</span></div>
              <p className="score">score {item.score.toFixed(5)} · {item.model_version}</p>
              <div className="item-actions">
                <button title="点击" onClick={() => action(item, "click")}><MousePointerClick size={18} /></button>
                <button title="喜欢" onClick={() => action(item, "like")}><Heart size={18} /></button>
                <button title="不感兴趣" onClick={() => action(item, "not_interested")}><ThumbsDown size={18} /></button>
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
  useEffect(() => { api("/api/profile").then(setProfile); }, []);
  if (!profile) return <div className="empty-state">正在读取画像...</div>;
  return (
    <section>
      <div className="section-heading"><div><p className="eyebrow">FEEDBACK STATE</p><h2>我的画像</h2></div></div>
      <div className="profile-band"><div><span>MicroLens 用户</span><strong>{profile.dataset_user_id ?? "冷启动"}</strong></div><div><span>正反馈内容</span><strong>{profile.positive_items.length}</strong></div><div><span>不感兴趣</span><strong>{profile.not_interested_items.length}</strong></div></div>
      <h3 className="subheading">最近行为</h3>
      <div className="event-list">{profile.recent_events.length ? profile.recent_events.map((event) => <div key={event.event_id}><span>{event.event_type}</span><strong>#{event.item_id}</strong><code>{event.request_id.slice(0, 8)}</code></div>) : <p>尚无主动反馈</p>}</div>
    </section>
  );
}

function Admin({ notify }) {
  const [dashboard, setDashboard] = useState(null);
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState("");

  async function refresh() {
    setDashboard(await api("/api/admin/dashboard"));
    setItems(await api(`/api/admin/items?query=${encodeURIComponent(query)}&limit=30`));
  }
  useEffect(() => { refresh(); }, []);

  async function statusChange(item) {
    const next = item.status === "online" ? "offline" : "online";
    await api(`/api/admin/items/${item.item_id}/status`, { method: "PATCH", body: JSON.stringify({ status: next, reason: `dashboard ${next}` }) });
    notify(next === "offline" ? "内容已从所有服务端候选下线" : "内容已恢复");
    refresh();
  }

  async function boost(item) {
    const now = new Date();
    await api("/api/admin/boosts", { method: "POST", body: JSON.stringify({ item_id: item.item_id, reason: "dashboard priority", starts_at: new Date(now.getTime() - 60000).toISOString(), ends_at: new Date(now.getTime() + 86400000).toISOString(), priority: 300 }) });
    notify("强推规则已生效，有效期 24 小时");
  }

  if (!dashboard) return <div className="empty-state">正在聚合真实事件指标...</div>;
  const metrics = [["用户", dashboard.users], ["请求", dashboard.requests], ["曝光", dashboard.exposures], ["点击", dashboard.clicks], ["CTR", `${(dashboard.ctr * 100).toFixed(2)}%`], ["点赞", dashboard.likes], ["下线", dashboard.offline_items]];
  return (
    <section>
      <div className="section-heading"><div><p className="eyebrow">OPERATIONS</p><h2>Dashboard</h2></div><span className="model-pill">{dashboard.model_version}</span></div>
      <div className="metric-strip">{metrics.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="ops-heading"><h3>内容运营</h3><form onSubmit={(event) => { event.preventDefault(); refresh(); }}><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="按 ID 或标题搜索" /></form></div>
      <div className="ops-table"><div className="ops-row header"><span>内容</span><span>热度</span><span>状态</span><span>操作</span></div>{items.map((item) => <div className="ops-row" key={item.item_id}><div><strong>#{item.item_id}</strong><p>{item.title}</p></div><span>{item.source_views.toLocaleString()}</span><span className={`status ${item.status}`}>{item.status}</span><div className="row-actions"><button title="强推" disabled={item.status !== "online"} onClick={() => boost(item)}><Zap size={17} /></button><button onClick={() => statusChange(item)}>{item.status === "online" ? "下线" : "恢复"}</button></div></div>)}</div>
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
  if (!user) return <Login onLogin={setUser} />;
  return (
    <div className="app-shell">
      <header><div className="brand"><div className="brand-mark"><Sparkles size={18} />Y</div><div><strong>YAHAHA</strong><span>Recsys Lab</span></div></div><nav><button className={view === "feed" ? "active" : ""} onClick={() => setView("feed")}><Compass size={17} />信息流</button><button className={view === "profile" ? "active" : ""} onClick={() => setView("profile")}><UserRound size={17} />画像</button>{user.role === "admin" && <button className={view === "admin" ? "active" : ""} onClick={() => setView("admin")}><BarChart3 size={17} />管理</button>}</nav><div className="user-menu"><span><ShieldCheck size={16} />{user.username}</span><button title="退出" onClick={logout}><LogOut size={18} /></button></div></header>
      <main className="workspace">{view === "feed" && <Feed notify={notify} />}{view === "profile" && <Profile />}{view === "admin" && <Admin notify={notify} />}</main>
      {toast && <div className={`toast ${toast.error ? "error-toast" : ""}`}>{toast.message}</div>}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
