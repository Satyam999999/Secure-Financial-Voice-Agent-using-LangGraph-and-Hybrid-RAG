from datetime import datetime
import asyncio
import threading
# ── Tool definitions ───────────────────────────────────────────────────────
# Each tool returns a dict: { "success": bool, "message": str, "data": any }
# Phase 8 (HITL) will add real integrations. These are realistic stubs.

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

def send_email_statement(session_id: str, email: str = None) -> dict:
    """
    Send a real account statement notification email via Gmail SMTP.
    Uses the SMTP_EMAIL from .env as both sender and recipient (demo mode).
    In production: fetch user's registered email from core banking system.
    """
    if not session_id:
        return {
            "success": False,
            "message": "Session not found. Please log in to request a statement.",
        }

    if not config.SMTP_EMAIL or not config.SMTP_APP_PASSWORD:
        return {
            "success": False,
            "message": "Email service is not configured. Please contact support.",
        }

    ref_number = f"STMT{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # In production: recipient = fetch from DB by session/user ID
    # For demo: send to the configured SMTP_EMAIL itself
    recipient = email or config.SMTP_EMAIL

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Account Statement Request Received — Ref: {ref_number}"
    msg["From"]    = config.SMTP_EMAIL
    msg["To"]      = recipient

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1565c0; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="color: white; margin: 0;">🏦 Banking Assistant</h2>
            <p style="color: #bbdefb; margin: 4px 0 0;">Account Statement Request</p>
        </div>
        <div style="border: 1px solid #e0e0e0; border-top: none; padding: 24px; border-radius: 0 0 8px 8px;">
            <p>Dear Customer,</p>
            <p>Your account statement request has been received and is being processed.</p>

            <div style="background: #f5f5f5; padding: 16px; border-radius: 6px; margin: 16px 0;">
                <p style="margin: 0;"><strong>Reference Number:</strong> {ref_number}</p>
                <p style="margin: 8px 0 0;"><strong>Request Time:</strong> {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}</p>
                <p style="margin: 8px 0 0;"><strong>Delivery:</strong> Within 24 hours to this email</p>
            </div>

            <p>Your detailed account statement will be sent to this email address shortly.</p>

            <div style="background: #fff3e0; padding: 12px; border-radius: 6px; margin: 16px 0; border-left: 4px solid #ff9800;">
                <p style="margin: 0; font-size: 13px;">
                    <strong>Security Notice:</strong> Never share this email or your banking credentials with anyone.
                    Our bank will never ask for your OTP, PIN, or password via email or phone.
                </p>
            </div>

            <p style="color: #666; font-size: 12px;">
                This is an automated message from your Banking Assistant.<br>
                Session ID: {session_id[:8]}…
            </p>
        </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.SMTP_EMAIL, config.SMTP_APP_PASSWORD)
            server.sendmail(config.SMTP_EMAIL, recipient, msg.as_string())

        print(f"[Tool] Email sent to {recipient} | ref={ref_number}")
        return {
            "success": True,
            "message": (
                f"Your account statement request has been received. "
                f"A confirmation has been sent to your registered email address. "
                f"The statement will be delivered within 24 hours. "
                f"Reference number: {ref_number}."
            ),
            "data": {"ref_number": ref_number, "sent_to": recipient},
        }

    except smtplib.SMTPAuthenticationError:
        print("[Tool] SMTP authentication failed — check SMTP_APP_PASSWORD in .env")
        return {
            "success": False,
            "message": "Email service authentication failed. Please contact support.",
        }
    except Exception as e:
        print(f"[Tool] Email send failed: {e}")
        return {
            "success": False,
            "message": "Could not send email at this time. Please try again later.",
        }


def fetch_account_summary(session_id: str) -> dict:
    """
    Return a safe, generic account summary.
    In production: integrate with core banking API after authentication.
    """
    if not session_id:
        return {
            "success": False,
            "message": "Session not found. Please verify your identity first.",
        }

    print(f"[Tool] fetch_account_summary | session={session_id}")

    # Never return real account data here without auth — stub only
    return {
        "success": True,
        "message": (
            "For security reasons, I can only provide account details through "
            "the official mobile app or net banking portal after full authentication. "
            "Would you like me to guide you through the login process?"
        ),
        "data": {},
    }


def escalate_to_human(session_id: str, reason: str, conversation_history: list) -> dict:
    """
    Escalate to human agent.
    Logging is handled by the caller (routes.py) in async context.
    """
    ref_number = f"ESC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    print(f"[Tool] escalate_to_human | session={session_id[:8]} | ref={ref_number}")

    return {
        "success": True,
        "message": (
            f"I've escalated your request to a human banking specialist. "
            f"Your reference number is {ref_number}. "
            f"A representative will contact you within 2-4 business hours "
            f"on your registered contact details."
        ),
        "data": {
            "ref_number": ref_number,
            "reason":     reason,
            "session_id": session_id,
            "is_escalation": True,          # flag for routes.py to log
            "conversation":  conversation_history or [],
        },
    }


    
def request_callback(session_id: str) -> dict:
    """Request a callback from the bank."""
    ref_number = f"CB{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    print(f"[Tool] request_callback | session={session_id} | ref={ref_number}")

    return {
        "success": True,
        "message": (
            f"Your callback request has been registered. "
            f"Reference: {ref_number}. "
            f"A banking representative will call you on your registered mobile number within 4 business hours."
        ),
        "data": {"ref_number": ref_number},
    }