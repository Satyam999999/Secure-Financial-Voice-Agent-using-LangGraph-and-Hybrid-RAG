import re

# ── Blocked patterns (hard rules, no LLM needed) ──────────────
BLOCK_PATTERNS = [
    # OTP / PIN / password fishing
    (r"\b(otp|one.time.pass|pin)\b", "OTP_REQUEST"),
    (r"\b(password|passcode)\b", "PASSWORD_REQUEST"),
    # Social engineering
    (r"\b(give me.{0,20}(account|card|cvv|expiry))\b", "SOCIAL_ENGINEERING"),
    (r"\b(send.{0,15}money|transfer.{0,15}funds)\b", "TRANSFER_REQUEST"),
    # Prompt injection attempts
    (r"ignore (previous|above|all) instructions", "PROMPT_INJECTION"),
    (r"(system prompt|you are now|act as|jailbreak)", "PROMPT_INJECTION"),
    # Explicit fraud
    (r"\b(hack|steal|exploit|bypass|fake account)\b", "FRAUD_ATTEMPT"),
]

SAFE_FALLBACK = (
    "I'm unable to help with that request. "
    "For sensitive banking matters, please contact us through "
    "official channels: visit your nearest branch or call our "
    "verified customer care number."
)

def check_input(text: str) -> dict:
    """
    Returns:
        { "safe": True }  — if input passes all checks
        { "safe": False, "reason": str, "response": str }  — if blocked
    """
    lowered = text.lower().strip()

    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, lowered):
            print(f"[InputGuard] BLOCKED — reason: {reason} | input: {text[:60]}")
            return {
                "safe": False,
                "reason": reason,
                "response": SAFE_FALLBACK,
            }

    return {"safe": True}