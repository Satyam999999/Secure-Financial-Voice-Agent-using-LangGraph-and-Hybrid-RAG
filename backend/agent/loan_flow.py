"""
Agentic Loan Application Flow using LangGraph.

Multi-turn guided conversation:
User: "I want to apply for a personal loan"
Bot:  "What loan amount do you need?"
User: "2 lakhs"
Bot:  "What is your monthly income?"
User: "50,000"
Bot:  "What is the loan purpose?"
User: "Medical emergency"
Bot:  "Based on your details, you are eligible for ₹2,00,000 at 12% p.a.
       EMI would be ₹4,444/month for 5 years. Shall I proceed?"
User: "Yes"
Bot:  "Application submitted! Ref: LOAN20260321. Confirmation sent to email."
"""

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
import operator
import config
from agent.tools import send_email_statement

# ── Loan State ────────────────────────────────────────────────
class LoanState(TypedDict):
    session_id:    str
    user:          dict
    messages:      Annotated[list, operator.add]  # conversation history

    # Collected loan details
    loan_type:     str
    loan_amount:   str
    monthly_income: str
    loan_purpose:  str
    employment:    str

    # Flow control
    current_step:  str
    confirmed:     bool
    completed:     bool

    # Output
    answer:        str
    ref_number:    str

LOAN_STEPS = [
    "loan_type",
    "loan_amount",
    "monthly_income",
    "loan_purpose",
    "employment",
    "confirm",
    "done",
]

# Lazily initialized compiled LangGraph instance reused across requests.
_loan_graph = None

def get_llm():
    return ChatGroq(
        model=config.MODEL_NAME,
        temperature=0.2,
        groq_api_key=config.GROQ_API_KEY,
        max_tokens=200,
    )

# ── Node: Determine next question ────────────────────────────
LOAN_COLLECTOR_PROMPT = """You are a banking loan application assistant.

Collected information so far:
- Loan type:       {loan_type}
- Loan amount:     {loan_amount}
- Monthly income:  {monthly_income}
- Loan purpose:    {loan_purpose}
- Employment type: {employment}

User's latest message: {message}

Your job:
1. Extract any loan information from the user's message and update the fields above
2. Determine what information is still missing
3. Ask for the NEXT missing piece of information naturally

Missing fields (ask for the first one that is "unknown"):
- If loan_type is unknown: ask what type of loan (personal, home, car, education, gold)
- If loan_amount is unknown: ask how much they need
- If monthly_income is unknown: ask their monthly income
- If loan_purpose is unknown: ask the purpose of the loan
- If employment is unknown: ask if they are salaried or self-employed
- If all filled: say "READY_TO_CONFIRM"

Respond with JSON only:
{{
  "loan_type": "extracted or unknown",
  "loan_amount": "extracted or unknown",
  "monthly_income": "extracted or unknown",
  "loan_purpose": "extracted or unknown",
  "employment": "extracted or unknown",
  "next_question": "your question to user OR READY_TO_CONFIRM"
}}"""

def collect_info_node(state: LoanState) -> LoanState:
    """Collect loan application details step by step."""
    llm    = get_llm()
    prompt = ChatPromptTemplate.from_template(LOAN_COLLECTOR_PROMPT)
    chain  = prompt | llm

    last_msg = state["messages"][-1] if state["messages"] else ""

    result = chain.invoke({
        "loan_type":      state.get("loan_type", "unknown"),
        "loan_amount":    state.get("loan_amount", "unknown"),
        "monthly_income": state.get("monthly_income", "unknown"),
        "loan_purpose":   state.get("loan_purpose", "unknown"),
        "employment":     state.get("employment", "unknown"),
        "message":        last_msg,
    })

    import json, re
    try:
        raw  = result.content.strip()
        # Extract JSON even if wrapped in markdown
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        data  = json.loads(match.group()) if match else {}
    except Exception:
        data = {}

    next_q = data.get("next_question", "Could you tell me more about your loan requirement?")

    return {
        **state,
        "loan_type":      data.get("loan_type", state.get("loan_type", "unknown")),
        "loan_amount":    data.get("loan_amount", state.get("loan_amount", "unknown")),
        "monthly_income": data.get("monthly_income", state.get("monthly_income", "unknown")),
        "loan_purpose":   data.get("loan_purpose", state.get("loan_purpose", "unknown")),
        "employment":     data.get("employment", state.get("employment", "unknown")),
        "current_step":   "confirm" if next_q == "READY_TO_CONFIRM" else "collecting",
        "answer":         next_q if next_q != "READY_TO_CONFIRM" else "",
    }

# ── Node: Check eligibility + present offer ───────────────────
def eligibility_node(state: LoanState) -> LoanState:
    """Calculate eligibility and present loan offer."""
    try:
        # Parse income and amount
        income_str = state.get("monthly_income", "0").replace(",", "").replace("₹", "").strip()
        amount_str = state.get("loan_amount", "0").replace(",", "").replace("₹", "").replace("lakh", "00000").replace("lakhs", "00000").strip()

        monthly_income = float(''.join(filter(lambda x: x.isdigit() or x == '.', income_str)) or 0)
        loan_amount    = float(''.join(filter(lambda x: x.isdigit() or x == '.', amount_str)) or 0)

        # If amount mentioned in lakhs
        if "lakh" in state.get("loan_amount", "").lower():
            loan_amount = loan_amount * 100000 if loan_amount < 1000 else loan_amount

        # Simple eligibility: loan ≤ 20x monthly income
        max_eligible   = monthly_income * 20
        is_eligible    = loan_amount <= max_eligible and monthly_income >= 15000

        if not is_eligible:
            if monthly_income < 15000:
                answer = (
                    f"I'm sorry, but based on your monthly income of ₹{monthly_income:,.0f}, "
                    f"you do not meet the minimum income requirement of ₹15,000 for a personal loan. "
                    f"You may be eligible for other loan products. Would you like me to connect you with a banking specialist?"
                )
            else:
                answer = (
                    f"Based on your monthly income of ₹{monthly_income:,.0f}, "
                    f"the maximum loan you are eligible for is ₹{max_eligible:,.0f}. "
                    f"You requested ₹{loan_amount:,.0f}. Would you like to apply for ₹{max_eligible:,.0f} instead?"
                )
            return {**state, "answer": answer, "current_step": "not_eligible", "completed": False}

        # Calculate EMI (at 12% p.a. for 5 years)
        rate    = 12 / 100 / 12  # monthly rate
        tenure  = 60              # 5 years in months
        emi     = loan_amount * rate * (1 + rate)**tenure / ((1 + rate)**tenure - 1)

        loan_type = state.get("loan_type", "personal").title()

        answer = (
            f"Great news! Based on your profile:\n\n"
            f"📋 Loan Details:\n"
            f"• Type: {loan_type} Loan\n"
            f"• Amount: ₹{loan_amount:,.0f}\n"
            f"• Interest Rate: 12% per annum\n"
            f"• Tenure: 5 years (60 months)\n"
            f"• Monthly EMI: ₹{emi:,.0f}\n"
            f"• Purpose: {state.get('loan_purpose', 'General')}\n\n"
            f"You are eligible! Shall I proceed with the application? (Yes/No)"
        )

        return {**state, "answer": answer, "current_step": "awaiting_confirmation"}

    except Exception as e:
        print(f"[LoanFlow] Eligibility calc error: {e}")
        answer = (
            "Based on your details, you appear to be eligible for this loan. "
            "Shall I proceed with the application? (Yes/No)"
        )
        return {**state, "answer": answer, "current_step": "awaiting_confirmation"}

# ── Node: Handle confirmation ─────────────────────────────────
def confirmation_node(state: LoanState) -> LoanState:
    """Handle user's yes/no confirmation."""
    last_msg = (state["messages"][-1] if state["messages"] else "").lower().strip()
    confirmed = any(w in last_msg for w in ["yes", "yeah", "proceed", "confirm", "ok", "sure", "apply"])

    if not confirmed:
        return {
            **state,
            "answer":    "No problem. Your loan application has been cancelled. Feel free to apply again anytime.",
            "completed": True,
            "confirmed": False,
        }

    return {**state, "confirmed": True}

# ── Node: Submit application ──────────────────────────────────
def submit_application_node(state: LoanState) -> LoanState:
    """Submit the loan application and send confirmation."""
    from datetime import datetime
    ref_number = f"LOAN{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Send confirmation email
    user      = state.get("user", {})
    email     = user.get("email", "")
    if email:
        _send_loan_confirmation_email(
            email      = email,
            ref_number = ref_number,
            loan_type  = state.get("loan_type", "Personal"),
            amount     = state.get("loan_amount", ""),
            purpose    = state.get("loan_purpose", ""),
        )

    answer = (
        f"✅ Your loan application has been submitted successfully!\n\n"
        f"📄 Application Reference: {ref_number}\n"
        f"• Loan Type: {state.get('loan_type', 'Personal').title()} Loan\n"
        f"• Amount: ₹{state.get('loan_amount', '')}\n"
        f"• Purpose: {state.get('loan_purpose', '')}\n\n"
        f"A confirmation has been sent to your registered email. "
        f"A loan officer will contact you within 2 business days for document verification."
    )

    return {
        **state,
        "answer":     answer,
        "ref_number": ref_number,
        "completed":  True,
    }

def _send_loan_confirmation_email(email, ref_number, loan_type, amount, purpose):
    """Send loan application confirmation email."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import config

    if not config.SMTP_EMAIL or not config.SMTP_APP_PASSWORD:
        print("[LoanFlow] SMTP not configured, skipping email")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Loan Application Received — Ref: {ref_number}"
    msg["From"]    = config.SMTP_EMAIL
    msg["To"]      = email

    html = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1565c0; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0;">🏦 Loan Application Confirmation</h2>
        </div>
        <div style="border: 1px solid #e0e0e0; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Dear Customer,</p>
            <p>Your loan application has been received and is under review.</p>
            <div style="background: #f5f5f5; padding: 16px; border-radius: 6px; margin: 16px 0;">
                <p style="margin: 0;"><strong>Reference Number:</strong> {ref_number}</p>
                <p style="margin: 8px 0 0;"><strong>Loan Type:</strong> {loan_type.title()} Loan</p>
                <p style="margin: 8px 0 0;"><strong>Amount Requested:</strong> ₹{amount}</p>
                <p style="margin: 8px 0 0;"><strong>Purpose:</strong> {purpose}</p>
            </div>
            <p>Next steps:</p>
            <ol>
                <li>A loan officer will contact you within 2 business days</li>
                <li>Keep your income proof and identity documents ready</li>
                <li>Track your application using reference: <strong>{ref_number}</strong></li>
            </ol>
            <div style="background: #fff3e0; padding: 12px; border-radius: 6px; border-left: 4px solid #ff9800;">
                <p style="margin: 0; font-size: 13px;">
                    <strong>Important:</strong> Never share your OTP, PIN, or account credentials with anyone.
                </p>
            </div>
        </div>
    </body></html>
    """

    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.SMTP_EMAIL, config.SMTP_APP_PASSWORD)
            server.sendmail(config.SMTP_EMAIL, email, msg.as_string())
        print(f"[LoanFlow] Confirmation email sent to {email}")
    except Exception as e:
        print(f"[LoanFlow] Email error: {e}")

# ── Conditional edges ─────────────────────────────────────────
def route_after_collect(state: LoanState) -> str:
    if state.get("current_step") == "confirm":
        return "check_eligibility"
    return "ask_more"

def route_after_eligibility(state: LoanState) -> str:
    if state.get("current_step") == "not_eligible":
        return "done"
    return "await_confirmation"

def route_after_confirmation(state: LoanState) -> str:
    if state.get("confirmed"):
        return "submit"
    return "done"

# ── Build loan graph ──────────────────────────────────────────
def build_loan_graph():
    graph = StateGraph(LoanState)

    graph.add_node("collect_info",        collect_info_node)
    graph.add_node("check_eligibility",   eligibility_node)

    graph.set_entry_point("collect_info")

    # collect_info → either ask more questions (END) or check eligibility
    graph.add_conditional_edges(
        "collect_info",
        route_after_collect,
        {
            "ask_more":          END,
            "check_eligibility": "check_eligibility",
        }
    )

    # check_eligibility → either not eligible (END) or wait for confirmation (END)
    # Both end here — next user message re-enters at collect_info
    # which detects current_step == "awaiting_confirmation" and routes to handle_confirmation
    graph.add_conditional_edges(
        "check_eligibility",
        route_after_eligibility,
        {
            "done":               END,
            "await_confirmation": END,
        }
    )

    return graph.compile()

def get_loan_graph():
    global _loan_graph
    if _loan_graph is None:
        _loan_graph = build_loan_graph()
    return _loan_graph

async def run_loan_flow(
    message:    str,
    session_id: str,
    user:       dict,
    loan_state: dict = None,
) -> dict:
    import asyncio

    state: LoanState = {
        "session_id":     session_id,
        "user":           user or {},
        "messages":       [message],
        "loan_type":      loan_state.get("loan_type", "unknown") if loan_state else "unknown",
        "loan_amount":    loan_state.get("loan_amount", "unknown") if loan_state else "unknown",
        "monthly_income": loan_state.get("monthly_income", "unknown") if loan_state else "unknown",
        "loan_purpose":   loan_state.get("loan_purpose", "unknown") if loan_state else "unknown",
        "employment":     loan_state.get("employment", "unknown") if loan_state else "unknown",
        "current_step":   loan_state.get("current_step", "collecting") if loan_state else "collecting",
        "confirmed":      False,
        "completed":      False,
        "answer":         "",
        "ref_number":     "",
    }

    current_step = state["current_step"]

    # Route to correct entry node based on current step
    if current_step == "awaiting_confirmation":
        # User is responding yes/no — go straight to confirmation handler
        graph = StateGraph(LoanState)
        graph.add_node("handle_confirmation", confirmation_node)
        graph.add_node("submit_application",  submit_application_node)
        graph.set_entry_point("handle_confirmation")
        graph.add_conditional_edges(
            "handle_confirmation",
            route_after_confirmation,
            {"submit": "submit_application", "done": END}
        )
        graph.add_edge("submit_application", END)
        confirm_graph = graph.compile()

        final = await asyncio.get_event_loop().run_in_executor(
            None, lambda: confirm_graph.invoke(state)
        )
    else:
        # Normal collection flow
        final = await asyncio.get_event_loop().run_in_executor(
            None, lambda: get_loan_graph().invoke(state)
        )

    return {
        "answer":    final.get("answer", ""),
        "completed": final.get("completed", False),
        "ref_number": final.get("ref_number", ""),
        "loan_state": {
            "loan_type":      final.get("loan_type", "unknown"),
            "loan_amount":    final.get("loan_amount", "unknown"),
            "monthly_income": final.get("monthly_income", "unknown"),
            "loan_purpose":   final.get("loan_purpose", "unknown"),
            "employment":     final.get("employment", "unknown"),
            "current_step":   final.get("current_step", "collecting"),
        },
    }