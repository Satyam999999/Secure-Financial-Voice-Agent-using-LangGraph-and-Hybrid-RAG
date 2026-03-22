import re

# Patterns that should NEVER appear in LLM output
OUTPUT_BLOCK_PATTERNS = [
    (r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "CARD_NUMBER"),  # 16-digit card
    (r"\b\d{6,8}\b", "POSSIBLE_OTP"),                                   # 6-8 digit codes
    (r"\b[A-Z]{4}0\d{6}\b", "IFSC_CODE"),                              # IFSC format
    (r"(password|otp|pin).{0,10}is.{0,10}\d+", "CREDENTIAL_LEAK"),
]

SAFE_FALLBACK = (
    "I found some information but cannot display it as it may contain "
    "sensitive data. Please contact official banking support for details."
)

def check_output(text: str) -> dict:
    """
    Scan LLM output before returning to user.
    Returns:
        { "safe": True, "text": original_text }
        { "safe": False, "text": fallback, "reason": str }
    """
    for pattern, reason in OUTPUT_BLOCK_PATTERNS:
        if re.search(pattern, text):
            print(f"[OutputGuard] BLOCKED output — reason: {reason}")
            return {
                "safe": False,
                "text": SAFE_FALLBACK,
                "reason": reason,
            }

    return {"safe": True, "text": text}