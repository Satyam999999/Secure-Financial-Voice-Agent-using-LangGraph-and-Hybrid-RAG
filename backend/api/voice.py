from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from faster_whisper import WhisperModel
from gtts import gTTS
from rag.retriever import query_rag
import io, tempfile, os

router = APIRouter()

BANKING_PROMPT = (
    "Banking assistant conversation. Terms include: "
    "savings account, current account, fixed deposit, recurring deposit, "
    "KYC, Aadhaar, PAN card, NEFT, IMPS, RTGS, UPI, net banking, "
    "mobile banking, ATM, debit card, credit card, IFSC code, "
    "loan, EMI, interest rate, balance, statement, cheque book, "
    "passbook, nominee, account number, branch, customer care."
)

print("[Voice] Loading Whisper model (base)...")
whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
print("[Voice] Whisper ready.")


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Receive audio file from browser → return transcribed text.
    Uses banking-specific prompt for better domain accuracy.
    """
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be audio.")

    suffix = ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await audio.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        segments, info = whisper_model.transcribe(
            tmp_path,
            beam_size=5,
            language="en",                  # force English — removes language detection overhead
            initial_prompt=BANKING_PROMPT,  # bias toward banking vocabulary
            vad_filter=True,                # filter out silence/noise
            vad_parameters=dict(
                min_silence_duration_ms=500,  # ignore pauses under 500ms
            ),
            temperature=0.0,                # deterministic — more consistent output
            best_of=5,                      # try 5 candidates, pick best
            condition_on_previous_text=False, # don't let previous text bias next segment
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        os.unlink(tmp_path)

    if not text:
        raise HTTPException(status_code=422, detail="Could not transcribe audio. Please speak clearly and try again.")

    print(f"[STT] Transcribed ({info.language}, {info.duration:.1f}s): {text}")
    return {"text": text, "language": info.language}


@router.post("/speak")
async def speak(payload: dict):
    """
    Receive text → return audio/mp3 stream.
    """
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text provided.")

    if len(text) > 500:
        text = text[:500] + "..."

    tts = gTTS(text=text, lang="en", slow=False)
    mp3_buffer = io.BytesIO()
    tts.write_to_fp(mp3_buffer)
    mp3_buffer.seek(0)

    print(f"[TTS] Speaking: {text[:60]}...")
    return StreamingResponse(mp3_buffer, media_type="audio/mpeg")