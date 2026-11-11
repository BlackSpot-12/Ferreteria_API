import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", SMTP_USER)
WEB_PUBLIC_URL = os.getenv("WEB_PUBLIC_URL", "").rstrip("/")
MAIL_ENABLED = os.getenv("MAIL_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def enviar_correo(destinatario: str, asunto: str, html: str, texto_plano: str) -> bool:
    if any(char in str(destinatario) for char in "\r\n") or any(
        char in str(asunto) for char in "\r\n"
    ):
        logger.warning("Correo rechazado: category=header_validation")
        return False
    if not destinatario or not asunto:
        logger.warning("Correo rechazado: category=header_validation")
        return False
    if not MAIL_ENABLED:
        logger.info("Correo omitido: category=notification, mail_enabled=false")
        return False

    try:
        message = EmailMessage()
        message["Subject"] = asunto
        message["From"] = MAIL_FROM
        message["To"] = destinatario
        message.set_content(texto_plano)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except Exception:
        logger.warning("Fallo SMTP: category=notification")
        return False
