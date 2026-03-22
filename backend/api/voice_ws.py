import ssl, certifi, os
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
os.environ["SSL_CERT_FILE"]      = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from RealtimeSTT import AudioToTextRecorder
from RealtimeTTS import TextToAudioStream, KokoroEngine
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from rag.retriever import query_rag, format_docs
from rag.embedder import get_vectorstore
from guardrails.input_guard import check_input
from agent.intent import classify_intent, BLOCKED_INTENTS, BLOCKED_RESPONSES
from agent.tools import send_email_statement, fetch_account_summary, escalate_to_human, request_callback
from db.pg_logger import log_interaction_pg as log_interaction
import asyncio, json, base64, threading, config, uuid

router = APIRouter()

# ── Tool selection prompt ─────────────────────────────────────
TOOL_PROMPT = """You are a banking action classifier.
Reply with ONLY the tool name.

Tools:
- send_email_statement
- fetch_account_summary
- escalate_to_human
- request_callback
- apply_for_loan
- none

Rules:
- Any mention of loan, lakh loan, apply loan = apply_for_loan
- Balance, account details = fetch_account_summary
- Statement, email statement = send_email_statement
- Human, agent, escalate = escalate_to_human
- Callback, call me = request_callback

Message: {message}
Tool:"""

# ── LLM ──────────────────────────────────────────────────────
llm = ChatGroq(model=config.MODEL_NAME, temperature=0.1, groq_api_key=config.GROQ_API_KEY)

# ── TTS ───────────────────────────────────────────────────────
print("[VoiceWS] Initializing TTS engine...")
try:
    tts_engine = KokoroEngine()
    tts_stream = TextToAudioStream(tts_engine)
    print("[VoiceWS] TTS engine ready.")
except Exception as e:
    print(f"[VoiceWS] TTS engine failed: {e}")
    tts_engine = None
    tts_stream = None

# ── STT ───────────────────────────────────────────────────────
print("[VoiceWS] Initializing RealtimeSTT recorder...")
try:
    recorder = AudioToTextRecorder(
        use_microphone=False,
        model="base.en",
        realtime_model_type="tiny.en",
        language="en",
        silero_sensitivity=0.4,
        webrtc_sensitivity=3,
        post_speech_silence_duration=0.6,
        min_length_of_recording=0.5,
        min_gap_between_recordings=0,
        enable_realtime_transcription=True,
        realtime_processing_pause=0.05,
        beam_size=5,
        beam_size_realtime=3,
        initial_prompt=(
            "Banking conversation. Terms: KYC, NEFT, IMPS, RTGS, UPI, "
            "Aadhaar, PAN card, savings account, fixed deposit, EMI, loan."
        ),
        spinner=False,
        no_log_file=True,
    )
    print("[VoiceWS] Recorder ready.")
except Exception as e:
    print(f"[VoiceWS] Recorder failed: {e}")
    recorder = None

# ── Sync helpers for async memory (called from sync thread) ──
def run_async(coro, loop: asyncio.AbstractEventLoop | None = None):
    """Run an async coroutine from a sync context safely."""
    try:
        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=5)

        try:
            running_loop = asyncio.get_running_loop()
            return running_loop.run_until_complete(coro)
        except RuntimeError:
            # Called from a non-async thread without a loop.
            return asyncio.run(coro)
    except Exception as e:
        print(f"[VoiceWS] run_async error: {e}")
        try:
            coro.close()
        except Exception:
            pass
        return None

def add_turn_sync(session_id, role, content, loop: asyncio.AbstractEventLoop | None = None):
    from agent.memory import add_turn
    run_async(add_turn(session_id, role, content), loop=loop)

def get_context_sync(session_id, loop: asyncio.AbstractEventLoop | None = None):
    from agent.memory import get_context_string
    return run_async(get_context_string(session_id), loop=loop) or ""

def get_history_sync(session_id, loop: asyncio.AbstractEventLoop | None = None):
    from agent.memory import get_history
    return run_async(get_history(session_id), loop=loop) or []

def log_interaction_sync(session_id, question, intent, answer, loop: asyncio.AbstractEventLoop | None = None, **kwargs):
    run_async(log_interaction(
        session_id=session_id, question=question,
        intent=intent, answer=answer, **kwargs
    ), loop=loop)

# ── Route action (sync, no async DB calls) ───────────────────
def route_action_sync(message: str, session_id: str, user: dict, history: list) -> dict | None:
    """Select and execute tool. Fully synchronous."""
    prompt = ChatPromptTemplate.from_template(TOOL_PROMPT)
    chain  = prompt | llm
    result = chain.invoke({"message": message})
    tool   = result.content.strip().lower()
    print(f"[VoiceWS] Tool selected: {tool}")

    if tool == "send_email_statement":
        email = user.get("email") if user else None
        return send_email_statement(session_id, email=email)
    elif tool == "fetch_account_summary":
        return fetch_account_summary(session_id)
    elif tool == "escalate_to_human":
        return escalate_to_human(session_id, reason=message, conversation_history=history)
    elif tool == "request_callback":
        return request_callback(session_id)
    elif tool == "apply_for_loan":
        return {
            "success": True,
            "message": "I'd be happy to help you apply for a loan! Please use the loan application feature in the main chat for a step-by-step guided process.",
            "data": {}
        }
    return None

# ── Generate answer (sync, runs in thread) ───────────────────
def generate_answer_sync(
    question: str,
    session_id: str,
    user: dict,
    loop: asyncio.AbstractEventLoop | None = None,
) -> str:
    """Full pipeline — sync version for voice thread."""

    # Layer 1: input guard
    guard = check_input(question)
    if not guard["safe"]:
        return guard["response"]

    # Layer 2: intent
    intent = classify_intent(question)
    add_turn_sync(session_id, "user", question, loop=loop)
    print(f"[VoiceWS] Intent: {intent} | query: {question[:50]}")

    if intent in BLOCKED_INTENTS:
        return BLOCKED_RESPONSES[intent]

    if intent == "CHITCHAT":
        return "Hello! I am your banking assistant. How can I help you today?"

    # Layer 3: ACTION_REQUEST → tool
    if intent == "ACTION_REQUEST":
        history = get_history_sync(session_id, loop=loop)
        result  = route_action_sync(question, session_id, user, history)
        if result:
            answer = result["message"]
            add_turn_sync(session_id, "assistant", answer, loop=loop)
            log_interaction_sync(
                session_id=session_id, question=question,
                intent=intent, answer=answer,
                tool_used=result.get("data", {}).get("ref_number"),
                loop=loop,
            )
            return answer
        fallback = "I understand you want to perform an action. Please use the main chat or visit your nearest branch."
        add_turn_sync(session_id, "assistant", fallback, loop=loop)
        return fallback

    # Layer 4: INFO_QUERY → RAG
    try:
        history_ctx = get_context_sync(session_id, loop=loop)
        result      = query_rag(question, history_context=history_ctx)
        answer      = result["answer"]
        add_turn_sync(session_id, "assistant", answer, loop=loop)
        log_interaction_sync(
            session_id=session_id, question=question,
            intent=intent, answer=answer,
            num_chunks=result["num_chunks_retrieved"],
            sources=result["sources"],
            loop=loop,
        )
        return answer
    except Exception as e:
        print(f"[VoiceWS] RAG error: {e}")
        return "I am having trouble accessing the knowledge base right now. Please try again."

# ── WebSocket endpoint ────────────────────────────────────────
@router.websocket("/ws/voice")
async def voice_websocket(ws: WebSocket):
    await ws.accept()
    session_id = str(uuid.uuid4())
    print(f"[VoiceWS] Connected | session={session_id[:8]}")

    if not recorder:
        await ws.send_json({"type": "error", "text": "Voice recorder not available."})
        await ws.close()
        return

    abort_flag = {"value": False}
    loop       = asyncio.get_event_loop()
    running    = {"value": True}
    user_info  = {"data": {}}

    # ── Try to get user from token ────────────────────────────
    try:
        from auth.auth_handler import decode_token
        token = ws.query_params.get("token")
        if token:
            payload = decode_token(token)
            user_info["data"] = payload
    except Exception:
        pass

    # ── STT callbacks ─────────────────────────────────────────
    def on_partial(text: str):
        asyncio.run_coroutine_threadsafe(
            ws.send_json({"type": "partial_transcript", "text": text}), loop
        )

    def on_final(text: str):
        """Runs in recorder background thread — all sync."""
        abort_flag["value"] = False

        # Send transcript
        asyncio.run_coroutine_threadsafe(
            ws.send_json({"type": "final_transcript", "text": text}), loop
        )

        # Generate answer (sync)
        try:
            answer = generate_answer_sync(text, session_id, user_info["data"], loop=loop)
        except Exception as e:
            print(f"[VoiceWS] Answer error: {e}")
            answer = "Sorry, I could not process that. Please try again."

        # Send text answer
        asyncio.run_coroutine_threadsafe(
            ws.send_json({"type": "answer", "text": answer}), loop
        )

        # TTS
        if tts_stream and running["value"]:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "tts_start"}), loop
            )

            def tts_chunk(chunk: bytes):
                if abort_flag["value"] or not running["value"]:
                    tts_stream.stop()
                    return
                b64 = base64.b64encode(chunk).decode()
                asyncio.run_coroutine_threadsafe(
                    ws.send_json({"type": "tts_chunk", "audio": b64}), loop
                )

            try:
                tts_stream.feed(answer)
                tts_stream.play(on_audio_chunk=tts_chunk, muted=True)
            except Exception as e:
                print(f"[VoiceWS] TTS error: {e}")

        if running["value"]:
            asyncio.run_coroutine_threadsafe(
                ws.send_json({"type": "tts_end"}), loop
            )

    recorder.on_realtime_transcription_update = on_partial

    # ── Recorder loop in background thread ───────────────────
    def recorder_loop():
        while running["value"]:
            try:
                recorder.text(on_final)
            except Exception as e:
                print(f"[VoiceWS] Recorder error: {e}")
                break

    rec_thread = threading.Thread(target=recorder_loop, daemon=True)
    rec_thread.start()

    # ── WebSocket receive loop ────────────────────────────────
    try:
        while True:
            msg = await ws.receive()

            if "bytes" in msg and msg["bytes"]:
                recorder.feed_audio(msg["bytes"])

            elif "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue

                t = data.get("type")

                if t == "interrupt":
                    abort_flag["value"] = True
                    if tts_stream:
                        tts_stream.stop()
                    await ws.send_json({"type": "tts_stopped"})
                    print(f"[VoiceWS] Interrupted | session={session_id[:8]}")

                elif t == "text_input":
                    text = data.get("text", "").strip()
                    if text:
                        threading.Thread(target=on_final, args=(text,), daemon=True).start()

                elif t == "ping":
                    await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        print(f"[VoiceWS] Disconnected | session={session_id[:8]}")
    except Exception as e:
        if "disconnect" not in str(e).lower():
            print(f"[VoiceWS] Error: {e}")
    finally:
        running["value"] = False
        abort_flag["value"] = True
        recorder.on_realtime_transcription_update = None
        if tts_stream:
            try:
                tts_stream.stop()
            except Exception:
                pass
        print(f"[VoiceWS] Cleaned up | session={session_id[:8]}")