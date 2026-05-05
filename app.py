"""
CareCircle — Streamlit App
===========================
A care coordination agent for Meera.
Upload prescriptions, check interactions, get a daily briefing.
"""

import streamlit as st
import anthropic
import base64
import json
import uuid
from datetime import datetime, date
from pathlib import Path

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CareCircle",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stApp { font-family: 'Inter', sans-serif; }

    .cc-header {
        background: linear-gradient(135deg, #1E3A5F 0%, #2E75B6 100%);
        padding: 24px 28px; border-radius: 12px;
        margin-bottom: 24px; color: white;
    }
    .cc-header h1 { margin: 0; font-size: 28px; font-weight: 700; }
    .cc-header p  { margin: 4px 0 0; font-size: 14px; opacity: 0.85; }

    .metric-card {
        background: white; border-radius: 10px;
        padding: 18px 20px; border: 1px solid #e0e0e0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .metric-card .label { font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-card .value { font-size: 28px; font-weight: 700; color: #1E3A5F; margin-top: 4px; }
    .metric-card .sub   { font-size: 12px; color: #aaa; margin-top: 2px; }

    .med-card {
        background: white; border-radius: 10px;
        padding: 16px 18px; border: 1px solid #e0e0e0;
        margin-bottom: 10px; border-left: 4px solid #2E75B6;
    }
    .med-card.stale  { border-left-color: #FFA500; }
    .med-card .mname { font-size: 16px; font-weight: 700; color: #1E3A5F; }
    .med-card .minfo { font-size: 13px; color: #555; margin-top: 4px; }
    .med-card .msrc  { font-size: 11px; color: #aaa; margin-top: 6px; }

    .alert-critical { background:#fff0f0; border:1px solid #ffcccc; border-left:4px solid #cc0000; border-radius:10px; padding:16px 18px; margin-bottom:10px; }
    .alert-high     { background:#fff8f0; border:1px solid #ffd9b3; border-left:4px solid #FF6600; border-radius:10px; padding:16px 18px; margin-bottom:10px; }
    .alert-low      { background:#f0f8ff; border:1px solid #cce0ff; border-left:4px solid #2E75B6; border-radius:10px; padding:16px 18px; margin-bottom:10px; }

    .briefing-box {
        background: white; border-radius: 12px;
        padding: 24px; border: 1px solid #e0e0e0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        font-size: 15px; line-height: 1.7; color: #333;
    }

    .crisis-card {
        background: #fff0f0; border: 2px solid #cc0000;
        border-radius: 12px; padding: 20px;
    }
    .crisis-card h3 { color: #cc0000; margin-top: 0; }

    .confirm-card {
        background: #fffbf0; border: 1px solid #ffd980;
        border-left: 4px solid #FFA500; border-radius: 10px;
        padding: 16px 18px; margin-bottom: 10px;
    }

    .tag-verified { background:#e8f5e9; color:#2e7d32; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
    .tag-stale    { background:#fff3e0; color:#e65100; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
    .tag-high     { background:#ffebee; color:#c62828; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "profile" not in st.session_state:
    st.session_state.profile = {
        "patient": {
            "id": "dad_001",
            "display_name": "Dad",
            "age": 67,
            "conditions": ["Type 2 Diabetes", "Hypertension", "Post-cardiac episode"],
            "doctors": [
                {"role": "Cardiologist", "hospital": "Fortis Hospital"},
                {"role": "Endocrinologist", "hospital": "Apollo Hospital"},
                {"role": "General Physician", "hospital": "City Clinic"}
            ]
        },
        "medications": [],
        "lab_reports": [],
        "caregiver_updates": [],
        "alerts": []
    }

if "pending_confirmations" not in st.session_state:
    st.session_state.pending_confirmations = []

if "briefing" not in st.session_state:
    st.session_state.briefing = None

if "crisis_mode" not in st.session_state:
    st.session_state.crisis_mode = False


# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_client():
    key = st.session_state.get("api_key", "") or st.secrets.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)

def is_stale(date_str, threshold_days):
    if not date_str:
        return True
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return (date.today() - d).days > threshold_days
    except:
        return False

def days_ago(date_str):
    if not date_str:
        return "unknown date"
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        diff = (date.today() - d).days
        if diff == 0: return "today"
        if diff == 1: return "yesterday"
        return f"{diff} days ago"
    except:
        return date_str

def save_profile():
    pass  # In-memory for demo; in production this writes to disk


# ── PROMPTS ───────────────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """You are a medical data extraction assistant for CareCircle.

Extract ALL medications from this prescription image. For each medication extract:
- medication_name, dosage, frequency, duration, prescribing_doctor, date_prescribed, instructions

For each field provide confidence: HIGH (clearly readable), MEDIUM (some uncertainty), LOW (unclear/guessed).

CRITICAL RULES:
- If medication name is not clearly readable — do NOT guess. Flag it.
- A medication is ready_to_add ONLY if name + dosage + frequency are ALL HIGH confidence.
- Never invent information not visible in the image.

Return valid JSON only:
{
  "extraction_possible": true,
  "overall_confidence": "HIGH",
  "reason_if_low": "",
  "medications": [
    {
      "medication_name": "",
      "medication_name_confidence": "HIGH",
      "medication_name_alternatives": [],
      "dosage": "",
      "dosage_confidence": "HIGH",
      "frequency": "",
      "frequency_confidence": "HIGH",
      "duration": "",
      "prescribing_doctor": "",
      "date_prescribed": "",
      "instructions": "",
      "ready_to_add": true,
      "needs_confirmation": []
    }
  ],
  "document_notes": ""
}"""

INTERACTION_PROMPT = """You are a clinical pharmacology assistant for CareCircle.

Patient conditions: {conditions}

Medications:
{medications}

Check for drug-drug and drug-condition interactions.

RULES:
- Never diagnose. Never recommend changing medications. Always say "discuss with the doctor".
- Plain English only — Meera is not a pharmacist.
- If no interactions: say so clearly and reassuringly.

Return valid JSON only:
{{
  "interactions_found": false,
  "overall_risk": "NONE",
  "summary": "",
  "interactions": [
    {{
      "severity": "CRITICAL",
      "drugs_involved": [],
      "what_happens": "",
      "what_to_do": "",
      "urgency": ""
    }}
  ],
  "reassurance": ""
}}"""

BRIEFING_PROMPT = """You are CareCircle, a care coordination assistant for Meera.

Meera is a 31-year-old product manager in Bangalore managing her 67-year-old father's health from a distance.
She checks this at 7 AM before work or 10 PM when exhausted. She needs to know three things:
1. Is Dad okay?
2. Is anything urgent?
3. What do I need to do?

Here is Dad's current health profile:
{profile}

Write a warm, plain-English daily briefing. Maximum 200 words.

RULES:
- Never diagnose. Use plain language.
- If data is stale (prescriptions >90 days old, labs >30 days), say so.
- Be honest about what you don't know.
- End with one clear action item if there is one.
- Tone: caring, calm, direct. Like a trusted friend who happens to know medicine."""

CRISIS_PROMPT = """You are CareCircle in CRISIS MODE.

Meera needs information in the next 60 seconds. Dad may be having a medical emergency.

Dad's profile:
{profile}

Generate a structured crisis card with:
1. Current medications (name + dosage only — no extra text)
2. Last cardiac report summary (one sentence)
3. Nearest hospital from profile
4. Emergency contacts

Keep it extremely brief. This is not a time for prose. Headers and bullet points only.
No diagnostic language. No speculation."""


# ── CORE FUNCTIONS ────────────────────────────────────────────────────────────
def ingest_prescription(image_bytes, filename):
    client = get_client()
    if not client:
        return None, "No API key set"

    b64 = base64.standard_b64encode(image_bytes).decode()
    ext = filename.split(".")[-1].lower()
    media_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": EXTRACTION_PROMPT}
            ]
        }]
    )

    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip()), None


def run_interaction_check():
    client = get_client()
    if not client:
        return None

    meds = st.session_state.profile["medications"]
    if len(meds) < 2:
        return None

    med_list = "\n".join([
        f"- {m['name']} {m['dosage']}, {m['frequency']}"
        + (f" ({m['instructions']})" if m.get("instructions") else "")
        for m in meds
    ])
    conditions = ", ".join(st.session_state.profile["patient"]["conditions"])

    prompt = INTERACTION_PROMPT.format(conditions=conditions, medications=med_list)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    # Save alerts
    st.session_state.profile["alerts"] = []
    for i in result.get("interactions", []):
        st.session_state.profile["alerts"].append({
            "type": "drug_interaction",
            "severity": i["severity"],
            "drugs": i["drugs_involved"],
            "summary": i["what_happens"],
            "action": i["what_to_do"],
            "urgency": i["urgency"]
        })
    return result


def generate_briefing():
    client = get_client()
    if not client:
        return "Please set your API key in the sidebar."

    profile_summary = json.dumps(st.session_state.profile, indent=2)
    prompt = BRIEFING_PROMPT.format(profile=profile_summary)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def generate_crisis_card():
    client = get_client()
    if not client:
        return "Please set your API key."

    profile_summary = json.dumps(st.session_state.profile, indent=2)
    prompt = CRISIS_PROMPT.format(profile=profile_summary)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def detect_crisis(query: str) -> bool:
    crisis_keywords = [
        "chest pain", "chest ache", "heart attack", "not breathing",
        "unconscious", "fainted", "collapsed", "stroke", "emergency",
        "ambulance", "hospital now", "fell down", "not responding",
        "can't breathe", "cannot breathe"
    ]
    q = query.lower()
    return any(k in q for k in crisis_keywords)


def answer_query(query: str):
    client = get_client()
    if not client:
        return "Please set your API key."

    profile_summary = json.dumps(st.session_state.profile, indent=2)

    system = """You are CareCircle, a care coordination assistant.
RULES:
- Never diagnose or recommend medication changes.
- Always cite source and date of information.
- Flag if data is stale or missing.
- If uncertain, say so explicitly.
- Plain English only. Meera is not a clinician.
- Keep answers under 150 words."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=400,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Dad's profile:\n{profile_summary}\n\nMeera's question: {query}"
        }]
    )
    return response.content[0].text.strip()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔵 CareCircle")
    st.markdown("---")

    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")
    if api_key:
        st.session_state.api_key = api_key
        st.success("API key set ✓")

    st.markdown("---")
    st.markdown("**Dad's Profile**")
    p = st.session_state.profile["patient"]
    st.markdown(f"👤 {p['display_name']}, {p['age']} years")
    for c in p["conditions"]:
        st.markdown(f"  · {c}")

    st.markdown("---")
    meds = st.session_state.profile["medications"]
    labs = st.session_state.profile["lab_reports"]
    alerts = st.session_state.profile["alerts"]
    updates = st.session_state.profile["caregiver_updates"]

    col1, col2 = st.columns(2)
    col1.metric("Medications", len(meds))
    col2.metric("Alerts", len(alerts))
    col1.metric("Lab Reports", len(labs))
    col2.metric("Updates", len(updates))

    st.markdown("---")
    st.markdown("**Navigation**")
    page = st.radio("", [
        "🏠  Daily Briefing",
        "💊  Medications",
        "🔬  Lab Reports",
        "🗣️  Caregiver Updates",
        "⚠️  Alerts",
        "💬  Ask CareCircle",
    ], label_visibility="collapsed")


# ── HEADER ────────────────────────────────────────────────────────────────────
critical_count = sum(1 for a in alerts if a.get("severity") == "CRITICAL")
header_sub = "Keeping Meera informed, so she can be a daughter — not a coordinator."
if critical_count:
    header_sub = f"⚠️  {critical_count} CRITICAL alert{'s' if critical_count > 1 else ''} need your attention."

st.markdown(f"""
<div class="cc-header">
  <h1>🔵 CareCircle</h1>
  <p>{header_sub}</p>
</div>
""", unsafe_allow_html=True)


# ── PAGE: DAILY BRIEFING ──────────────────────────────────────────────────────
if "Daily Briefing" in page:
    st.markdown("### Good morning, Meera.")
    st.markdown("Here's everything you need to know about Dad today.")

    col1, col2, col3, col4 = st.columns(4)
    stale_meds = sum(1 for m in meds if is_stale(m.get("date_prescribed"), 90))
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Medications</div>
            <div class="value">{len(meds)}</div>
            <div class="sub">{stale_meds} possibly stale</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Active Alerts</div>
            <div class="value" style="color:{'#cc0000' if alerts else '#2e7d32'}">{len(alerts)}</div>
            <div class="sub">{'Needs attention' if alerts else 'All clear'}</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Lab Reports</div>
            <div class="value">{len(labs)}</div>
            <div class="sub">{'Recent' if labs else 'None uploaded'}</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="label">Caregiver Updates</div>
            <div class="value">{len(updates)}</div>
            <div class="sub">{'Recent activity' if updates else 'No updates'}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🔄 Generate Today's Briefing", use_container_width=True, type="primary"):
        with st.spinner("Generating your daily briefing..."):
            st.session_state.briefing = generate_briefing()

    if st.session_state.briefing:
        st.markdown(f'<div class="briefing-box">{st.session_state.briefing}</div>', unsafe_allow_html=True)

    # Crisis button
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("#### 🚨 Emergency")
    if st.button("🚨 DAD IS HAVING AN EMERGENCY — Get Crisis Card", use_container_width=True):
        st.session_state.crisis_mode = True

    if st.session_state.crisis_mode:
        with st.spinner("Generating emergency information..."):
            crisis = generate_crisis_card()
        st.markdown(f'<div class="crisis-card"><h3>🚨 CRISIS CARD</h3>{crisis}</div>', unsafe_allow_html=True)
        if st.button("✅ Emergency resolved — return to normal"):
            st.session_state.crisis_mode = False
            st.rerun()


# ── PAGE: MEDICATIONS ─────────────────────────────────────────────────────────
elif "Medications" in page:
    st.markdown("### 💊 Medications")
    st.markdown("Dad's verified medication list. Each entry was extracted from a prescription and confirmed before being added.")

    # Upload
    with st.expander("➕ Upload a new prescription", expanded=not meds):
        uploaded = st.file_uploader("Upload prescription photo", type=["jpg","jpeg","png","webp"])
        if uploaded:
            st.image(uploaded, caption="Uploaded prescription", width=400)
            if st.button("🔍 Extract medications from this prescription", type="primary"):
                with st.spinner("Reading prescription..."):
                    result, err = ingest_prescription(uploaded.read(), uploaded.name)
                if err:
                    st.error(f"Error: {err}")
                elif result:
                    if not result.get("extraction_possible"):
                        st.error(f"❌ Could not read prescription: {result.get('reason_if_low', 'Image unclear')}")
                        st.warning("Please upload a clearer photo.")
                    else:
                        added = 0
                        for med in result.get("medications", []):
                            if med.get("ready_to_add"):
                                entry = {
                                    "id": str(uuid.uuid4())[:8],
                                    "name": med["medication_name"],
                                    "dosage": med["dosage"],
                                    "frequency": med["frequency"],
                                    "duration": med.get("duration"),
                                    "instructions": med.get("instructions"),
                                    "prescribing_doctor": med.get("prescribing_doctor", "Unknown"),
                                    "date_prescribed": med.get("date_prescribed"),
                                    "source": uploaded.name,
                                    "date_ingested": datetime.now().strftime("%Y-%m-%d"),
                                    "verified": True,
                                    "stale": False,
                                    "confidence": "HIGH"
                                }
                                st.session_state.profile["medications"].append(entry)
                                added += 1
                            else:
                                st.session_state.pending_confirmations.append({
                                    "medication_name": med.get("medication_name", "Unknown"),
                                    "fields_to_confirm": med.get("needs_confirmation", []),
                                    "partial_data": med,
                                    "source": uploaded.name
                                })

                        if added:
                            st.success(f"✅ {added} medication(s) added to Dad's profile.")
                        pending = len(st.session_state.pending_confirmations)
                        if pending:
                            st.warning(f"⚠️ {pending} medication(s) need your confirmation before being added.")
                        if result.get("document_notes"):
                            st.info(f"📋 {result['document_notes']}")
                        st.rerun()

    # Pending confirmations
    if st.session_state.pending_confirmations:
        st.markdown("#### ⚠️ Needs Your Confirmation")
        st.markdown("These were extracted but NOT added — something was unclear. Please review:")
        for i, item in enumerate(st.session_state.pending_confirmations):
            st.markdown(f"""<div class="confirm-card">
                <strong>⚠️ {item['medication_name']}</strong><br>
                <span style="color:#888; font-size:13px;">Unclear fields: {', '.join(item['fields_to_confirm'])}</span>
            </div>""", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                confirmed_name = st.text_input("Confirm medication name", value=item["medication_name"], key=f"name_{i}")
                confirmed_dose = st.text_input("Confirm dosage", value=item["partial_data"].get("dosage",""), key=f"dose_{i}")
                confirmed_freq = st.text_input("Confirm frequency", value=item["partial_data"].get("frequency",""), key=f"freq_{i}")
            with col2:
                if st.button("✅ Add to profile", key=f"add_{i}"):
                    entry = {
                        "id": str(uuid.uuid4())[:8],
                        "name": confirmed_name,
                        "dosage": confirmed_dose,
                        "frequency": confirmed_freq,
                        "source": item["source"],
                        "date_ingested": datetime.now().strftime("%Y-%m-%d"),
                        "verified": True,
                        "manually_confirmed": True,
                        "stale": False,
                        "confidence": "MANUALLY_CONFIRMED"
                    }
                    st.session_state.profile["medications"].append(entry)
                    st.session_state.pending_confirmations.pop(i)
                    st.success(f"Added {confirmed_name} to profile.")
                    st.rerun()
                if st.button("❌ Discard", key=f"discard_{i}"):
                    st.session_state.pending_confirmations.pop(i)
                    st.rerun()

    # Medication list
    if not meds:
        st.info("No medications in profile yet. Upload a prescription above.")
    else:
        st.markdown(f"#### Active Medications ({len(meds)})")
        for m in meds:
            stale = is_stale(m.get("date_prescribed"), 90)
            stale_class = "stale" if stale else ""
            stale_tag = '<span class="tag-stale">⚠️ POSSIBLY STALE</span>' if stale else '<span class="tag-verified">✓ VERIFIED</span>'
            prescribed = days_ago(m.get("date_prescribed"))
            st.markdown(f"""<div class="med-card {stale_class}">
                <div class="mname">{m['name']} {m['dosage']} &nbsp; {stale_tag}</div>
                <div class="minfo">📅 {m['frequency']}{' &nbsp;·&nbsp; ' + m['instructions'] if m.get('instructions') else ''}</div>
                <div class="msrc">Prescribed {prescribed} by {m.get('prescribing_doctor','Unknown')} &nbsp;·&nbsp; Source: {m.get('source','Unknown')}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if len(meds) >= 2:
            if st.button("🔍 Check for Drug Interactions", type="primary", use_container_width=True):
                with st.spinner("Checking interactions..."):
                    result = run_interaction_check()
                if result:
                    if result["interactions_found"]:
                        st.warning(f"⚠️ {result['summary']}")
                    else:
                        st.success(f"✅ {result.get('reassurance', 'No significant interactions found.')}")
                    st.rerun()


# ── PAGE: LAB REPORTS ─────────────────────────────────────────────────────────
elif "Lab Reports" in page:
    st.markdown("### 🔬 Lab Reports")

    with st.expander("➕ Add a lab result manually", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            test_name = st.text_input("Test name (e.g. Fasting Blood Sugar)")
            test_value = st.text_input("Value (e.g. 180)")
            test_unit = st.selectbox("Unit", ["mg/dL", "mmol/L", "g/dL", "%", "IU/L", "mEq/L", "other"])
        with col2:
            ref_range = st.text_input("Reference range (e.g. 70-100)")
            test_date = st.date_input("Date of test", value=date.today())
            lab_name = st.text_input("Lab / Hospital name")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("➕ Add Lab Result", type="primary"):
                if test_name and test_value:
                    entry = {
                        "id": str(uuid.uuid4())[:8],
                        "test": test_name,
                        "value": test_value,
                        "unit": test_unit,
                        "reference_range": ref_range,
                        "date": str(test_date),
                        "lab": lab_name,
                        "date_ingested": datetime.now().strftime("%Y-%m-%d"),
                        "stale": is_stale(str(test_date), 30)
                    }
                    st.session_state.profile["lab_reports"].append(entry)
                    st.success(f"✅ {test_name} added.")
                    st.rerun()

    if not labs:
        st.info("No lab reports yet. Add one above.")
    else:
        for r in sorted(labs, key=lambda x: x.get("date",""), reverse=True):
            stale = is_stale(r.get("date"), 30)
            tag = '<span class="tag-stale">⚠️ STALE (>30 days)</span>' if stale else '<span class="tag-verified">✓ RECENT</span>'
            st.markdown(f"""<div class="med-card {'stale' if stale else ''}">
                <div class="mname">{r['test']}: {r['value']} {r['unit']} &nbsp; {tag}</div>
                <div class="minfo">Reference range: {r.get('reference_range','Not specified')}</div>
                <div class="msrc">Date: {r.get('date','Unknown')} &nbsp;·&nbsp; Lab: {r.get('lab','Unknown')}</div>
            </div>""", unsafe_allow_html=True)


# ── PAGE: CAREGIVER UPDATES ───────────────────────────────────────────────────
elif "Caregiver" in page:
    st.markdown("### 🗣️ Caregiver Updates")
    st.markdown("Log what the caregiver reports. Everything is tagged as 'interpreted' — not clinical fact.")

    with st.expander("➕ Add caregiver update", expanded=True):
        update_text = st.text_area("What did the caregiver report?", placeholder="e.g. Uncle ne aaj BP ki dawai li, thoda chakkar aaya...")
        update_date = st.date_input("Date", value=date.today())
        col1, col2 = st.columns(2)
        with col1:
            meds_taken = st.checkbox("Medications taken")
            had_meals  = st.checkbox("Had meals")
        with col2:
            symptoms   = st.text_input("Symptoms reported (if any)")

        if st.button("➕ Log Update", type="primary"):
            if update_text:
                entry = {
                    "id": str(uuid.uuid4())[:8],
                    "text": update_text,
                    "date": str(update_date),
                    "medications_taken": meds_taken,
                    "had_meals": had_meals,
                    "symptoms": symptoms,
                    "source": "Caregiver-A",
                    "tagged_as": "interpreted",
                    "date_ingested": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.profile["caregiver_updates"].append(entry)
                st.success("✅ Update logged.")
                st.rerun()

    if updates:
        st.markdown(f"#### Recent Updates ({len(updates)})")
        for u in sorted(updates, key=lambda x: x.get("date",""), reverse=True):
            age = days_ago(u.get("date"))
            sym = f" &nbsp;·&nbsp; Symptoms: _{u['symptoms']}_" if u.get("symptoms") else ""
            st.markdown(f"""<div class="med-card">
                <div class="mname">Caregiver-A &nbsp;·&nbsp; {age}</div>
                <div class="minfo">{u['text']}</div>
                <div class="msrc">
                    Meds taken: {'✓' if u.get('medications_taken') else '?'} &nbsp;·&nbsp;
                    Meals: {'✓' if u.get('had_meals') else '?'}{sym} &nbsp;·&nbsp;
                    <em>Tagged as: interpreted (not clinical fact)</em>
                </div>
            </div>""", unsafe_allow_html=True)


# ── PAGE: ALERTS ──────────────────────────────────────────────────────────────
elif "Alerts" in page:
    st.markdown("### ⚠️ Alerts")

    if not alerts:
        st.success("✅ No active alerts. Everything looks okay based on the information we have.")
    else:
        for a in alerts:
            sev = a.get("severity","LOW")
            cls = "alert-critical" if sev == "CRITICAL" else "alert-high" if sev == "HIGH" else "alert-low"
            icon = "🚨" if sev == "CRITICAL" else "⚠️" if sev == "HIGH" else "ℹ️"
            drugs = " + ".join(a.get("drugs",[]))
            st.markdown(f"""<div class="{cls}">
                <strong>{icon} {sev}: {drugs}</strong><br>
                <span style="font-size:14px">{a.get('summary','')}</span><br><br>
                <strong>What to do:</strong> {a.get('action','')}<br>
                <strong>Urgency:</strong> {a.get('urgency','')}
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Staleness check**")
    stale_meds = [m for m in meds if is_stale(m.get("date_prescribed"), 90)]
    stale_labs = [r for r in labs if is_stale(r.get("date"), 30)]
    if stale_meds:
        st.warning(f"⚠️ {len(stale_meds)} prescription(s) are older than 90 days — please verify they're still current.")
        for m in stale_meds:
            st.markdown(f"  · {m['name']} {m['dosage']} — prescribed {days_ago(m.get('date_prescribed'))}")
    if stale_labs:
        st.warning(f"⚠️ {len(stale_labs)} lab report(s) are older than 30 days.")
    if not stale_meds and not stale_labs:
        st.success("✅ All data is within freshness thresholds.")


# ── PAGE: ASK CARECIRCLE ──────────────────────────────────────────────────────
elif "Ask" in page:
    st.markdown("### 💬 Ask CareCircle")
    st.markdown("Ask anything about Dad's health. CareCircle will answer based only on what's in his profile — and will always say when it doesn't know.")

    query = st.text_input("Your question", placeholder="What medications is Dad on? / Is Dad's blood sugar high? / What did the caregiver say today?")

    if query:
        if detect_crisis(query):
            st.error("🚨 This sounds like an emergency. Switch to the Daily Briefing page and use the Crisis Card button immediately.")
        else:
            if st.button("Ask", type="primary"):
                with st.spinner("Checking Dad's profile..."):
                    answer = answer_query(query)
                st.markdown(f'<div class="briefing-box">{answer}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Example questions:**")
    examples = [
        "What medications is Dad on right now?",
        "When was his last lab report?",
        "What did the caregiver say today?",
        "Are any of his prescriptions out of date?",
        "Is there anything urgent I should know?"
    ]
    for e in examples:
        st.markdown(f"  · _{e}_")


# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<p style="font-size:11px; color:#aaa; text-align:center;">'
    'CareCircle · Built for Meera · 100xEngineers Applied AI Capstone · '
    'Not a medical device. Always consult a doctor for medical decisions.'
    '</p>',
    unsafe_allow_html=True
)
