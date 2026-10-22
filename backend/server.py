from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, UploadFile, File, Response
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
from datetime import datetime, timezone, timedelta
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import httpx
import bcrypt
import jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")
OWNER_EMAIL = os.environ["OWNER_EMAIL"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"].lower()
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------- Auth ----------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(email: str) -> str:
    payload = {"sub": email, "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=12), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_admin(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"email": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Not authorized")
    return user


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@api_router.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower()
    ip = request.client.host if request.client else "unknown"
    ident = f"{ip}:{email}"
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("locked_until") and att["locked_until"] > time.time():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        count = (att or {}).get("count", 0) + 1
        upd = {"count": count, "first_at": time.time()}
        if count >= 5:
            upd["locked_until"] = time.time() + 900
        await db.login_attempts.update_one({"identifier": ident}, {"$set": upd}, upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_one({"identifier": ident})
    token = create_access_token(email)
    response.set_cookie(key="access_token", value=token, httponly=True, secure=True, samesite="none", max_age=43200, path="/")
    return {"token": token, "user": {"email": email, "name": user.get("name", "Admin"), "role": "admin"}}


@api_router.get("/auth/me")
async def auth_me(admin=Depends(get_current_admin)):
    return admin


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"status": "ok"}


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@api_router.post("/auth/change-password")
async def change_password(payload: ChangePasswordIn, admin=Depends(get_current_admin)):
    user = await db.users.find_one({"email": admin["email"]})
    if not user or not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one({"email": admin["email"]}, {"$set": {"password_hash": hash_password(payload.new_password)}})
    return {"status": "ok"}


async def seed_admin():
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing is None:
        await db.users.insert_one({
            "email": ADMIN_EMAIL, "password_hash": hash_password(ADMIN_PASSWORD),
            "name": "Ram Pravesh Sahni", "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Admin user seeded")

# ---------------- Content (public) ----------------

CAT_LABELS = {"backend": "Backend", "web": "Web", "mobile": "Mobile", "ai": "AI & Automation"}
SPAN_PATTERN = ["lg:col-span-3", "lg:col-span-3", "lg:col-span-2", "lg:col-span-2", "lg:col-span-2"]

DEFAULT_PROJECTS = [
    {"title": "Billing & Invoice API", "cat": "backend", "desc": "High-concurrency microservice handling secure invoice generation, PDF exports and payment gateway webhooks for multiple tenants.", "hi": "RBAC · PDF invoices · payment webhooks", "tech": ["Django", "PostgreSQL", "Docker", "AWS"], "featured": True, "order": 0, "img": "https://images.unsplash.com/photo-1759661881353-5b9cc55e1cf4?crop=entropy&cs=srgb&fm=jpg&q=85", "features": ["Multi-tenant architecture with role-based access control", "PDF invoice generation with branded templates", "Payment gateway webhooks with retry-safe handling", "Containerised with Docker and deployed on AWS"], "outcome": "One API serves every tenant — billing runs end to end without manual work.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
    {"title": "Realtime Chat Service", "cat": "backend", "desc": "Ultra-low latency WebSocket chat server supporting 10k+ concurrent connections with pub/sub architecture and message history.", "hi": "10k+ concurrent sockets · Redis pub/sub", "tech": ["Golang", "Redis", "PostgreSQL"], "featured": False, "order": 1, "img": "https://images.pexels.com/photos/26765065/pexels-photo-26765065.png?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "features": ["WebSocket server in Go built for high throughput", "Redis pub/sub fan-out across multiple nodes", "Persistent message history in PostgreSQL", "Graceful reconnects and presence tracking"], "outcome": "10k+ concurrent connections stay live with sub-second message delivery.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
    {"title": "Business Dashboard", "cat": "web", "desc": "Analytics & financial management portal featuring real-time telemetry, charts and exportable reports behind secure login.", "hi": "Live telemetry · exportable reports", "tech": ["React", "TypeScript", "Tailwind CSS"], "featured": False, "order": 2, "img": "https://images.pexels.com/photos/9951077/pexels-photo-9951077.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "features": ["Real-time charts and KPI telemetry", "Secure authentication and session handling", "Exportable PDF/CSV reports", "Fast loads with TypeScript-safe data layer"], "outcome": "Owners see the whole business on one screen and export reports in a click.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
    {"title": "Delivery Tracking App", "cat": "mobile", "desc": "Cross-platform mobile application with live GPS driver movement, push alerts and full order lifecycle management.", "hi": "Live GPS tracking · push notifications", "tech": ["Flutter", "Firebase", "FastAPI"], "featured": False, "order": 3, "img": "https://images.unsplash.com/photo-1759661881353-5b9cc55e1cf4?crop=entropy&cs=srgb&fm=jpg&q=85", "features": ["Single Flutter codebase for Android and iOS", "Live driver GPS movement on maps", "Push notifications at every order stage", "FastAPI backend with Firebase sync"], "outcome": "Customers watch their delivery move in real time, from pickup to doorstep.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
    {"title": "Lead-to-WhatsApp Automation", "cat": "ai", "desc": "Zero-human workflow routing incoming lead forms through AI qualification directly into WhatsApp conversations within seconds.", "hi": "AI lead scoring · instant WhatsApp reply", "tech": ["n8n", "OpenAI", "Webhooks"], "featured": False, "order": 4, "img": "https://images.pexels.com/photos/26765065/pexels-photo-26765065.png?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "features": ["n8n workflow triggered by any form or webhook", "AI scores and qualifies every new lead", "Instant personalised reply on WhatsApp", "Retries and logging built into the pipeline"], "outcome": "Every lead gets an intelligent WhatsApp reply in seconds — even at 2 AM.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
    {"title": "Support Chatbot with RAG", "cat": "ai", "desc": "Context-aware AI knowledge assistant answering from dynamic company documents via retrieval-augmented generation.", "hi": "Vector search · human handover", "tech": ["FastAPI", "LangChain", "PostgreSQL Vector"], "featured": False, "order": 5, "img": "https://images.pexels.com/photos/9951077/pexels-photo-9951077.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940", "features": ["RAG over company documents and FAQs", "Vector search stored in PostgreSQL", "FastAPI serving layer with LangChain", "Hands over to a human when confidence is low"], "outcome": "Support answers come from your own documents — accurate, instant, always on.", "gh": "https://github.com/rpsahnni-creator", "live": ""},
]

DEFAULT_SKILLS = [
    {"name": "Backend", "items": ["Python", "Django", "Django REST", "FastAPI", "Golang", "Node.js", "Express.js", "TypeScript", "GraphQL", "Celery"], "order": 0},
    {"name": "Databases", "items": ["PostgreSQL", "Oracle", "SQL", "MongoDB", "Redis"], "order": 1},
    {"name": "Frontend", "items": ["HTML5", "CSS3", "JavaScript", "React", "Next.js", "Vite", "Tailwind CSS"], "order": 2},
    {"name": "Mobile", "items": ["Flutter", "React Native", "Firebase"], "order": 3},
    {"name": "Cloud & DevOps", "items": ["AWS", "GCP", "Docker", "Git", "GitHub Actions", "Nginx", "Linux", "Vercel"], "order": 4},
    {"name": "AI & Automation", "items": ["n8n", "LLM APIs", "LangChain", "RAG", "Chatbots", "Webhooks"], "order": 5},
]

DEFAULT_TESTIMONIALS = [
    {"text": "Ram took our billing from messy spreadsheets to a fully automated API — invoices, payments, everything. What our team did in hours now happens on its own.", "name": "Ankit V.", "role": "Founder, Logistics Startup", "order": 0},
    {"text": "The chat backend he built in Go handles our busiest sale days without a hiccup. Clear communication, clean code, delivered before the deadline.", "name": "Priya S.", "role": "CTO, E-commerce Platform", "order": 1},
    {"text": "Our WhatsApp lead automation replies in seconds, even at midnight. Enquiries stopped slipping through the cracks — that alone paid for the project.", "name": "Rohit M.", "role": "Owner, Real Estate Agency", "order": 2},
    {"text": "He built our dashboard and the support chatbot both. One person, full stack, zero excuses. We stopped interviewing agencies after working with him.", "name": "Sneha K.", "role": "Operations Head, EdTech Company", "order": 3},
]


async def seed_content():
    if await db.projects.count_documents({}) == 0:
        await db.projects.insert_many([{**p, "id": str(uuid.uuid4())} for p in DEFAULT_PROJECTS])
    if await db.skills.count_documents({}) == 0:
        await db.skills.insert_many([{**s, "id": str(uuid.uuid4())} for s in DEFAULT_SKILLS])
    if await db.testimonials.count_documents({}) == 0:
        await db.testimonials.insert_many([{**t, "id": str(uuid.uuid4())} for t in DEFAULT_TESTIMONIALS])


def shape_project(p, i, span):
    return {
        "id": p["id"], "n": f"{i + 1:02d}", "t": p["title"], "c": p["cat"],
        "cl": CAT_LABELS.get(p["cat"], p["cat"]), "d": p["desc"], "hi": p.get("hi", ""),
        "k": p.get("tech", []), "span": span, "featured": bool(p.get("featured")),
        "img": p.get("img", ""), "features": p.get("features", []),
        "outcome": p.get("outcome", ""), "gh": p.get("gh", ""), "live": p.get("live", ""),
    }


@api_router.get("/content")
async def get_content():
    projs = await db.projects.find({}, {"_id": 0}).sort("order", 1).to_list(200)
    shaped = []
    j = 0
    for i, p in enumerate(projs):
        if p.get("featured"):
            span = "lg:col-span-6"
        else:
            span = SPAN_PATTERN[j % len(SPAN_PATTERN)]
            j += 1
        shaped.append(shape_project(p, i, span))
    skills = await db.skills.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    testis = await db.testimonials.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    resume = await db.files.find_one({"id": "resume"}, {"_id": 1})
    return {
        "projects": shaped,
        "skills": skills,
        "testimonials": testis,
        "resumeUrl": "/api/resume" if resume else "",
    }

# ---------------- Admin CRUD ----------------

class ProjectIn(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    cat: str = Field(pattern="^(backend|web|mobile|ai)$")
    desc: str = Field(min_length=5, max_length=600)
    hi: str = ""
    tech: list[str] = []
    features: list[str] = []
    outcome: str = ""
    gh: str = ""
    live: str = ""
    img: str = ""
    featured: bool = False
    order: int = 0


class SkillIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    items: list[str] = []
    order: int = 0


class TestimonialIn(BaseModel):
    text: str = Field(min_length=5, max_length=600)
    name: str = Field(min_length=2, max_length=60)
    role: str = ""
    order: int = 0


@api_router.get("/admin/projects")
async def admin_list_projects(admin=Depends(get_current_admin)):
    return await db.projects.find({}, {"_id": 0}).sort("order", 1).to_list(200)


@api_router.post("/admin/projects")
async def admin_create_project(p: ProjectIn, admin=Depends(get_current_admin)):
    doc = {**p.model_dump(), "id": str(uuid.uuid4())}
    await db.projects.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.put("/admin/projects/{pid}")
async def admin_update_project(pid: str, p: ProjectIn, admin=Depends(get_current_admin)):
    res = await db.projects.update_one({"id": pid}, {"$set": p.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok"}


@api_router.delete("/admin/projects/{pid}")
async def admin_delete_project(pid: str, admin=Depends(get_current_admin)):
    await db.projects.delete_one({"id": pid})
    return {"status": "ok"}


@api_router.get("/admin/skills")
async def admin_list_skills(admin=Depends(get_current_admin)):
    return await db.skills.find({}, {"_id": 0}).sort("order", 1).to_list(50)


@api_router.post("/admin/skills")
async def admin_create_skill(s: SkillIn, admin=Depends(get_current_admin)):
    doc = {**s.model_dump(), "id": str(uuid.uuid4())}
    await db.skills.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.put("/admin/skills/{sid}")
async def admin_update_skill(sid: str, s: SkillIn, admin=Depends(get_current_admin)):
    res = await db.skills.update_one({"id": sid}, {"$set": s.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Skill group not found")
    return {"status": "ok"}


@api_router.delete("/admin/skills/{sid}")
async def admin_delete_skill(sid: str, admin=Depends(get_current_admin)):
    await db.skills.delete_one({"id": sid})
    return {"status": "ok"}


@api_router.get("/admin/testimonials")
async def admin_list_testimonials(admin=Depends(get_current_admin)):
    return await db.testimonials.find({}, {"_id": 0}).sort("order", 1).to_list(50)


@api_router.post("/admin/testimonials")
async def admin_create_testimonial(t: TestimonialIn, admin=Depends(get_current_admin)):
    doc = {**t.model_dump(), "id": str(uuid.uuid4())}
    await db.testimonials.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.put("/admin/testimonials/{tid}")
async def admin_update_testimonial(tid: str, t: TestimonialIn, admin=Depends(get_current_admin)):
    res = await db.testimonials.update_one({"id": tid}, {"$set": t.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"status": "ok"}


@api_router.delete("/admin/testimonials/{tid}")
async def admin_delete_testimonial(tid: str, admin=Depends(get_current_admin)):
    await db.testimonials.delete_one({"id": tid})
    return {"status": "ok"}


@api_router.get("/admin/enquiries")
async def admin_enquiries(admin=Depends(get_current_admin)):
    return await db.enquiries.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


class ReplyIn(BaseModel):
    message: str = Field(min_length=2, max_length=4000)


@api_router.post("/admin/enquiries/{eid}/reply")
async def admin_reply_enquiry(eid: str, payload: ReplyIn, admin=Depends(get_current_admin)):
    enq = await db.enquiries.find_one({"id": eid}, {"_id": 0})
    if not enq:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    name_e = escape(enq["name"])
    msg_e = escape(payload.message).replace("\n", "<br/>")
    subject = "Re: your enquiry to rpsahnni.dev"
    html = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="padding:24px;'
        'font-family:Arial,sans-serif;color:#111827">'
        f'<p style="margin:0 0 12px">Hi {name_e},</p>'
        f'<p style="margin:0 0 12px">{msg_e}</p>'
        '<p style="margin:0 0 12px">— Ram Pravesh Sahni, Full-Stack, Mobile &amp; AI Automation Developer</p>'
        f'<p style="margin:24px 0 0;font-size:12px;color:#6b7280">Sent by {escape(EMAIL_FROM_NAME)} in reply to your enquiry. '
        'We never ask for your password or card details by email.</p>'
        '</td></tr></table>'
    )
    await send_email(to=enq["email"], subject=subject, html=html)
    await db.enquiries.update_one({"id": eid}, {"$set": {"replied_at": datetime.now(timezone.utc).isoformat()}})
    return {"status": "ok"}


class TrackIn(BaseModel):
    path: str = Field(max_length=200)
    sid: str = Field(max_length=64)
    ref: str = ""


@api_router.post("/track")
async def track_view(t: TrackIn):
    if not t.path.startswith("/"):
        raise HTTPException(status_code=400, detail="bad path")
    await db.pageviews.insert_one({
        "id": str(uuid.uuid4()), "path": t.path, "sid": t.sid, "ref": t.ref[:300],
        "at": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "ok"}


@api_router.get("/admin/analytics")
async def admin_analytics(admin=Depends(get_current_admin)):
    views = await db.pageviews.find({}, {"_id": 0}).to_list(20000)
    enqs = await db.enquiries.find({}, {"_id": 0, "created_at": 1}).to_list(2000)
    now = datetime.now(timezone.utc)
    days = []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        days.append({
            "day": day,
            "views": sum(1 for v in views if str(v.get("at", "")).startswith(day)),
            "enquiries": sum(1 for e in enqs if str(e.get("created_at", "")).startswith(day)),
        })
    refs = {}
    for v in views:
        r = v.get("ref") or ""
        host = "Direct"
        if r:
            host = urlparse(r).hostname or "Direct"
        refs[host] = refs.get(host, 0) + 1
    top = sorted(refs.items(), key=lambda x: -x[1])[:5]
    return {
        "totalViews": len(views),
        "uniqueSessions": len({v.get("sid") for v in views if v.get("sid")}),
        "totalEnquiries": len(enqs),
        "days": days,
        "topReferrers": [{"source": k, "count": c} for k, c in top],
    }

# ---------------- Files (images + resume) ----------------

@api_router.post("/admin/files")
async def admin_upload_file(file: UploadFile = File(...), admin=Depends(get_current_admin)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads allowed here")
    fid = str(uuid.uuid4())
    await db.files.insert_one({
        "id": fid, "filename": file.filename, "content_type": file.content_type,
        "data": data, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"id": fid, "url": f"/api/files/{fid}"}


@api_router.post("/admin/resume")
async def admin_upload_resume(file: UploadFile = File(...), admin=Depends(get_current_admin)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB)")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF allowed for resume")
    await db.files.update_one(
        {"id": "resume"},
        {"$set": {"id": "resume", "filename": file.filename, "content_type": "application/pdf",
                  "data": data, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"status": "ok", "url": "/api/resume"}


@api_router.get("/files/{fid}")
async def get_file(fid: str):
    doc = await db.files.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=bytes(doc["data"]), media_type=doc["content_type"])


@api_router.get("/resume")
async def get_resume():
    doc = await db.files.find_one({"id": "resume"})
    if not doc:
        raise HTTPException(status_code=404, detail="No resume uploaded yet")
    return Response(content=bytes(doc["data"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{doc.get("filename", "resume.pdf")}"'})

# ---------------- Email (contact form) ----------------

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
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    await seed_admin()
    await seed_content()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
