from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def mail_configured() -> bool:
    if settings.resend_api_key:
        return True
    return bool(settings.smtp_host and settings.smtp_from)


def _message_bodies(verify_url: str) -> tuple[str, str]:
    text = (
        "Confirm you are creating an Optiq account.\n\n"
        f"Click this link to verify your email:\n{verify_url}\n\n"
        "If you did not sign up, ignore this message."
    )
    html = (
        "<p>Confirm you are creating an Optiq account.</p>"
        f'<p><a href="{verify_url}">Click to verify your email</a></p>'
        "<p>If you did not sign up, ignore this message.</p>"
    )
    return text, html


def _send_via_resend(to_email: str, from_addr: str, text: str, html: str) -> bool:
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": from_addr,
            "to": [to_email],
            "subject": "Confirm your Optiq account",
            "text": text,
            "html": html,
        },
        timeout=20.0,
    )
    response.raise_for_status()
    return True


def _send_via_smtp(to_email: str, from_addr: str, text: str, html: str) -> bool:
    message = EmailMessage()
    message["Subject"] = "Confirm your Optiq account"
    message["From"] = from_addr
    message["To"] = to_email
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, (settings.smtp_password or "").replace(" ", ""))
        smtp.send_message(message)
    return True


def send_verification_email(to_email: str, verify_url: str) -> bool:
    if not mail_configured():
        logger.warning(
            "Mail is not configured (smtp_host=%s smtp_from=%s resend=%s); verification email was not sent",
            bool(settings.smtp_host),
            bool(settings.smtp_from),
            bool(settings.resend_api_key),
        )
        return False

    text, html = _message_bodies(verify_url)
    from_addr = settings.smtp_from or "Optiq <noreply@optiq.local>"

    if settings.resend_api_key:
        try:
            return _send_via_resend(to_email, from_addr, text, html)
        except Exception:
            logger.exception("Resend failed to deliver verification email")
            if not (settings.smtp_host and settings.smtp_from):
                return False

    if not (settings.smtp_host and settings.smtp_from):
        return False

    try:
        return _send_via_smtp(to_email, from_addr, text, html)
    except Exception:
        logger.exception("SMTP failed to deliver verification email")
        return False
