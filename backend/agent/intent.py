from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
import config

INTENT_PROMPT = """You are an intent classifier for a banking assistant.

Classify the user's message into EXACTLY one of these intents:

INFO_QUERY      — user wants general information (how to open account, loan rates, KYC docs, branch hours, what is UPI)
ACTION_REQUEST  — user wants to DO something or get their OWN account-specific data (check MY balance, send MY statement, apply for loan, I want a loan, need loan, loan apply, talk to agent)
SENSITIVE       — user mentions OTP, PIN, password, CVV, or account credentials
FRAUD           — message looks like phishing, scam, social engineering, or fraud attempt
CHITCHAT        — greetings, thanks, small talk unrelated to banking

IMPORTANT RULES:
- Any message mentioning "I want loan", "need a loan", "apply for loan", "loan for X amount", "personal loan", "home loan", "car loan" = ACTION_REQUEST
- Anything with "my" referring to user's own account data = ACTION_REQUEST
- Questions about how loans work in general = INFO_QUERY

Examples:
"How do I open a savings account?" → INFO_QUERY
"What is my balance?" → ACTION_REQUEST
"I want a loan" → ACTION_REQUEST
"I want loan for 2 lakhs" → ACTION_REQUEST
"Apply for personal loan" → ACTION_REQUEST
"Need home loan" → ACTION_REQUEST
"I want 5 lakhs loan" → ACTION_REQUEST
"What are loan interest rates?" → INFO_QUERY
"How does a home loan work?" → INFO_QUERY
"Send me my statement" → ACTION_REQUEST
"What is my OTP" → SENSITIVE
"Hello how are you" → CHITCHAT

Reply with ONLY the intent label. No explanation. No punctuation.

User message: {message}
Intent:"""

ROUTING_PROMPT = """You are a banking action classifier.

Given the user's message, decide which tool to call.
Reply with ONLY the tool name — no explanation, no punctuation.

Available tools:
- send_email_statement : user wants account statement sent to email
- fetch_account_summary : user wants to check balance or account details
- escalate_to_human : user wants to talk to a human, contact support staff, speak to an agent, get human help, or is frustrated
- request_callback : user wants a call back from the bank
- none : no tool needed, handle via general response

Examples:
"send me my last 3 months statement" → send_email_statement
"what is my balance" → fetch_account_summary
"I want to talk to a human agent" → escalate_to_human
"contact human for me" → escalate_to_human
"connect me to a person" → escalate_to_human
"speak to someone" → escalate_to_human
"I need human help" → escalate_to_human
"get me a representative" → escalate_to_human
"please call me back" → request_callback
"how do I open an account" → none

User message: {message}
Tool:"""
# Intents that should NOT reach the RAG chain
BLOCKED_INTENTS = {"SENSITIVE", "FRAUD"}

BLOCKED_RESPONSES = {
    "SENSITIVE": (
        "For security reasons, I cannot process requests involving OTPs, PINs, "
        "or passwords. Never share these with anyone, including bank representatives."
    ),
    "FRAUD": (
        "This looks like it may be a fraudulent request. I've flagged this interaction. "
        "If you believe you're being scammed, please call our fraud helpline immediately."
    ),
}

CHITCHAT_RESPONSE = (
    "Hello! I'm your banking assistant. I can help you with account information, "
    "loan queries, KYC requirements, and more. What would you like to know?"
)

# Lazy-load classifier LLM
_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = ChatGroq(
            model=config.MODEL_NAME,
            temperature=0,              # deterministic classification
            groq_api_key=config.GROQ_API_KEY,
            max_tokens=10,              # we only need one label back
        )
    return _classifier

def classify_intent(message: str) -> str:
    """Returns intent label as string."""
    prompt = ChatPromptTemplate.from_template(INTENT_PROMPT)
    chain = prompt | get_classifier()
    result = chain.invoke({"message": message})
    intent = result.content.strip().upper()

    # Fallback if model returns something unexpected
    valid = {"INFO_QUERY", "ACTION_REQUEST", "SENSITIVE", "FRAUD", "CHITCHAT"}
    if intent not in valid:
        print(f"[Intent] Unknown label '{intent}', defaulting to INFO_QUERY")
        intent = "INFO_QUERY"

    print(f"[Intent] '{message[:50]}' → {intent}")
    return intent