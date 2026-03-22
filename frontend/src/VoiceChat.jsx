import { useState, useRef, useEffect } from "react";

const WS_URL = "ws://localhost:8000/api/v1/ws/voice";

export default function VoiceChat({ token, wsBase = "ws://localhost:8000" }) {

  const WS_URL = `${wsBase}/api/v1/ws/voice`;
  const [connected, setConnected]       = useState(false);
  const [aiSpeaking, setAiSpeaking]     = useState(false);
  const [partialText, setPartialText]   = useState("");
  const [conversation, setConversation] = useState([]);
  const [status, setStatus]             = useState("Click Start to begin");
  const [textInput, setTextInput]       = useState("");
  const [error, setError]               = useState("");

  const wsRef         = useRef(null);
  const audioCtxRef   = useRef(null);
  const workletRef    = useRef(null);
  const streamRef     = useRef(null);
  const audioQueueRef = useRef([]);
  const playingRef    = useRef(false);
  const bottomRef     = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation, partialText]);

  // ── WebSocket connect ──────────────────────────────────────
  const connect = async () => {
    setError("");
    const url = token ? `${WS_URL}?token=${token}` : WS_URL;
    const ws  = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = async () => {
      setConnected(true);
      setStatus("Connected — initializing mic…");
      await startMic(ws);
    };

    ws.onmessage = (e) => {
      if (typeof e.data === "string") handleMessage(JSON.parse(e.data));
    };

    ws.onerror = () => {
      setError("WebSocket error — is the backend running on port 8000?");
      setStatus("Connection failed");
    };

    ws.onclose = () => {
      setConnected(false);
      setAiSpeaking(false);
      setStatus("Disconnected");
      stopMic();
    };
  };

  const disconnect = () => {
    wsRef.current?.close();
    stopMic();
    setConnected(false);
    setAiSpeaking(false);
    setPartialText("");
  };

  // ── Handle messages from server ───────────────────────────
  const handleMessage = (msg) => {
    switch (msg.type) {

      case "partial_transcript":
        setPartialText(msg.text);
        setStatus("Listening…");
        // Interrupt if AI is currently speaking
        if (aiSpeaking && msg.text.length > 4) {
          wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
        }
        break;

      case "final_transcript":
        setPartialText("");
        setConversation((p) => [...p, { role: "user", text: msg.text }]);
        setStatus("Processing…");
        break;

      case "answer":
        setConversation((p) => [...p, { role: "bot", text: msg.text }]);
        break;

      case "tts_start":
        setAiSpeaking(true);
        setStatus("AI speaking…");
        audioQueueRef.current = [];
        playingRef.current    = false;
        break;

      case "tts_chunk":
        if (msg.audio) {
          const raw = atob(msg.audio);
          const buf = new ArrayBuffer(raw.length);
          new Uint8Array(buf).forEach((_, i, a) => { a[i] = raw.charCodeAt(i); });
          audioQueueRef.current.push(buf);
          if (!playingRef.current) playNextChunk();
        }
        break;

      case "tts_end":
      case "tts_stopped":
        setAiSpeaking(false);
        setStatus("Listening…");
        audioQueueRef.current = [];
        playingRef.current    = false;
        break;

      case "error":
        setError(msg.text || "Server error");
        setStatus("Error");
        break;

      case "pong":
        break;

      default:
        break;
    }
  };

  // ── Audio playback queue ──────────────────────────────────
  const playNextChunk = async () => {
    if (!audioQueueRef.current.length) {
      playingRef.current = false;
      return;
    }
    playingRef.current    = true;
    const ctx             = audioCtxRef.current;
    if (!ctx) { playingRef.current = false; return; }

    const buf = audioQueueRef.current.shift();
    try {
      const decoded = await ctx.decodeAudioData(buf);
      const src     = ctx.createBufferSource();
      src.buffer    = decoded;
      src.connect(ctx.destination);
      src.onended   = playNextChunk;
      src.start();
    } catch {
      playNextChunk();
    }
  };

  // ── Mic capture using AudioWorklet ────────────────────────
  const startMic = async (ws) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate:       { ideal: 16000 },
          channelCount:     1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
        },
      });
      streamRef.current = stream;

      const ctx = new AudioContext({ sampleRate: 16000 });
      audioCtxRef.current = ctx;

      // Load the worklet processor from /public/
      await ctx.audioWorklet.addModule("/pcm-processor.js");

      const workletNode = new AudioWorkletNode(ctx, "pcm-processor");
      workletRef.current = workletNode;

      // Receive PCM chunks from worklet and send to server
      workletNode.port.onmessage = (e) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(e.data); // ArrayBuffer — zero copy
        }
      };

      const source = ctx.createMediaStreamSource(stream);
      source.connect(workletNode);
      // Don't connect workletNode to destination — we don't want mic feedback

      setStatus("Listening… speak now");
    } catch (err) {
      console.error("Mic error:", err);
      setError(
        err.name === "NotAllowedError"
          ? "Microphone access denied — please allow mic in browser settings"
          : `Mic error: ${err.message}`
      );
      setStatus("Mic failed");
    }
  };

  const stopMic = () => {
    workletRef.current?.port.close();
    workletRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    audioCtxRef.current?.close();
    workletRef.current  = null;
    streamRef.current   = null;
    audioCtxRef.current = null;
  };

  // ── Text input fallback ───────────────────────────────────
  const sendTextInput = () => {
    const text = textInput.trim();
    if (!text || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: "text_input", text }));
    setConversation((p) => [...p, { role: "user", text }]);
    setTextInput("");
    setStatus("Processing…");
  };

  // ── Interrupt button ───────────────────────────────────────
  const interrupt = () => {
    wsRef.current?.send(JSON.stringify({ type: "interrupt" }));
    setAiSpeaking(false);
    setStatus("Listening…");
  };

  // ── UI ─────────────────────────────────────────────────────
  return (
    <div style={s.container}>

      {/* Status bar */}
      <div style={s.statusBar}>
        <div style={{
          ...s.dot,
          background: !connected      ? "#9e9e9e"
                    : aiSpeaking      ? "#ff9800"
                    : status.includes("Processing") ? "#1976d2"
                    : "#43a047",
        }} />
        <span style={s.statusText}>{status}</span>
        {connected && aiSpeaking && (
          <span style={s.waveAnim}>▁▂▄▂▁▃▅▃▁</span>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div style={s.errorBanner}>
          ⚠️ {error}
          <button style={s.errorClose} onClick={() => setError("")}>✕</button>
        </div>
      )}

      {/* Conversation */}
      <div style={s.chat}>
        {conversation.length === 0 && !connected && (
          <div style={s.hint}>
            <p style={s.hintTitle}>🎙️ Hands-free Voice Chat</p>
            <p style={s.hintSub}>Click Start — then just speak. No button holding needed.</p>
            <div style={s.featureList}>
              <span style={s.featureTag}>✓ Continuous listening</span>
              <span style={s.featureTag}>✓ Interruption detection</span>
              <span style={s.featureTag}>✓ Neural TTS response</span>
            </div>
          </div>
        )}

        {conversation.length === 0 && connected && (
          <p style={s.listenHint}>Listening… ask me anything about banking</p>
        )}

        {conversation.map((m, i) => (
          <div key={i} style={m.role === "user" ? s.userRow : s.botRow}>
            {m.role === "bot" && <span style={s.botAvatar}>🏦</span>}
            <div style={m.role === "user" ? s.userBubble : s.botBubble}>
              {m.text}
            </div>
          </div>
        ))}

        {/* Live partial transcript */}
        {partialText && (
          <div style={s.userRow}>
            <div style={{ ...s.userBubble, opacity: 0.55, fontStyle: "italic" }}>
              {partialText}▋
            </div>
          </div>
        )}

        {/* AI speaking indicator */}
        {aiSpeaking && (
          <div style={s.botRow}>
            <span style={s.botAvatar}>🏦</span>
            <div style={{ ...s.botBubble, ...s.speakingBubble }}>
              <span style={s.pulse}>●</span>
              <span style={s.pulse2}>●</span>
              <span style={s.pulse3}>●</span>
            </div>
          </div>
        )}

        {/* Processing indicator */}
        {status === "Processing…" && !aiSpeaking && (
          <div style={s.botRow}>
            <span style={s.botAvatar}>🏦</span>
            <div style={s.botBubble}>
              <span style={{ color: "#999", fontSize: 13 }}>Thinking…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Text input fallback */}
      {connected && (
        <div style={s.textRow}>
          <input
            style={s.textInput}
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendTextInput()}
            placeholder="Or type here…"
          />
          <button style={s.sendBtn} onClick={sendTextInput}>Send</button>
        </div>
      )}

      {/* Main controls */}
      <div style={s.controls}>
        {!connected ? (
          <button style={s.startBtn} onClick={connect}>
            🎙️ Start Voice Session
          </button>
        ) : (
          <>
            {aiSpeaking && (
              <button style={s.interruptBtn} onClick={interrupt}>
                ✋ Interrupt
              </button>
            )}
            <button style={s.stopBtn} onClick={disconnect}>
              ⏹ End Session
            </button>
          </>
        )}
      </div>

      <style>{`
        @keyframes blink  { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes blink2 { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes blink3 { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes wave   { 0%,100%{opacity:.4} 50%{opacity:1} }
      `}</style>
    </div>
  );
}

const s = {
  container:    { maxWidth: 640, margin: "0 auto", padding: "20px 16px", fontFamily: "'Segoe UI', system-ui, sans-serif", height: "calc(100vh - 60px)", display: "flex", flexDirection: "column", boxSizing: "border-box" },
  statusBar:    { display: "flex", alignItems: "center", gap: 8, marginBottom: 12, padding: "8px 14px", background: "#f5f5f5", borderRadius: 20 },
  dot:          { width: 10, height: 10, borderRadius: "50%", flexShrink: 0, transition: "background 0.3s" },
  statusText:   { fontSize: 13, color: "#555", flex: 1 },
  waveAnim:     { fontSize: 13, color: "#ff9800", letterSpacing: 2, animation: "wave 1s ease-in-out infinite" },
  errorBanner:  { display: "flex", alignItems: "center", justifyContent: "space-between", background: "#fff3e0", border: "1px solid #ffcc80", borderRadius: 8, padding: "8px 12px", marginBottom: 10, fontSize: 13, color: "#e65100" },
  errorClose:   { background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "#e65100" },
  chat:         { flex: 1, overflowY: "auto", padding: "8px 0", marginBottom: 8 },
  hint:         { textAlign: "center", paddingTop: 50 },
  hintTitle:    { fontSize: 20, fontWeight: 600, color: "#1a1a2e", margin: "0 0 8px" },
  hintSub:      { fontSize: 14, color: "#777", margin: "0 0 20px" },
  featureList:  { display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" },
  featureTag:   { background: "#e8f5e9", color: "#2e7d32", padding: "4px 12px", borderRadius: 12, fontSize: 12, fontWeight: 500 },
  listenHint:   { textAlign: "center", color: "#aaa", marginTop: 40, fontSize: 14, fontStyle: "italic" },
  userRow:      { display: "flex", justifyContent: "flex-end", marginBottom: 10 },
  botRow:       { display: "flex", alignItems: "flex-end", gap: 8, marginBottom: 10 },
  botAvatar:    { fontSize: 18, marginBottom: 2 },
  userBubble:   { background: "#1976d2", color: "#fff", padding: "10px 14px", borderRadius: "18px 18px 4px 18px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5 },
  botBubble:    { background: "#f5f5f5", color: "#1a1a2e", padding: "10px 14px", borderRadius: "4px 18px 18px 18px", maxWidth: "75%", fontSize: 14, lineHeight: 1.5 },
  speakingBubble: { display: "flex", gap: 6, alignItems: "center", padding: "14px 18px" },
  pulse:        { fontSize: 18, color: "#1976d2", animation: "blink 1.2s ease-in-out infinite" },
  pulse2:       { fontSize: 18, color: "#1976d2", animation: "blink2 1.2s ease-in-out infinite 0.2s" },
  pulse3:       { fontSize: 18, color: "#1976d2", animation: "blink3 1.2s ease-in-out infinite 0.4s" },
  textRow:      { display: "flex", gap: 8, marginBottom: 8 },
  textInput:    { flex: 1, padding: "10px 14px", border: "1px solid #ddd", borderRadius: 20, fontSize: 13, outline: "none", background: "#fafafa" },
  sendBtn:      { padding: "10px 18px", background: "#1976d2", color: "#fff", border: "none", borderRadius: 20, cursor: "pointer", fontSize: 13 },
  controls:     { display: "flex", gap: 10, paddingTop: 8, borderTop: "1px solid #eee" },
  startBtn:     { flex: 1, padding: "14px", background: "#2e7d32", color: "#fff", border: "none", borderRadius: 24, fontSize: 15, fontWeight: 600, cursor: "pointer" },
  stopBtn:      { flex: 1, padding: "14px", background: "#d32f2f", color: "#fff", border: "none", borderRadius: 24, fontSize: 15, fontWeight: 600, cursor: "pointer" },
  interruptBtn: { padding: "14px 20px", background: "#ff9800", color: "#fff", border: "none", borderRadius: 24, fontSize: 14, fontWeight: 500, cursor: "pointer" },
};