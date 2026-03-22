import { useState, useRef, useEffect } from "react";
import axios from "axios";
import AdminDashboard from "./AdminDashboard.jsx";
import VoiceChat from "./VoiceChat.jsx";

const API = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : "http://localhost:8000/api/v1";

const WS_BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace("https://", "wss://").replace("http://", "ws://")
  : "ws://localhost:8000";

// ── Design tokens ──────────────────────────────────────────────
const T = {
  blue:       "#1565C0",
  blueSoft:   "#E8F0FE",
  blueLight:  "#BBDEFB",
  dark:       "#0D1117",
  surface:    "#F8FAFC",
  border:     "#E2E8F0",
  borderMid:  "#CBD5E1",
  text:       "#1E293B",
  muted:      "#64748B",
  hint:       "#94A3B8",
  green:      "#16A34A",
  greenSoft:  "#DCFCE7",
  red:        "#DC2626",
  redSoft:    "#FEE2E2",
  amber:      "#D97706",
  amberSoft:  "#FEF3C7",
  purple:     "#7C3AED",
  purpleSoft: "#EDE9FE",
  white:      "#FFFFFF",
};

// ── Loan Chat Modal ─────────────────────────────────────────────
function LoanChatModal({ onClose, token, sessionId }) {
  const [messages, setMessages] = useState([{
    role: "bot",
    text: "Welcome! I'll guide you through your loan application step by step.\n\nWhat type of loan are you looking for?",
  }]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [step, setStep]       = useState(0);
  const bottomRef             = useRef(null);
  const authHeaders           = token ? { Authorization: `Bearer ${token}` } : {};

  const loanTypes = ["Personal Loan", "Home Loan", "Car Loan", "Education Loan", "Gold Loan"];
  const steps     = ["Type", "Amount", "Income", "Purpose", "Employment", "Confirm", "Done"];

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput("");
    setMessages((p) => [...p, { role: "user", text: q }]);
    setLoading(true);
    setStep((s) => Math.min(s + 1, 6));
    try {
      const res = await axios.post(`${API}/chat`, { question: q, session_id: sessionId }, { headers: authHeaders });
      setMessages((p) => [...p, { role: "bot", text: res.data.answer, ref: res.data.tool_used }]);
    } catch {
      setMessages((p) => [...p, { role: "bot", text: "Something went wrong. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(15,23,42,0.6)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:1000, padding:"16px" }}>
      <div style={{ background:T.white, borderRadius:"20px", width:"min(560px,100%)", height:"min(680px,90vh)", display:"flex", flexDirection:"column", overflow:"hidden", border:`1px solid ${T.border}` }}>

        {/* Header */}
        <div style={{ background:T.dark, padding:"18px 20px", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <div style={{ display:"flex", alignItems:"center", gap:"12px" }}>
            <div style={{ width:"36px", height:"36px", borderRadius:"10px", background:"#1E40AF", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"16px" }}>💳</div>
            <div>
              <p style={{ margin:0, fontWeight:600, fontSize:"15px", color:T.white }}>Loan Application</p>
              <p style={{ margin:0, fontSize:"12px", color:"#94A3B8" }}>AI-guided • 5 minutes</p>
            </div>
          </div>
          <button onClick={onClose} style={{ background:"rgba(255,255,255,0.1)", border:"none", borderRadius:"8px", width:"32px", height:"32px", color:T.white, cursor:"pointer", fontSize:"16px", display:"flex", alignItems:"center", justifyContent:"center" }}>✕</button>
        </div>

        {/* Progress */}
        <div style={{ padding:"12px 20px", background:"#F8FAFC", borderBottom:`1px solid ${T.border}` }}>
          <div style={{ display:"flex", gap:"4px" }}>
            {steps.map((s, i) => (
              <div key={i} style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", gap:"4px" }}>
                <div style={{ height:"3px", borderRadius:"2px", width:"100%", background: i <= step ? T.blue : T.border, transition:"background 0.3s" }} />
                <span style={{ fontSize:"9px", color: i <= step ? T.blue : T.hint, fontWeight: i <= step ? 600 : 400 }}>{s}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex:1, overflowY:"auto", padding:"16px", display:"flex", flexDirection:"column", gap:"10px" }}>
          {messages.map((m, i) => (
            <div key={i} style={{ display:"flex", justifyContent: m.role==="user" ? "flex-end" : "flex-start", alignItems:"flex-end", gap:"8px" }}>
              {m.role === "bot" && (
                <div style={{ width:"28px", height:"28px", borderRadius:"8px", background:T.blueSoft, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"14px", flexShrink:0 }}>🏦</div>
              )}
              <div style={{
                background: m.role==="user" ? T.blue : T.white,
                color: m.role==="user" ? T.white : T.text,
                padding:"10px 14px",
                borderRadius: m.role==="user" ? "18px 18px 4px 18px" : "4px 18px 18px 18px",
                maxWidth:"80%",
                fontSize:"14px",
                lineHeight:1.6,
                whiteSpace:"pre-wrap",
                border: m.role==="bot" ? `1px solid ${T.border}` : "none",
              }}>
                {m.text}
                {m.ref && <p style={{ margin:"6px 0 0", fontSize:"11px", color:"#16A34A", fontWeight:600 }}>✓ Ref: {m.ref}</p>}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display:"flex", alignItems:"flex-end", gap:"8px" }}>
              <div style={{ width:"28px", height:"28px", borderRadius:"8px", background:T.blueSoft, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"14px" }}>🏦</div>
              <div style={{ background:T.white, border:`1px solid ${T.border}`, borderRadius:"4px 18px 18px 18px", padding:"12px 16px" }}>
                <div style={{ display:"flex", gap:"4px" }}>
                  {[0,1,2].map(i => <div key={i} style={{ width:"6px", height:"6px", borderRadius:"50%", background:T.hint, animation:`bounce 1s ${i*0.2}s infinite` }} />)}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick buttons (first message only) */}
        {messages.length === 1 && (
          <div style={{ padding:"0 16px 12px", display:"flex", flexWrap:"wrap", gap:"8px" }}>
            {loanTypes.map(t => (
              <button key={t} onClick={() => send(t)} style={{ background:T.blueSoft, border:`1px solid ${T.blueLight}`, borderRadius:"20px", padding:"7px 14px", fontSize:"13px", color:T.blue, cursor:"pointer", fontWeight:500 }}>{t}</button>
            ))}
          </div>
        )}

        {/* Input */}
        <div style={{ padding:"12px 16px", borderTop:`1px solid ${T.border}`, background:T.white, display:"flex", gap:"8px" }}>
          <input
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key==="Enter" && send()}
            placeholder="Type your answer…" disabled={loading}
            style={{ flex:1, padding:"10px 14px", border:`1.5px solid ${T.border}`, borderRadius:"12px", fontSize:"14px", outline:"none", background:T.surface, color:T.text }}
          />
          <button onClick={() => send()} disabled={loading} style={{ padding:"10px 20px", background:T.blue, color:T.white, border:"none", borderRadius:"12px", cursor:"pointer", fontSize:"14px", fontWeight:500 }}>
            Send
          </button>
        </div>
      </div>
      <style>{`@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}`}</style>
    </div>
  );
}

// ── Intent & confidence badge configs ──────────────────────────
const INTENT_STYLES = {
  INFO_QUERY:       { bg:"#EFF6FF", color:"#1D4ED8", label:"Info" },
  ACTION_REQUEST:   { bg:"#FFF7ED", color:"#C2410C", label:"Action" },
  CHITCHAT:         { bg:"#FAF5FF", color:"#6D28D9", label:"Chat" },
  SENSITIVE:        { bg:"#FFF1F2", color:"#BE123C", label:"Blocked" },
  FRAUD:            { bg:"#FFF1F2", color:"#BE123C", label:"Fraud" },
  OTP_REQUEST:      { bg:"#FFF1F2", color:"#BE123C", label:"Blocked" },
  PASSWORD_REQUEST: { bg:"#FFF1F2", color:"#BE123C", label:"Blocked" },
  PROMPT_INJECTION: { bg:"#FFF1F2", color:"#BE123C", label:"Blocked" },
  FRAUD_ATTEMPT:    { bg:"#FFF1F2", color:"#BE123C", label:"Fraud" },
  TRANSFER_REQUEST: { bg:"#FFFBEB", color:"#B45309", label:"Transfer" },
};
const CONF_STYLES = {
  HIGH:   { bg:"#F0FDF4", color:"#15803D", label:"✓ High" },
  MEDIUM: { bg:"#FFFBEB", color:"#B45309", label:"~ Medium" },
  LOW:    { bg:"#FFF1F2", color:"#BE123C", label:"⚠ Low" },
};

// ── Main App ────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages]           = useState([]);
  const [input, setInput]                 = useState("");
  const [loading, setLoading]             = useState(false);
  const [recording, setRecording]         = useState(false);
  const [voiceMode, setVoiceMode]         = useState(false);
  const [streamMode, setStreamMode]       = useState(true);
  const [showAdmin, setShowAdmin]         = useState(false);
  const [showVoice, setShowVoice]         = useState(false);
  const [showLoan, setShowLoan]           = useState(false);
  const [sidebarOpen, setSidebarOpen]     = useState(false);
  const [token, setToken]                 = useState(() => localStorage.getItem("auth_token") || null);
  const [user, setUser]                   = useState(() => { const u = localStorage.getItem("auth_user"); return u ? JSON.parse(u) : null; });
  const [loginForm, setLoginForm]         = useState({ username:"", password:"" });
  const [registerForm, setRegisterForm]   = useState({ username:"", email:"", full_name:"", password:"" });
  const [showRegister, setShowRegister]   = useState(false);
  const [loginError, setLoginError]       = useState("");
  const [registerError, setRegisterError] = useState("");
  const [registerSuccess, setRegisterSuccess] = useState("");
  const [sessionId, setSessionId]         = useState(() => localStorage.getItem("chat_session_id") || null);

  const bottomRef        = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef        = useRef([]);
  const authHeaders      = token ? { Authorization:`Bearer ${token}` } : {};

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:"smooth" }); }, [messages]);

  // ── Auth ─────────────────────────────────────────────────────
  const login = async () => {
    setLoginError("");
    try {
      const res = await axios.post(`${API}/auth/login`, loginForm);
      const { access_token, username, full_name, role, chat_session_id } = res.data;
      const userData = { username, full_name, role };
      setToken(access_token);
      setUser(userData);
      localStorage.setItem("auth_token", access_token);
      localStorage.setItem("auth_user", JSON.stringify(userData));
      if (chat_session_id) {
        setSessionId(chat_session_id);
        localStorage.setItem("chat_session_id", chat_session_id);
        try {
          const h = await axios.get(`${API}/history/${chat_session_id}`, { headers:{ Authorization:`Bearer ${access_token}` } });
          const restored = (h.data.history || []).map(t => ({ role:t.role==="user"?"user":"bot", text:t.content, intent:null, sources:[], chunks:0, blocked:false, tool_used:null, escalated:false, confidence_label:null }));
          if (restored.length) setMessages(restored);
        } catch {}
      }
    } catch (err) { setLoginError(err.response?.data?.detail || "Login failed."); }
  };

  const register = async () => {
    setRegisterError("");
    try {
      await axios.post(`${API}/auth/register`, registerForm);
      setRegisterSuccess("Account created! Sign in now.");
      setShowRegister(false);
      setLoginForm({ username:registerForm.username, password:"" });
    } catch (err) { setRegisterError(err.response?.data?.detail || "Registration failed."); }
  };

  const logout = () => {
    setToken(null); setUser(null); setMessages([]);
    setShowVoice(false); setShowAdmin(false); setShowLoan(false);
    localStorage.removeItem("auth_token"); localStorage.removeItem("auth_user");
  };

  // ── Login screen ──────────────────────────────────────────────
  if (!token) {
    return (
      <div style={{ minHeight:"100vh", background:"#F0F4F8", display:"flex", alignItems:"center", justifyContent:"center", fontFamily:"system-ui,sans-serif", padding:"16px" }}>
        <div style={{ background:T.white, borderRadius:"24px", width:"min(420px,100%)", overflow:"hidden", border:`1px solid ${T.border}` }}>
          {/* Card top accent */}
          <div style={{ background:T.dark, padding:"32px 32px 24px", textAlign:"center" }}>
            <div style={{ width:"56px", height:"56px", borderRadius:"16px", background:"#1E40AF", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"26px", margin:"0 auto 12px" }}>🏦</div>
            <h2 style={{ margin:"0 0 4px", color:T.white, fontWeight:700, fontSize:"22px" }}>Banking Assistant</h2>
            <p style={{ margin:0, color:"#94A3B8", fontSize:"14px" }}>{showRegister ? "Create your account" : "Sign in to continue"}</p>
          </div>

          <div style={{ padding:"28px 32px 32px" }}>
            {!showRegister ? (
              <>
                {registerSuccess && <div style={{ background:T.greenSoft, border:`1px solid #BBF7D0`, borderRadius:"10px", padding:"10px 14px", marginBottom:"16px", fontSize:"13px", color:T.green }}>{registerSuccess}</div>}
                <div style={{ marginBottom:"14px" }}>
                  <label style={{ display:"block", fontSize:"13px", fontWeight:500, color:T.muted, marginBottom:"6px" }}>Username</label>
                  <input style={iStyle} placeholder="customer1" value={loginForm.username}
                    onChange={e => setLoginForm(p => ({...p, username:e.target.value}))}
                    onKeyDown={e => e.key==="Enter" && login()} />
                </div>
                <div style={{ marginBottom:"20px" }}>
                  <label style={{ display:"block", fontSize:"13px", fontWeight:500, color:T.muted, marginBottom:"6px" }}>Password</label>
                  <input style={iStyle} type="password" placeholder="••••••••" value={loginForm.password}
                    onChange={e => setLoginForm(p => ({...p, password:e.target.value}))}
                    onKeyDown={e => e.key==="Enter" && login()} />
                </div>
                {loginError && <div style={{ background:T.redSoft, border:`1px solid #FECACA`, borderRadius:"10px", padding:"10px 14px", marginBottom:"16px", fontSize:"13px", color:T.red }}>{loginError}</div>}
                <button onClick={login} style={{ width:"100%", padding:"13px", background:T.blue, color:T.white, border:"none", borderRadius:"12px", fontSize:"15px", fontWeight:600, cursor:"pointer", marginBottom:"12px" }}>Sign In</button>
                <button onClick={() => setShowRegister(true)} style={{ width:"100%", padding:"11px", background:"transparent", color:T.muted, border:`1px solid ${T.border}`, borderRadius:"12px", fontSize:"14px", cursor:"pointer", marginBottom:"20px" }}>Create an account</button>
                <div style={{ background:T.surface, borderRadius:"12px", padding:"14px 16px" }}>
                  <p style={{ margin:"0 0 8px", fontSize:"12px", fontWeight:600, color:T.muted }}>Demo credentials</p>
                  <div style={{ display:"flex", gap:"8px" }}>
                    {[["customer1","password123"],["admin","admin123"]].map(([u,p]) => (
                      <button key={u} onClick={() => setLoginForm({username:u,password:p})} style={{ flex:1, padding:"8px", background:T.white, border:`1px solid ${T.border}`, borderRadius:"8px", fontSize:"12px", color:T.text, cursor:"pointer", fontFamily:"monospace" }}>{u}</button>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <>
                {[["Full name","text","Your full name","full_name"],["Username","text","username","username"],["Email","email","email@example.com","email"],["Password","password","••••••••","password"]].map(([label,type,ph,key]) => (
                  <div key={key} style={{ marginBottom:"14px" }}>
                    <label style={{ display:"block", fontSize:"13px", fontWeight:500, color:T.muted, marginBottom:"6px" }}>{label}</label>
                    <input style={iStyle} type={type} placeholder={ph} value={registerForm[key]}
                      onChange={e => setRegisterForm(p => ({...p,[key]:e.target.value}))}
                      onKeyDown={e => e.key==="Enter" && register()} />
                  </div>
                ))}
                {registerError && <div style={{ background:T.redSoft, border:`1px solid #FECACA`, borderRadius:"10px", padding:"10px 14px", marginBottom:"16px", fontSize:"13px", color:T.red }}>{registerError}</div>}
                <button onClick={register} style={{ width:"100%", padding:"13px", background:T.blue, color:T.white, border:"none", borderRadius:"12px", fontSize:"15px", fontWeight:600, cursor:"pointer", marginBottom:"12px" }}>Create Account</button>
                <button onClick={() => setShowRegister(false)} style={{ width:"100%", padding:"11px", background:"transparent", color:T.muted, border:`1px solid ${T.border}`, borderRadius:"12px", fontSize:"14px", cursor:"pointer" }}>Back to sign in</button>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Send helpers ──────────────────────────────────────────────
  const sendMessage = async (question) => {
    const q = (question || input).trim();
    if (!q || loading) return;
    setMessages(p => [...p, { role:"user", text:q }]);
    setInput(""); setLoading(true);
    streamMode ? await sendStreaming(q) : await sendNormal(q);
  };

  const sendStreaming = async (q) => {
    const botId = Date.now();
    setMessages(p => [...p, { id:botId, role:"bot", text:"", intent:null, sources:[], chunks:0, blocked:false, tool_used:null, escalated:false, streaming:true, confidence_label:null }]);
    try {
      const res = await fetch(`${API}/chat/stream`, { method:"POST", headers:{"Content-Type":"application/json",...authHeaders}, body:JSON.stringify({ question:q, session_id:sessionId }) });
      const reader = res.body.getReader(); const decoder = new TextDecoder();
      let buffer = "", meta = null, fullAnswer = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream:true });
        const lines = buffer.split("\n"); buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim(); if (!raw) continue;
          try {
            const p = JSON.parse(raw);
            if (p.type === "meta") {
              meta = p;
              if (!sessionId && p.session_id) { setSessionId(p.session_id); localStorage.setItem("chat_session_id", p.session_id); }
              if (p.intent && p.intent !== "INFO_QUERY") { setMessages(prev => prev.filter(m => m.id !== botId)); setLoading(false); await sendNormal(q); return; }
              setMessages(prev => prev.map(m => m.id===botId ? {...m, intent:p.intent, sources:p.sources||[], chunks:p.num_chunks||0, blocked:p.blocked, confidence_label:p.confidence_label||null} : m));
            }
            if (p.type === "token") { fullAnswer += p.text; setMessages(prev => prev.map(m => m.id===botId ? {...m, text:m.text+p.text} : m)); }
            if (p.type === "done") { setMessages(prev => prev.map(m => m.id===botId ? {...m, streaming:false} : m)); if (voiceMode && meta && !meta.blocked && fullAnswer) await speakText(fullAnswer); }
          } catch {}
        }
      }
    } catch { setMessages(p => p.map(m => m.id===botId ? {...m, text:"⚠️ Error. Please try again.", streaming:false} : m)); }
    finally { setLoading(false); }
  };

  const sendNormal = async (q) => {
    try {
      const res = await axios.post(`${API}/chat`, { question:q, session_id:sessionId }, { headers:authHeaders });
      if (!sessionId && res.data.session_id) { setSessionId(res.data.session_id); localStorage.setItem("chat_session_id", res.data.session_id); }
      setMessages(p => [...p, { role:"bot", text:res.data.answer, intent:res.data.intent, sources:res.data.sources, chunks:res.data.num_chunks_retrieved, blocked:res.data.blocked, tool_used:res.data.tool_used, escalated:res.data.escalated, confidence_label:res.data.confidence_label||null }]);
      if (voiceMode && !res.data.blocked) await speakText(res.data.answer);
    } catch { setMessages(p => [...p, { role:"bot", text:"⚠️ Server error. Please try again.", intent:null, sources:[], chunks:0, blocked:false, tool_used:null, escalated:false, confidence_label:null }]); }
    finally { setLoading(false); }
  };

  const speakText = async (text) => {
    try { const res = await axios.post(`${API}/speak`, {text}, {responseType:"blob", headers:authHeaders}); new Audio(URL.createObjectURL(res.data)).play(); } catch {}
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio:{ echoCancellation:true, noiseSuppression:true, sampleRate:16000, channelCount:1 } });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = e => chunksRef.current.push(e.data);
      recorder.onstop = async () => { const blob = new Blob(chunksRef.current, {type:mimeType}); stream.getTracks().forEach(t => t.stop()); await transcribeAudio(blob); };
      recorder.start(); mediaRecorderRef.current = recorder; setRecording(true);
    } catch { alert("Microphone access denied."); }
  };

  const stopRecording = () => { mediaRecorderRef.current?.stop(); setRecording(false); };

  const transcribeAudio = async (blob) => {
    setLoading(true);
    setMessages(p => [...p, { role:"user", text:"Transcribing…", temp:true }]);
    try {
      const fd = new FormData(); fd.append("audio", blob, "recording.webm");
      const res = await axios.post(`${API}/transcribe`, fd, { headers:{"Content-Type":"multipart/form-data",...authHeaders} });
      setMessages(p => p.map(m => m.temp ? {role:"user", text:res.data.text} : m));
      await sendMessage(res.data.text);
    } catch {
      setMessages(p => p.filter(m => !m.temp));
      setMessages(p => [...p, { role:"bot", text:"Could not transcribe. Please try again.", intent:null, sources:[], chunks:0, blocked:false, tool_used:null, escalated:false, confidence_label:null }]);
      setLoading(false);
    }
  };

  const clearSession = async () => {
    if (sessionId) { try { await axios.delete(`${API}/history/${sessionId}`, {headers:authHeaders}); } catch {} }
    localStorage.removeItem("chat_session_id"); setSessionId(null); setMessages([]);
  };

  // ── Render ────────────────────────────────────────────────────
  const userInitials = user?.full_name?.split(" ").map(w => w[0]).join("").slice(0,2).toUpperCase() || "U";
  const navItems = [
    { icon: "💬", label: "Chat", action: () => { setShowVoice(false); setShowAdmin(false); } },
    { icon: "🎙️", label: "Voice Chat", action: () => { setShowAdmin(false); setShowVoice(true); } },
    { icon: "💳", label: "Apply for Loan", action: () => setShowLoan(true) },
    { icon: "⚙️", label: "Admin", action: () => { setShowVoice(false); setShowAdmin(true); } },
  ];

  return (
    <div style={{ display:"flex", height:"100vh", fontFamily:"system-ui,-apple-system,sans-serif", background:T.surface, color:T.text }}>

      {/* Loan modal */}
      {showLoan && <LoanChatModal onClose={() => setShowLoan(false)} token={token} sessionId={sessionId} />}

      {/* ── Sidebar ──────────────────────────────────────────── */}
      <div style={{ width: sidebarOpen ? "240px" : "60px", background:T.dark, display:"flex", flexDirection:"column", transition:"width 0.25s", overflow:"hidden", flexShrink:0 }}>

        {/* Logo */}
        <div style={{ padding:"16px 14px", display:"flex", alignItems:"center", gap:"10px", borderBottom:"1px solid rgba(255,255,255,0.08)", cursor:"pointer" }} onClick={() => setSidebarOpen(o => !o)}>
          <div style={{ width:"32px", height:"32px", borderRadius:"9px", background:"#1E40AF", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"16px", flexShrink:0 }}>🏦</div>
          {sidebarOpen && <span style={{ color:T.white, fontWeight:700, fontSize:"15px", whiteSpace:"nowrap" }}>Banking AI</span>}
        </div>

        {/* Nav items */}
        {navItems.map(({ icon, label, action }) => (
          <button key={label} onClick={action} style={{ display:"flex", alignItems:"center", gap:"12px", padding:"13px 14px", background:"transparent", border:"none", color:"#CBD5E1", cursor:"pointer", width:"100%", textAlign:"left", transition:"background 0.15s", borderRadius:0 }}
            onMouseEnter={e => e.currentTarget.style.background="rgba(255,255,255,0.06)"}
            onMouseLeave={e => e.currentTarget.style.background="transparent"}>
            <span style={{ fontSize:"16px", width:"32px", textAlign:"center", flexShrink:0 }}>{icon}</span>
            {sidebarOpen && <span style={{ fontSize:"14px", whiteSpace:"nowrap" }}>{label}</span>}
          </button>
        ))}

        <div style={{ flex:1 }} />

        {/* User section */}
        <div style={{ padding:"12px 14px", borderTop:"1px solid rgba(255,255,255,0.08)", display:"flex", alignItems:"center", gap:"10px" }}>
          <div style={{ width:"32px", height:"32px", borderRadius:"50%", background:"#1E40AF", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"12px", fontWeight:700, color:T.white, flexShrink:0 }}>{userInitials}</div>
          {sidebarOpen && (
            <div style={{ flex:1, minWidth:0 }}>
              <p style={{ margin:0, fontSize:"13px", fontWeight:500, color:T.white, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{user?.full_name}</p>
              <button onClick={logout} style={{ background:"none", border:"none", color:"#94A3B8", fontSize:"12px", cursor:"pointer", padding:0 }}>Sign out</button>
            </div>
          )}
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────── */}
      <div style={{ flex:1, display:"flex", flexDirection:"column", minWidth:0 }}>
        {showAdmin ? (
          <div style={{ flex:1, overflowY:"auto" }}>
            <div style={{ padding:"12px 20px", background:T.white, borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", gap:"12px" }}>
              <button onClick={() => setShowAdmin(false)} style={backBtnStyle}>← Back to chat</button>
              <span style={{ fontWeight:600, color:T.text, fontSize:"15px" }}>Admin Dashboard</span>
            </div>
            <AdminDashboard token={token} />
          </div>
        ) : showVoice ? (
          <div style={{ flex:1, display:"flex", flexDirection:"column" }}>
            <div style={{ padding:"12px 20px", background:T.white, borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", gap:"12px" }}>
              <button onClick={() => setShowVoice(false)} style={backBtnStyle}>← Back to chat</button>
              <span style={{ fontWeight:600, color:T.text, fontSize:"15px" }}>🎙️ Voice Chat</span>
            </div>
            <VoiceChat token={token} wsBase={WS_BASE} />
          </div>
        ) : (
          <>
            {/* Top bar */}
            <div style={{ padding:"12px 20px", background:T.white, borderBottom:`1px solid ${T.border}`, display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
              <div style={{ display:"flex", alignItems:"center", gap:"8px" }}>
                <div style={{ width:"8px", height:"8px", borderRadius:"50%", background:"#16A34A" }} />
                <span style={{ fontSize:"13px", color:T.muted, fontFamily:"monospace" }}>{sessionId ? sessionId.slice(0,8)+"…" : "New session"}</span>
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:"12px" }}>
                {/* Stream toggle */}
                <label style={{ display:"flex", alignItems:"center", gap:"6px", cursor:"pointer" }}>
                  <span style={{ fontSize:"12px", color:T.muted }}>Stream</span>
                  <div style={{ position:"relative", width:"36px", height:"20px" }} onClick={() => setStreamMode(s => !s)}>
                    <div style={{ position:"absolute", inset:0, borderRadius:"10px", background: streamMode ? T.blue : T.border, transition:"background 0.2s" }} />
                    <div style={{ position:"absolute", top:"2px", left: streamMode ? "18px" : "2px", width:"16px", height:"16px", borderRadius:"50%", background:T.white, transition:"left 0.2s" }} />
                  </div>
                </label>
                {/* Voice toggle */}
                <label style={{ display:"flex", alignItems:"center", gap:"6px", cursor:"pointer" }}>
                  <span style={{ fontSize:"12px", color:T.muted }}>Voice</span>
                  <div style={{ position:"relative", width:"36px", height:"20px" }} onClick={() => setVoiceMode(s => !s)}>
                    <div style={{ position:"absolute", inset:0, borderRadius:"10px", background: voiceMode ? T.blue : T.border, transition:"background 0.2s" }} />
                    <div style={{ position:"absolute", top:"2px", left: voiceMode ? "18px" : "2px", width:"16px", height:"16px", borderRadius:"50%", background:T.white, transition:"left 0.2s" }} />
                  </div>
                </label>
                {messages.length > 0 && (
                  <button onClick={clearSession} style={{ background:"transparent", border:`1px solid ${T.border}`, borderRadius:"8px", padding:"5px 10px", fontSize:"12px", color:T.muted, cursor:"pointer" }}>New chat</button>
                )}
              </div>
            </div>

            {/* Messages */}
            <div style={{ flex:1, overflowY:"auto", padding:"24px 20px" }}>
              {messages.length === 0 ? (
            <div style={{ maxWidth:"560px", margin:"40px auto", textAlign:"center" }}>
              <div style={{ width:"64px", height:"64px", borderRadius:"20px", background:T.blueSoft, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"28px", margin:"0 auto 20px" }}>🏦</div>
              <h2 style={{ margin:"0 0 8px", fontSize:"22px", fontWeight:700, color:T.text }}>How can I help you?</h2>
              <p style={{ margin:"0 0 28px", color:T.muted, fontSize:"15px", lineHeight:1.6 }}>Ask about banking services, apply for loans, or get account support.</p>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"10px", marginBottom:"16px" }}>
                {[
                  { icon:"🏛️", text:"How do I open a savings account?" },
                  { icon:"📄", text:"What are the KYC requirements?" },
                  { icon:"👤", text:"I want to talk to a human agent" },
                  { icon:"📊", text:"Send me my account statement" },
                ].map(({ icon, text }) => (
                  <button key={text} onClick={() => sendMessage(text)}
                    style={{ background:T.white, border:`1px solid ${T.border}`, borderRadius:"14px", padding:"14px", textAlign:"left", cursor:"pointer", transition:"border-color 0.15s, background 0.15s" }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = T.blue; e.currentTarget.style.background = T.blueSoft; }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.background = T.white; }}>
                    <span style={{ fontSize:"18px", display:"block", marginBottom:"6px" }}>{icon}</span>
                    <span style={{ fontSize:"13px", color:T.text, lineHeight:1.4 }}>{text}</span>
                  </button>
                ))}
              </div>
              <div style={{ display:"flex", gap:"10px", justifyContent:"center" }}>
                <button onClick={() => setShowLoan(true)} style={{ background:T.dark, color:T.white, border:"none", borderRadius:"12px", padding:"11px 20px", fontSize:"14px", cursor:"pointer", fontWeight:500 }}>💳 Apply for a loan</button>
                <button onClick={() => setShowVoice(true)} style={{ background:T.white, color:T.text, border:`1px solid ${T.border}`, borderRadius:"12px", padding:"11px 20px", fontSize:"14px", cursor:"pointer", fontWeight:500 }}>🎙️ Try voice chat</button>
              </div>
            </div>
              ) : (
            <div style={{ maxWidth:"720px", margin:"0 auto", display:"flex", flexDirection:"column", gap:"16px" }}>
              {messages.map((msg, i) => (
                <div key={i} style={{ display:"flex", justifyContent: msg.role==="user" ? "flex-end" : "flex-start", alignItems:"flex-end", gap:"10px" }}>
                  {msg.role === "bot" && (
                    <div style={{ width:"34px", height:"34px", borderRadius:"10px", background: msg.blocked ? "#FEE2E2" : T.blueSoft, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"16px", flexShrink:0, marginBottom:"2px" }}>
                      {msg.blocked ? "🛡️" : "🏦"}
                    </div>
                  )}
                  <div style={{ maxWidth:"75%" }}>
                    {/* Badges */}
                    {(msg.intent || msg.confidence_label) && (
                      <div style={{ display:"flex", gap:"6px", marginBottom:"6px", flexWrap:"wrap" }}>
                        {msg.intent && (INTENT_STYLES[msg.intent]) && (
                          <span style={{ fontSize:"10px", fontWeight:600, padding:"2px 8px", borderRadius:"6px", letterSpacing:"0.5px", textTransform:"uppercase", background: INTENT_STYLES[msg.intent]?.bg, color: INTENT_STYLES[msg.intent]?.color }}>
                            {INTENT_STYLES[msg.intent]?.label || msg.intent}
                          </span>
                        )}
                        {msg.confidence_label && msg.intent === "INFO_QUERY" && (
                          <span style={{ fontSize:"10px", fontWeight:600, padding:"2px 8px", borderRadius:"6px", background: CONF_STYLES[msg.confidence_label]?.bg, color: CONF_STYLES[msg.confidence_label]?.color }}>
                            {CONF_STYLES[msg.confidence_label]?.label}
                          </span>
                        )}
                      </div>
                    )}
                    {/* Bubble */}
                    <div style={{
                      background: msg.role==="user" ? T.blue : msg.blocked ? "#FFF1F2" : T.white,
                      color: msg.role==="user" ? T.white : T.text,
                      padding:"12px 16px",
                      borderRadius: msg.role==="user" ? "18px 18px 4px 18px" : "4px 18px 18px 18px",
                      fontSize:"14px", lineHeight:1.7, whiteSpace:"pre-wrap",
                      border: msg.role==="bot" ? `1px solid ${msg.blocked ? "#FECACA" : msg.escalated ? "#E9D5FF" : T.border}` : "none",
                    }}>
                      {msg.escalated && <p style={{ margin:"0 0 8px", fontSize:"12px", color:T.purple, fontWeight:500 }}>🚩 Escalated to human agent</p>}
                      {msg.tool_used && <p style={{ margin:"0 0 8px", fontSize:"12px", color:T.green, fontWeight:500 }}>✓ Ref: {msg.tool_used}</p>}
                      {msg.text}
                      {msg.streaming && <span style={{ color:T.blue }}>▋</span>}
                    </div>
                    {/* Actions row */}
                    {msg.role === "bot" && !msg.blocked && !msg.streaming && (
                      <div style={{ display:"flex", gap:"6px", marginTop:"6px", alignItems:"center" }}>
                        <button onClick={() => speakText(msg.text)} style={{ background:"transparent", border:`1px solid ${T.border}`, borderRadius:"8px", padding:"4px 10px", fontSize:"12px", color:T.muted, cursor:"pointer" }}>🔊</button>
                        {msg.sources?.length > 0 && (
                          <details style={{ fontSize:"12px" }}>
                            <summary style={{ color:T.muted, cursor:"pointer", userSelect:"none", listStyle:"none", padding:"4px 10px", border:`1px solid ${T.border}`, borderRadius:"8px", display:"inline-block" }}>
                              📄 {msg.chunks} sources
                            </summary>
                            <div style={{ marginTop:"6px", background:T.white, border:`1px solid ${T.border}`, borderRadius:"12px", padding:"10px 14px", display:"flex", flexDirection:"column", gap:"8px" }}>
                              {msg.sources.map((s, j) => (
                                <div key={j} style={{ fontSize:"12px" }}>
                                  <div style={{ display:"flex", alignItems:"center", gap:"6px", marginBottom:"2px" }}>
                                    <span style={{ fontWeight:500, color:T.text }}>Page {s.page}</span>
                                    {s.score !== undefined && (
                                      <span style={{ fontSize:"10px", padding:"1px 6px", borderRadius:"4px", background: s.score>0.7 ? T.greenSoft : s.score>0.4 ? T.amberSoft : T.redSoft, color: s.score>0.7 ? T.green : s.score>0.4 ? T.amber : T.red, fontWeight:600 }}>
                                        {s.score}
                                      </span>
                                    )}
                                  </div>
                                  <p style={{ margin:0, color:T.muted, lineHeight:1.4 }}>{s.preview}</p>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                  {msg.role === "user" && (
                    <div style={{ width:"34px", height:"34px", borderRadius:"50%", background:T.blue, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"12px", fontWeight:700, color:T.white, flexShrink:0, marginBottom:"2px" }}>{userInitials}</div>
                  )}
                </div>
              ))}
              {loading && !recording && !messages.some(m => m.streaming) && (
                <div style={{ display:"flex", alignItems:"flex-end", gap:"10px" }}>
                  <div style={{ width:"34px", height:"34px", borderRadius:"10px", background:T.blueSoft, display:"flex", alignItems:"center", justifyContent:"center", fontSize:"16px" }}>🏦</div>
                  <div style={{ background:T.white, border:`1px solid ${T.border}`, borderRadius:"4px 18px 18px 18px", padding:"14px 18px" }}>
                    <div style={{ display:"flex", gap:"5px" }}>
                      {[0,1,2].map(i => <div key={i} style={{ width:"7px", height:"7px", borderRadius:"50%", background:T.hint, animation:`bounce 1.2s ${i*0.25}s infinite` }} />)}
                    </div>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
              )}
            </div>

            {/* Input bar */}
            <div style={{ padding:"16px 20px", background:T.white, borderTop:`1px solid ${T.border}`, flexShrink:0 }}>
              <div style={{ maxWidth:"720px", margin:"0 auto" }}>
                <div style={{ display:"flex", gap:"10px", alignItems:"flex-end", background:T.surface, border:`1.5px solid ${recording ? T.red : loading ? T.blueLight : T.border}`, borderRadius:"16px", padding:"10px 12px", transition:"border-color 0.2s" }}>
                  <textarea
                    value={input} rows={1}
                    onChange={e => { setInput(e.target.value); e.target.style.height="auto"; e.target.style.height=Math.min(e.target.scrollHeight,120)+"px"; }}
                    onKeyDown={e => { if (e.key==="Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                    placeholder="Ask about banking services, type or use the mic…"
                    disabled={loading || recording}
                    style={{ flex:1, border:"none", background:"transparent", fontSize:"14px", resize:"none", outline:"none", lineHeight:1.5, color:T.text, maxHeight:"120px", minHeight:"24px", fontFamily:"inherit" }}
                  />
                  <div style={{ display:"flex", gap:"6px", alignItems:"center", flexShrink:0 }}>
                    <button
                      onMouseDown={startRecording} onMouseUp={stopRecording}
                      onTouchStart={startRecording} onTouchEnd={stopRecording}
                      disabled={loading && !recording}
                      style={{ width:"36px", height:"36px", borderRadius:"10px", border:"none", background: recording ? T.red : T.border, color: recording ? T.white : T.muted, cursor:"pointer", fontSize:"16px", display:"flex", alignItems:"center", justifyContent:"center", transition:"all 0.15s", transform: recording ? "scale(1.1)" : "scale(1)" }}>
                      {recording ? "⏹" : "🎤"}
                    </button>
                    <button
                      onClick={() => sendMessage()} disabled={loading || recording || !input.trim()}
                      style={{ width:"36px", height:"36px", borderRadius:"10px", border:"none", background: (loading||recording||!input.trim()) ? T.border : T.blue, color: (loading||recording||!input.trim()) ? T.muted : T.white, cursor: (loading||recording||!input.trim()) ? "not-allowed" : "pointer", fontSize:"16px", display:"flex", alignItems:"center", justifyContent:"center", transition:"all 0.15s" }}>
                      ↑
                    </button>
                  </div>
                </div>
                {recording && <p style={{ margin:"6px 0 0", fontSize:"12px", color:T.red, textAlign:"center" }}>Recording… release to send</p>}
                <p style={{ margin:"6px 0 0", fontSize:"11px", color:T.hint, textAlign:"center" }}>Enter to send · Shift+Enter for new line · Hold mic to speak</p>
              </div>
            </div>
          </>
        )}
      </div>
      <style>{`@keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}`}</style>
    </div>
  );
}

const iStyle = { width:"100%", padding:"11px 14px", border:`1.5px solid #E2E8F0`, borderRadius:"10px", fontSize:"14px", outline:"none", boxSizing:"border-box", color:"#1E293B", background:"#F8FAFC", fontFamily:"inherit" };
const backBtnStyle = { background:"transparent", border:`1px solid #E2E8F0`, borderRadius:"8px", padding:"6px 14px", fontSize:"13px", cursor:"pointer", color:"#64748B" };
