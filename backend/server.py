from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import time
import uuid
import logging
import ipaddress
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Emergent managed email proxy. This is a CONSTANT — never read it from
# os.environ, so it survives deployment.
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
OWNER_EMAIL = os.environ["OWNER_EMAIL"]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Email guardrail gate (G2/G3 structural checks) ---
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None) -> str | None:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning(f"Email paused: {code} ({e.response.status_code})")
            raise HTTPException(status_code=503, detail="Email is temporarily unavailable")
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to send email")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send email")


# --- Contact enquiries ---
_hits: dict[str, list[float]] = {}


def _rate_ok(ip: str) -> bool:
    now = time.time()
    window = [t for t in _hits.get(ip, []) if now - t < 600]
    if len(window) >= 5:
        _hits[ip] = window
        return False
    window.append(now)
    _hits[ip] = window
    return True


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    message: str = Field(min_length=10, max_length=4000)


@api_router.get("/")
async def root():
    return {"message": "rpsahnni.dev API", "status": "ok"}


@api_router.post("/contact")
async def create_enquiry(payload: ContactIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _rate_ok(ip):
        raise HTTPException(status_code=429, detail="Too many messages. Please try again later.")

    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "email": payload.email,
        "message": payload.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.enquiries.insert_one(doc)

    name_e = escape(payload.name)
    email_e = escape(payload.email)
    msg_e = escape(payload.message).replace("\n", "<br/>")

    owner_subject = f"New project enquiry from {payload.name[:60]}"
    owner_html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px;'
        'font-family:Arial,sans-serif;color:#111827">'
        f'<h2 style="margin:0 0 16px;font-size:18px">New enquiry on {escape(EMAIL_FROM_NAME)}</h2>'
        f'<p style="margin:0 0 8px"><strong>Name:</strong> {name_e}</p>'
        f'<p style="margin:0 0 8px"><strong>Email:</strong> <a href="mailto:{email_e}">{email_e}</a></p>'
        f'<p style="margin:16px 0 4px"><strong>Message:</strong></p>'
        f'<p style="margin:0;padding:12px;background:#f3f4f6;border-radius:8px">{msg_e}</p>'
        f'<p style="margin:24px 0 0;font-size:12px;color:#6b7280">Sent by the contact form on {escape(EMAIL_FROM_NAME)}. '
        'We never ask for your password or card details by email.</p>'
        '</td></tr></table>'
    )

    visitor_subject = "Thanks for reaching out"
    visitor_html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px;'
        'font-family:Arial,sans-serif;color:#111827">'
        f'<p style="margin:0 0 12px">Hi {name_e},</p>'
        '<p style="margin:0 0 12px">Thanks for your enquiry — I have received your message and will reply within a day.</p>'
        '<p style="margin:0 0 12px">— Ram Pravesh Sahni, Full-Stack, Mobile &amp; AI Automation Developer</p>'
        f'<p style="margin:24px 0 0;font-size:12px;color:#6b7280">Sent by {escape(EMAIL_FROM_NAME)}. '
        'We never ask for your password or card details by email.</p>'
        '</td></tr></table>'
    )

    emailed = True
    try:
        await send_email(to=OWNER_EMAIL, subject=owner_subject, html=owner_html)
        await send_email(to=payload.email, subject=visitor_subject, html=visitor_html)
    except HTTPException:
        emailed = False
        logger.warning(f"Enquiry {doc['id']} saved but email notification failed")

    return {"status": "ok", "id": doc["id"], "emailed": emailed}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
