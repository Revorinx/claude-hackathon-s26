import base64
import json
import os
import re
from pathlib import Path

import anthropic
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# ─── Config ───────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def get_client() -> anthropic.AsyncAnthropic | None:
    if not ANTHROPIC_API_KEY:
        return None
    return anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


app = FastAPI()

# ─── Helpers ──────────────────────────────────────────────────────────────────


def strip_fences(text: str) -> str:
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*([\s\S]*?)```\s*$", t)
    return m.group(1).strip() if m else t


async def complete_json(system: str, user: str, max_tokens: int = 4096) -> str:
    c = get_client()
    if not c:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set")
    msg = await c.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    block = next((b for b in msg.content if b.type == "text"), None)
    if not block:
        raise HTTPException(502, "No text response from model")
    return block.text


# ─── Prompts ──────────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = """You are a clinical documentation assistant helping patients AFTER discharge.
Your job is to extract structured information ONLY from the discharge text the user provides.
Rules:
- Do NOT invent medications, doses, or instructions that are not clearly supported by the text.
- If something is missing, use empty arrays or a short honest string like "Not specified in discharge paperwork."
- Include source_quote for medications and red flags when a short verbatim snippet exists in the text.
- Output ONLY valid JSON matching the schema described in the user message. No markdown, no commentary."""


def build_extract_user(raw_text: str) -> str:
    return f'''Discharge paperwork text:

"""{raw_text}"""

Return a single JSON object with this exact shape (keys required):
{{
  "diagnosis_or_reason": string,
  "medications": [{{"name": string, "dose"?: string, "route"?: string, "frequency_text": string, "notes"?: string, "source_quote"?: string}}],
  "follow_ups": [{{"type": string, "within_text": string, "provider"?: string, "location"?: string, "datetime_if_known"?: string, "source_quote"?: string}}],
  "red_flags": [{{"text": string, "severity_hint"?: "emergency"|"urgent"|"contact"|"monitor", "source_quote"?: string}}],
  "activity": {{"restrictions": string[], "allowances": string[]}},
  "diet": {{"do": string[], "avoid": string[]}},
  "plain_language_summary": string,
  "todays_checklist": [{{"id": string, "label": string, "category": "medication"|"activity"|"diet"|"follow_up"|"education"|"other"}}],
  "medication_schedule_today": [{{"time_local": string, "label": string}}]
}}

Use stable ids like "check-1", "check-2" for checklist items.'''


CHECKIN_SYSTEM = """You are a conservative triage assistant for patients reviewing AFTER-visit discharge instructions.
You compare the patient's reported symptoms to the red flags and discharge context provided.
Rules:
- You are NOT diagnosing. You give guidance to seek appropriate care based on the discharge text.
- If uncertain between provider vs urgent, choose the safer (more urgent) option.
- Always mention emergency services (911 in the US) for life-threatening symptoms if relevant.
- Output ONLY valid JSON as specified. No markdown."""


def build_checkin_user(symptoms: dict, red_flags: list, care_plan_summary: str = "") -> str:
    return f"""Patient symptom check-in (structured):

{json.dumps(symptoms, indent=2)}

Discharge red flags (from their paperwork):
{json.dumps(red_flags, indent=2)}

Optional summary of their care plan:
{care_plan_summary or "(none)"}

Return JSON with this exact shape:
{{
  "tier": "home" | "provider" | "urgent",
  "rationale": string (2-4 sentences, plain language),
  "matched_flags": string[],
  "warning": string,
  "reason_for_concern": string,
  "triggering_excerpt": string,
  "shareable_text": string
}}"""


VISIT_PREP_SYSTEM = """You are a care coordinator helping a patient prepare for their post-discharge follow-up appointment.
Given their care plan, identify the most urgent upcoming appointment and produce a practical visit preparation guide.
Output ONLY valid JSON. No markdown, no commentary."""


def build_visit_prep_user(care_plan: dict) -> str:
    return f"""Care plan:
{json.dumps(care_plan, indent=2)}

Return JSON with this exact shape:
{{
  "when": string,
  "with_whom": string,
  "location": string | null,
  "bring": string[],
  "mention": string[]
}}

Be concrete and specific to this patient's situation. Reference their actual diagnosis, medications, and red flags."""


VISION_SYSTEM = (
    "You are a document text extractor. Extract all visible text from the image "
    "exactly as it appears and return it as plain text. "
    "Return ONLY the raw text content — no commentary, no markdown."
)


def build_chat_system(care_plan: dict | None) -> str:
    if care_plan:
        ctx = f"""Patient diagnosis: {care_plan.get("diagnosis_or_reason", "unknown")}

Plain language summary: {care_plan.get("plain_language_summary", "none")}

Medications: {json.dumps(care_plan.get("medications", []))}

Red flags to watch for: {json.dumps(care_plan.get("red_flags", []))}

Activity: {json.dumps(care_plan.get("activity", {}))}

Diet: {json.dumps(care_plan.get("diet", {}))}"""
    else:
        ctx = "No care plan loaded."
    return f"""You are a caring, plain-language medical assistant helping a patient after hospital discharge.
You have access to their discharge care plan:

{ctx}

Rules:
- Answer questions about their condition, medications, recovery, and care plan in simple, reassuring language.
- You do NOT diagnose or prescribe. You explain what their discharge instructions say.
- If symptoms sound serious or match their red flags, tell them to contact their provider or call 911.
- Keep responses concise and easy to read. Use short paragraphs.
- If you don't know something, say so and suggest they call their care team."""


# ─── Demo check-in (rule-based fallback when no API key) ─────────────────────


def demo_checkin(symptoms: dict, plan: dict) -> dict:
    red_flags = plan.get("red_flags", [])
    flags_text = " ".join(f.get("text", "").lower() for f in red_flags)
    matched: list[str] = []
    score = 0
    if symptoms.get("fever") == "high":
        score += 3
        if "fever" in flags_text or "101" in flags_text:
            matched.append("Fever threshold from discharge")
    if symptoms.get("shortness_of_breath") in ("moderate", "severe"):
        score += 3
        matched.append("Breathing symptoms")
    if (symptoms.get("pain") or 0) >= 8:
        score += 2
        matched.append("Severe pain")
    if symptoms.get("swelling") == "severe":
        score += 2
        if "swelling" in flags_text:
            matched.append("Worsening swelling")
    if symptoms.get("worse_overall"):
        score += 2
        matched.append("Overall worse than before")
    tier = "urgent" if score >= 4 else ("provider" if score >= 2 else "home")
    warnings = {
        "urgent": "Seek urgent care now or use emergency services if severe.",
        "provider": "Contact your care team today for guidance.",
        "home": "Continue home care and keep monitoring as instructed.",
    }
    excerpt = (
        (red_flags[0].get("source_quote") or red_flags[0].get("text"))
        if red_flags
        else plan.get("plain_language_summary", "")[:120]
    )
    return {
        "tier": tier,
        "rationale": (
            "Your symptoms are relatively stable compared with the warning signs in your discharge instructions. "
            "Keep following your plan and reach out if anything changes."
            if tier == "home"
            else "Based on what you reported and the precautions from your discharge paperwork, "
            "it is reasonable to get clinician input or urgent evaluation."
        ),
        "matched_flags": matched or ["General monitoring"],
        "warning": warnings[tier],
        "reason_for_concern": (
            "No strong match to urgent warning signs right now."
            if tier == "home"
            else "Your symptoms overlap with situations your discharge instructions said to escalate."
        ),
        "triggering_excerpt": excerpt or "",
        "shareable_text": (
            f"Post-discharge check-in (demo logic): {warnings[tier]} "
            f"Summary: {plan.get('diagnosis_or_reason', '')}. "
            f"Reported pain {symptoms.get('pain', 0)}/10, fever {symptoms.get('fever', 'unknown')}, "
            f"breathing {symptoms.get('shortness_of_breath', 'unknown')}. "
            "This message is not medical advice."
        ),
    }


# ─── API Routes ───────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.get("/api/sample-care-plan")
async def sample_care_plan():
    return JSONResponse(json.loads((FIXTURES_DIR / "sample-care-plan.json").read_text()))


@app.post("/api/extract")
async def extract(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    raw = (body.get("raw_text") or "").strip()
    if not raw:
        raise HTTPException(400, "raw_text is required")
    if not get_client():
        raise HTTPException(
            503,
            "LLM unavailable — set ANTHROPIC_API_KEY or use Load sample.",
        )
    text = await complete_json(EXTRACT_SYSTEM, build_extract_user(raw), max_tokens=8192)
    try:
        parsed = json.loads(strip_fences(text))
    except json.JSONDecodeError:
        raise HTTPException(422, "Model returned invalid JSON")
    return {"care_plan": parsed}


@app.post("/api/extract-image")
async def extract_image(image: UploadFile = File(...)):
    c = get_client()
    if not c:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set")
    if not (image.content_type or "").startswith("image/"):
        raise HTTPException(400, "File must be an image")
    contents = await image.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "Image too large (max 20MB)")
    b64 = base64.standard_b64encode(contents).decode()
    msg = await c.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=VISION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image.content_type or "image/jpeg",
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this discharge document exactly as it appears.",
                    },
                ],
            }
        ],
    )
    block = next((b for b in msg.content if b.type == "text"), None)
    return {"raw_text": block.text.strip() if block else ""}


@app.post("/api/extract-pdf")
async def extract_pdf(pdf: UploadFile = File(...)):
    c = get_client()
    if not c:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set")
    if pdf.content_type != "application/pdf":
        raise HTTPException(400, "File must be a PDF")
    contents = await pdf.read()
    if len(contents) > 32 * 1024 * 1024:
        raise HTTPException(400, "PDF too large (max 32MB)")
    b64 = base64.standard_b64encode(contents).decode()
    msg = await c.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this discharge document exactly as it appears. Return ONLY the raw text — no commentary, no markdown.",
                    },
                ],
            }
        ],
    )
    block = next((b for b in msg.content if b.type == "text"), None)
    return {"raw_text": block.text.strip() if block else ""}


@app.post("/api/chat")
async def chat(request: Request):
    c = get_client()
    if not c:
        raise HTTPException(503, "API not configured")
    body = await request.json()
    messages = body.get("messages", [])
    care_plan = body.get("carePlan")

    async def generate():
        async with c.messages.stream(
            model=MODEL,
            max_tokens=1024,
            system=build_chat_system(care_plan),
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text.encode()

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.post("/api/check-in")
async def check_in(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    symptoms = body.get("symptoms")
    if not symptoms:
        raise HTTPException(400, "symptoms is required")
    red_flags = body.get("red_flags", [])
    care_plan_summary = body.get("care_plan_summary", "")
    if not get_client():
        plan = {
            "red_flags": red_flags,
            "plain_language_summary": care_plan_summary or "",
            "diagnosis_or_reason": "",
            "medications": [],
        }
        return demo_checkin(symptoms, plan)
    text = await complete_json(
        CHECKIN_SYSTEM,
        build_checkin_user(symptoms, red_flags, care_plan_summary),
        max_tokens=2048,
    )
    try:
        return json.loads(strip_fences(text))
    except json.JSONDecodeError:
        raise HTTPException(422, "Model returned invalid JSON")


@app.post("/api/visit-prep")
async def visit_prep(request: Request):
    if not get_client():
        raise HTTPException(503, "API not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    care_plan = body.get("carePlan")
    if not care_plan:
        raise HTTPException(400, "carePlan is required")
    text = await complete_json(
        VISIT_PREP_SYSTEM, build_visit_prep_user(care_plan), max_tokens=1024
    )
    try:
        return json.loads(strip_fences(text))
    except json.JSONDecodeError:
        raise HTTPException(422, "Model returned invalid JSON")


@app.post("/api/schedule-reminders")
async def schedule_reminders(request: Request):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")
    if not all([account_sid, auth_token, from_number]):
        raise HTTPException(503, "Twilio not configured")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    phone = body.get("phone")
    schedule = body.get("schedule", [])
    if not phone:
        raise HTTPException(400, "phone is required")

    from twilio.rest import Client as TwilioClient
    from datetime import datetime

    def parse_time_today(time_local: str):
        m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", time_local.strip(), re.IGNORECASE)
        if not m:
            return None
        h, mn = int(m.group(1)), int(m.group(2))
        mer = (m.group(3) or "").upper()
        if mer == "PM" and h != 12:
            h += 12
        if mer == "AM" and h == 12:
            h = 0
        now = datetime.now()
        return datetime(now.year, now.month, now.day, h, mn, 0)

    tc = TwilioClient(account_sid, auth_token)
    msid = os.environ.get("TWILIO_MESSAGING_SERVICE_SID")
    sids: list[str] = []
    now = datetime.now()
    try:
        confirm_kw: dict = {
            "to": phone,
            "body": "Your medication reminders are set up. You will receive a text at each scheduled medication time today.",
        }
        if msid:
            confirm_kw["messaging_service_sid"] = msid
        else:
            confirm_kw["from_"] = from_number
        tc.messages.create(**confirm_kw)

        for item in schedule:
            send_at = parse_time_today(item.get("time_local", ""))
            if not send_at:
                continue
            mins = (send_at.timestamp() - now.timestamp()) / 60
            if mins < 0:
                continue
            mb = f"\U0001f48a Reminder: {item.get('label', '')}"
            if mins < 15:
                kw: dict = {"to": phone, "body": mb}
                if msid:
                    kw["messaging_service_sid"] = msid
                else:
                    kw["from_"] = from_number
                msg = tc.messages.create(**kw)
            else:
                msg = tc.messages.create(
                    to=phone,
                    from_=from_number,
                    body=mb,
                    send_at=send_at,
                    schedule_type="fixed",
                    messaging_service_sid=msid,
                )
            sids.append(msg.sid)
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"sids": sids}


@app.post("/api/cancel-reminders")
async def cancel_reminders(request: Request):
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not all([account_sid, auth_token]):
        raise HTTPException(503, "Twilio not configured")
    body = await request.json()
    from twilio.rest import Client as TwilioClient

    tc = TwilioClient(account_sid, auth_token)
    cancelled = 0
    for sid in body.get("sids", []):
        try:
            tc.messages(sid).update(status="canceled")
            cancelled += 1
        except Exception:
            pass
    return {"cancelled": cancelled}


# ─── Page routes ─────────────────────────────────────────────────────────────
STATIC = Path(__file__).parent / "static"


@app.get("/upload")
async def page_upload():
    return FileResponse(STATIC / "upload.html")


@app.get("/plan")
async def page_plan():
    return FileResponse(STATIC / "plan.html")


@app.get("/check-in")
async def page_checkin():
    return FileResponse(STATIC / "check-in.html")


# ─── Static files (LAST — /api/* and page routes take priority) ──────────────
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
