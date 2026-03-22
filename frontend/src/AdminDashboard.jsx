import { useState, useEffect } from "react";
import axios from "axios";

const API = "http://localhost:8000/api/v1/admin";

const INTENT_COLORS = {
  INFO_QUERY: "#1565c0",
  ACTION_REQUEST: "#e65100",
  CHITCHAT: "#6a1b9a",
  SENSITIVE: "#c62828",
  FRAUD: "#b71c1c",
};

export default function AdminDashboard({ token }) {
  const [stats, setStats] = useState(null);
  const [escalations, setEscalations] = useState([]);
  const [tab, setTab] = useState("overview");
  const [responding, setResponding] = useState({});
  const [responseText, setResponseText] = useState({});
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  const load = async () => {
    try {
      const [s, e] = await Promise.all([
        axios.get(`${API}/stats`, { headers: authHeaders }),
        axios.get(`${API}/escalations?status=pending`, { headers: authHeaders }),
      ]);
      setStats(s.data);
      setEscalations(e.data.escalations || []);
    } catch (err) {
      console.error("Dashboard load error:", err.response?.data || err.message);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [token]);

  const resolve = async (id) => {
    const text = responseText[id]?.trim();
    if (!text) return;

    try {
      await axios.post(
        `${API}/escalations/${id}/resolve`,
        { agent_response: text },
        { headers: authHeaders }
      );
      setResponding((p) => ({ ...p, [id]: false }));
      setResponseText((p) => ({ ...p, [id]: "" }));
      load();
    } catch (err) {
      console.error("Resolve escalation error:", err.response?.data || err.message);
    }
  };

  if (!stats) return <div style={s.loading}>Loading dashboard...</div>;

  return (
    <div style={s.page}>
      <header style={s.header}>
        <h1 style={s.title}>Admin Dashboard</h1>
        <span style={s.live}>Live</span>
      </header>

      <div style={s.tabs}>
        {["overview", "escalations", "logs"].map((t) => (
          <button
            key={t}
            style={{ ...s.tab, ...(tab === t ? s.tabActive : {}) }}
            onClick={() => setTab(t)}
          >
            {t === "escalations" && escalations.length > 0
              ? `Escalations (${escalations.length})`
              : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div>
          <div style={s.cards}>
            {[
              { label: "Total Queries", value: stats.total, color: "#1565c0" },
              {
                label: "Blocked",
                value: `${stats.blocked} (${stats.blocked_pct}%)`,
                color: "#c62828",
              },
              { label: "Flagged", value: stats.flagged, color: "#e65100" },
              {
                label: "Pending HITL",
                value: stats.pending_escalations,
                color: "#6a1b9a",
              },
            ].map((c) => (
              <div key={c.label} style={s.card}>
                <p style={{ ...s.cardVal, color: c.color }}>{c.value}</p>
                <p style={s.cardLabel}>{c.label}</p>
              </div>
            ))}
          </div>

          <h3 style={s.sectionTitle}>Intent Breakdown</h3>
          <div style={s.intentList}>
            {(stats.intents || []).map((i) => (
              <div key={i.intent} style={s.intentRow}>
                <span
                  style={{
                    ...s.intentBadge,
                    background: `${INTENT_COLORS[i.intent] || "#888"}18`,
                    color: INTENT_COLORS[i.intent] || "#555",
                  }}
                >
                  {i.intent}
                </span>
                <div style={s.barWrap}>
                  <div
                    style={{
                      ...s.bar,
                      width: `${Math.round((i.cnt / Math.max(stats.total || 1, 1)) * 100)}%`,
                      background: INTENT_COLORS[i.intent] || "#888",
                    }}
                  />
                </div>
                <span style={s.barCount}>{i.cnt}</span>
              </div>
            ))}
          </div>

          <h3 style={s.sectionTitle}>Recent Interactions</h3>
          <table style={s.table}>
            <thead>
              <tr>
                {["Time", "Session", "Question", "Intent", "Blocked", "Flagged"].map((h) => (
                  <th key={h} style={s.th}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(stats.recent || []).map((r, i) => (
                <tr key={i} style={{ background: r.flagged ? "#fff8f8" : "transparent" }}>
                  <td style={s.td}>{(r.timestamp || "").slice(11, 19)}</td>
                  <td style={s.td}>
                    <code>{(r.session_id || "").slice(0, 8)}...</code>
                  </td>
                  <td style={{ ...s.td, maxWidth: 200 }}>
                    {(r.question || "").slice(0, 60)}
                    {(r.question || "").length > 60 ? "..." : ""}
                  </td>
                  <td style={s.td}>
                    <span
                      style={{
                        fontSize: 11,
                        fontWeight: 600,
                        padding: "2px 6px",
                        borderRadius: 8,
                        background: `${INTENT_COLORS[r.intent] || "#888"}18`,
                        color: INTENT_COLORS[r.intent] || "#555",
                      }}
                    >
                      {r.intent}
                    </span>
                  </td>
                  <td style={s.td}>{r.blocked ? "Blocked" : "OK"}</td>
                  <td style={s.td}>{r.flagged ? "Flagged" : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "escalations" && (
        <div>
          {escalations.length === 0 ? (
            <p style={s.empty}>No pending escalations</p>
          ) : (
            escalations.map((e) => (
              <div key={e.id} style={s.escCard}>
                <div style={s.escHeader}>
                  <span style={s.escId}>#{e.id}</span>
                  <span style={s.escReason}>{e.reason}</span>
                  <span style={s.escTime}>{(e.timestamp || "").slice(0, 19).replace("T", " ")}</span>
                </div>
                <p style={s.escSession}>
                  Session: <code>{(e.session_id || "").slice(0, 8)}...</code>
                </p>

                <details style={s.histDetails}>
                  <summary style={s.histSummary}>
                    View conversation ({Array.isArray(e.conversation) ? e.conversation.length : 0} turns)
                  </summary>
                  <div style={s.histBox}>
                    {(Array.isArray(e.conversation) ? e.conversation : []).map((t, i) => (
                      <div
                        key={i}
                        style={{
                          ...s.histTurn,
                          background: t.role === "user" ? "#e3f2fd" : "#f5f5f5",
                        }}
                      >
                        <strong>{t.role === "user" ? "User" : "Bot"}:</strong> {t.content}
                      </div>
                    ))}
                  </div>
                </details>

                {responding[e.id] ? (
                  <div style={s.respondBox}>
                    <textarea
                      style={s.textarea}
                      placeholder="Type your response to the customer..."
                      value={responseText[e.id] || ""}
                      onChange={(ev) =>
                        setResponseText((p) => ({ ...p, [e.id]: ev.target.value }))
                      }
                      rows={3}
                    />
                    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                      <button style={s.resolveBtn} onClick={() => resolve(e.id)}>
                        Resolve
                      </button>
                      <button
                        style={s.cancelBtn}
                        onClick={() => setResponding((p) => ({ ...p, [e.id]: false }))}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    style={s.respondBtn}
                    onClick={() => setResponding((p) => ({ ...p, [e.id]: true }))}
                  >
                    Respond and Resolve
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {tab === "logs" && (
        <div>
          <p style={s.logNote}>
            Full logs stored at: <code>logs/interactions.jsonl</code> and <code>data/interactions.db</code>
          </p>
          <p style={s.logNote}>
            Query SQLite directly:
            <br />
            <code>sqlite3 data/interactions.db "SELECT * FROM interactions ORDER BY id DESC LIMIT 20;"</code>
          </p>
          <p style={s.logNote}>
            Tail live logs:
            <br />
            <code>tail -f logs/interactions.jsonl | python3 -m json.tool</code>
          </p>
          <div style={s.statGrid}>
            <div style={s.statBox}>
              <p style={s.statVal}>{stats.total}</p>
              <p style={s.statKey}>Total logged</p>
            </div>
            <div style={s.statBox}>
              <p style={s.statVal}>{stats.escalations}</p>
              <p style={s.statKey}>Total escalations</p>
            </div>
            <div style={s.statBox}>
              <p style={s.statVal}>{stats.blocked}</p>
              <p style={s.statKey}>Blocked requests</p>
            </div>
            <div style={s.statBox}>
              <p style={s.statVal}>{stats.flagged}</p>
              <p style={s.statKey}>Flagged for review</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const s = {
  page: {
    maxWidth: 1000,
    margin: "0 auto",
    padding: "24px 20px",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
  },
  loading: { textAlign: "center", padding: 60, color: "#888" },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 20,
  },
  title: { margin: 0, fontSize: 22, fontWeight: 700, color: "#1a1a2e" },
  live: {
    fontSize: 12,
    color: "#2e7d32",
    background: "#e8f5e9",
    padding: "4px 12px",
    borderRadius: 20,
  },
  tabs: {
    display: "flex",
    gap: 4,
    marginBottom: 24,
    borderBottom: "1px solid #eee",
    paddingBottom: 0,
  },
  tab: {
    padding: "8px 20px",
    border: "none",
    background: "none",
    cursor: "pointer",
    fontSize: 14,
    color: "#666",
    borderBottom: "2px solid transparent",
    marginBottom: -1,
  },
  tabActive: { color: "#1976d2", borderBottom: "2px solid #1976d2", fontWeight: 600 },
  cards: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 },
  card: {
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: 12,
    padding: "16px 20px",
    textAlign: "center",
  },
  cardVal: { margin: 0, fontSize: 28, fontWeight: 700 },
  cardLabel: { margin: "4px 0 0", fontSize: 12, color: "#888" },
  sectionTitle: { fontSize: 14, fontWeight: 600, color: "#444", margin: "24px 0 12px" },
  intentList: { display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 },
  intentRow: { display: "flex", alignItems: "center", gap: 12 },
  intentBadge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "3px 10px",
    borderRadius: 10,
    minWidth: 140,
    textAlign: "center",
  },
  barWrap: { flex: 1, height: 8, background: "#f0f0f0", borderRadius: 4, overflow: "hidden" },
  bar: { height: "100%", borderRadius: 4, transition: "width 0.3s" },
  barCount: { fontSize: 13, color: "#555", minWidth: 24, textAlign: "right" },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    padding: "8px 12px",
    background: "#f5f5f5",
    textAlign: "left",
    fontWeight: 600,
    color: "#555",
    borderBottom: "1px solid #e0e0e0",
  },
  td: {
    padding: "8px 12px",
    borderBottom: "1px solid #f0f0f0",
    color: "#333",
    verticalAlign: "middle",
  },
  empty: { textAlign: "center", padding: 40, color: "#888", fontSize: 15 },
  escCard: {
    border: "1px solid #e0e0e0",
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    background: "#fff",
  },
  escHeader: { display: "flex", alignItems: "center", gap: 12, marginBottom: 8 },
  escId: { fontSize: 12, fontWeight: 700, color: "#888" },
  escReason: { fontSize: 13, fontWeight: 600, color: "#c62828", flex: 1 },
  escTime: { fontSize: 12, color: "#aaa" },
  escSession: { fontSize: 12, color: "#888", margin: "0 0 10px" },
  histDetails: { marginBottom: 12 },
  histSummary: { fontSize: 13, color: "#666", cursor: "pointer", padding: "4px 0" },
  histBox: { marginTop: 8, display: "flex", flexDirection: "column", gap: 6 },
  histTurn: { padding: "8px 12px", borderRadius: 8, fontSize: 13, lineHeight: 1.5 },
  respondBox: { marginTop: 12 },
  textarea: {
    width: "100%",
    padding: 10,
    border: "1px solid #ddd",
    borderRadius: 8,
    fontSize: 13,
    resize: "vertical",
    boxSizing: "border-box",
  },
  resolveBtn: {
    padding: "8px 20px",
    background: "#2e7d32",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    fontSize: 13,
  },
  cancelBtn: {
    padding: "8px 16px",
    background: "#f5f5f5",
    color: "#555",
    border: "1px solid #ddd",
    borderRadius: 8,
    cursor: "pointer",
    fontSize: 13,
  },
  respondBtn: {
    padding: "8px 20px",
    background: "#1976d2",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    fontSize: 13,
  },
  logNote: {
    background: "#f5f5f5",
    padding: "10px 14px",
    borderRadius: 8,
    fontSize: 13,
    marginBottom: 12,
    lineHeight: 1.7,
  },
  statGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 },
  statBox: {
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: 10,
    padding: 14,
    textAlign: "center",
  },
  statVal: { margin: 0, fontSize: 22, fontWeight: 700, color: "#1a1a2e" },
  statKey: { margin: "4px 0 0", fontSize: 12, color: "#777" },
};
