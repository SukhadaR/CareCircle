"""
CareCircle — Streamlit App with Supabase Persistence
Multi-profile support. Data persists across sessions.
"""

import streamlit as st
import anthropic
import base64
import json
import uuid
from datetime import datetime, date
from supabase import create_client

st.set_page_config(page_title="CareCircle", page_icon="🔵", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .cc-header { background: linear-gradient(135deg, #1E3A5F 0%, #2E75B6 100%); padding: 24px 28px; border-radius: 12px; margin-bottom: 24px; color: white; }
    .cc-header h1 { margin: 0; font-size: 28px; font-weight: 700; }
    .cc-header p  { margin: 4px 0 0; font-size: 14px; opacity: 0.85; }
    .metric-card { background: white; border-radius: 10px; padding: 18px 20px; border: 1px solid #e0e0e0; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
    .metric-card .label { font-size: 12px; color: #888; font-weight: 600; text-transform: uppercase; }
    .metric-card .value { font-size: 28px; font-weight: 700; color: #1E3A5F; margin-top: 4px; }
    .metric-card .sub   { font-size: 12px; color: #aaa; margin-top: 2px; }
    .med-card { background: white; border-radius: 10px; padding: 16px 18px; border: 1px solid #e0e0e0; margin-bottom: 10px; border-left: 4px solid #2E75B6; }
    .med-card.stale { border-left-color: #FFA500; }
    .med-card .mname { font-size: 16px; font-weight: 700; color: #1E3A5F; }
    .med-card .minfo { font-size: 13px; color: #555; margin-top: 4px; }
    .med-card .msrc  { font-size: 11px; color: #aaa; margin-top: 6px; }
    .alert-critical { background:#fff0f0; border:1px solid #ffcccc; border-left:4px solid #cc0000; border-radius:10px; padding:16px 18px; margin-bottom:10px; }
    .alert-high     { background:#fff8f0; border:1px solid #ffd9b3; border-left:4px solid #FF6600; border-radius:10px; padding:16px 18px; margin-bottom:10px; }
    .alert-low      { background:#f0f8ff; border:1px solid #cce0ff; border-left:4px solid #2E75B6; border-radius:10px; padding:16px 18px; margin-bottom:10px; }
    .briefing-box { background: white; border-radius: 12px; padding: 24px; border: 1px solid #e0e0e0; font-size: 15px; line-height: 1.7; color: #333; }
    .crisis-card { background: #fff0f0; border: 2px solid #cc0000; border-radius: 12px; padding: 20px; }
    .crisis-card h3 { color: #cc0000; margin-top: 0; }
    .confirm-card { background: #fffbf0; border: 1px solid #ffd980; border-left: 4px solid #FFA500; border-radius: 10px; padding: 16px 18px; margin-bottom: 10px; }
    .tag-verified { background:#e8f5e9; color:#2e7d32; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
    .tag-stale    { background:#fff3e0; color:#e65100; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_supabase():
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)

def db_get_profiles():
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("profiles").select("*").order("created_at").execute().data or []
    except: return []

def db_create_profile(name, age, conditions, doctors):
    sb = get_supabase()
    if not sb:
        st.error("❌ Cannot connect to database. Check that SUPABASE_URL and SUPABASE_KEY are set in Streamlit secrets.")
        return None
    pid = str(uuid.uuid4())[:8]
    try:
        sb.table("profiles").insert({"id": pid, "name": name, "age": age, "conditions": conditions, "doctors": doctors}).execute()
        return pid
    except Exception as e:
        st.error(f"❌ Database error: {e}")
        return None

def db_get_medications(pid):
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("medications").select("*").eq("profile_id", pid).order("created_at").execute().data or []
    except: return []

def db_add_medication(pid, med):
    sb = get_supabase()
    if not sb: return
    try: sb.table("medications").insert({**med, "profile_id": pid}).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_get_lab_reports(pid):
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("lab_reports").select("*").eq("profile_id", pid).order("date", desc=True).execute().data or []
    except: return []

def db_add_lab_report(pid, r):
    sb = get_supabase()
    if not sb: return
    try: sb.table("lab_reports").insert({**r, "profile_id": pid}).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_get_caregiver_updates(pid):
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("caregiver_updates").select("*").eq("profile_id", pid).order("date", desc=True).execute().data or []
    except: return []

def db_add_caregiver_update(pid, u):
    sb = get_supabase()
    if not sb: return
    try: sb.table("caregiver_updates").insert({**u, "profile_id": pid}).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_get_alerts(pid):
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("alerts").select("*").eq("profile_id", pid).order("created_at", desc=True).execute().data or []
    except: return []

def db_save_alerts(pid, interactions):
    sb = get_supabase()
    if not sb: return
    try:
        sb.table("alerts").delete().eq("profile_id", pid).eq("type", "drug_interaction").execute()
        for i in interactions:
            sb.table("alerts").insert({"profile_id": pid, "type": "drug_interaction", "severity": i["severity"],
                "drugs": i["drugs_involved"], "summary": i["what_happens"], "action": i["what_to_do"], "urgency": i["urgency"]}).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_delete_medication(med_id):
    sb = get_supabase()
    if not sb: return
    try: sb.table("medications").delete().eq("id", med_id).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_delete_lab_report(report_id):
    sb = get_supabase()
    if not sb: return
    try: sb.table("lab_reports").delete().eq("id", report_id).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_delete_caregiver_update(update_id):
    sb = get_supabase()
    if not sb: return
    try: sb.table("caregiver_updates").delete().eq("id", update_id).execute()
    except Exception as e: st.error(f"Error: {e}")

def db_save_prescription(pid, prescription):
    sb = get_supabase()
    if not sb: return
    try: sb.table("prescriptions").insert({**prescription, "profile_id": pid}).execute()
    except Exception as e: st.error(f"Error saving prescription: {e}")

def db_get_prescriptions(pid):
    sb = get_supabase()
    if not sb: return []
    try: return sb.table("prescriptions").select("*").eq("profile_id", pid).order("created_at", desc=True).execute().data or []
    except: return []

def db_delete_prescription(prescription_id):
    sb = get_supabase()
    if not sb: return
    try: sb.table("prescriptions").delete().eq("id", prescription_id).execute()
    except Exception as e: st.error(f"Error: {e}")

def get_ai_client():
    key = st.session_state.get("api_key", "") or st.secrets.get("ANTHROPIC_API_KEY", "")
    if not key: return None
    return anthropic.Anthropic(api_key=key)

def is_stale(date_str, threshold_days):
    if not date_str: return True
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (date.today() - d).days > threshold_days
    except: return False

def days_ago(date_str):
    if not date_str: return "unknown date"
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        diff = (date.today() - d).days
        if diff == 0: return "today"
        if diff == 1: return "yesterday"
        return f"{diff} days ago"
    except: return date_str

def parse_json_response(text):
    raw = text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    return json.loads(raw.strip())

def ingest_prescription(image_bytes, filename):
    client = get_ai_client()
    if not client: return None, "No API key"
    ext = filename.split(".")[-1].lower()
    media_map = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png","webp":"image/webp"}
    b64 = base64.standard_b64encode(image_bytes).decode()
    PROMPT = """Extract ALL medications from this prescription. For each: medication_name, dosage, frequency, duration, prescribing_doctor, date_prescribed, instructions. Confidence per field: HIGH/MEDIUM/LOW. ready_to_add=true only if name+dosage+frequency all HIGH. Return JSON only:
{"extraction_possible":true,"overall_confidence":"HIGH","reason_if_low":"","medications":[{"medication_name":"","medication_name_confidence":"HIGH","medication_name_alternatives":[],"dosage":"","dosage_confidence":"HIGH","frequency":"","frequency_confidence":"HIGH","duration":"","prescribing_doctor":"","date_prescribed":"","instructions":"","ready_to_add":true,"needs_confirmation":[]}],"document_notes":""}"""
    response = client.messages.create(model="claude-opus-4-5", max_tokens=1500,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":media_map.get(ext,"image/jpeg"),"data":b64}},
            {"type":"text","text":PROMPT}]}])
    return parse_json_response(response.content[0].text), None

def run_interaction_check(pid, meds, conditions):
    client = get_ai_client()
    if not client or len(meds) < 2: return None
    med_list = "\n".join([f"- {m['name']} {m['dosage']}, {m['frequency']}" + (f" ({m['instructions']})" if m.get("instructions") else "") for m in meds])
    PROMPT = f"""Patient conditions: {", ".join(conditions)}\nMedications:\n{med_list}\nCheck interactions. Never diagnose. Plain English. JSON only:
{{"interactions_found":false,"overall_risk":"NONE","summary":"","interactions":[{{"severity":"LOW","drugs_involved":[],"what_happens":"","what_to_do":"","urgency":""}}],"reassurance":""}}"""
    response = client.messages.create(model="claude-opus-4-5", max_tokens=1500, messages=[{"role":"user","content":PROMPT}])
    result = parse_json_response(response.content[0].text)
    db_save_alerts(pid, result.get("interactions",[]) if result["interactions_found"] else [])
    return result

def generate_briefing(profile, meds, labs, updates, alerts):
    client = get_ai_client()
    if not client: return "Please set your API key in the sidebar."
    summary = json.dumps({"medications":meds,"lab_reports":labs[-3:],"caregiver_updates":updates[:3],"alerts":alerts},indent=2)
    PROMPT = f"""You are CareCircle helping manage {profile["name"]}, {profile["age"]}y, conditions: {", ".join(profile.get("conditions",[]))}.
Data: {summary}
Write a warm plain-English daily briefing (max 200 words). Answer: Is {profile["name"]} okay? Anything urgent? One action item?
Never diagnose. Flag stale data. Tone: caring, calm, direct."""
    response = client.messages.create(model="claude-opus-4-5", max_tokens=400, messages=[{"role":"user","content":PROMPT}])
    return response.content[0].text.strip()

def generate_crisis_card(profile, meds):
    client = get_ai_client()
    if not client: return "Please set your API key."
    med_list = "\n".join([f"- {m['name']} {m['dosage']}" for m in meds]) or "No medications on file"
    doctors = ", ".join([f"{d['role']} at {d['hospital']}" for d in profile.get("doctors",[])]) or "None on file"
    PROMPT = f"""CRISIS MODE. Patient: {profile["name"]}, {profile["age"]}y. Conditions: {", ".join(profile.get("conditions",[]))}.
Medications:\n{med_list}\nDoctors: {doctors}
Generate crisis card with: CURRENT MEDICATIONS, NEAREST HOSPITAL, EMERGENCY CONTACTS. Ultra brief. No prose."""
    response = client.messages.create(model="claude-opus-4-5", max_tokens=400, messages=[{"role":"user","content":PROMPT}])
    return response.content[0].text.strip()

def answer_query(query, profile, meds, labs, updates):
    client = get_ai_client()
    if not client: return "Please set your API key."
    summary = json.dumps({"patient":profile,"medications":meds,"lab_reports":labs,"caregiver_updates":updates[:5]},indent=2)
    response = client.messages.create(model="claude-opus-4-5", max_tokens=400,
        system="You are CareCircle. Never diagnose. Always cite source and date. Flag stale/missing data. Plain English. Under 150 words.",
        messages=[{"role":"user","content":f"Profile:\n{summary}\n\nQuestion: {query}"}])
    return response.content[0].text.strip()

def detect_crisis(q):
    return any(k in q.lower() for k in ["chest pain","heart attack","not breathing","unconscious","fainted","collapsed","stroke","emergency","ambulance","fell down","not responding"])

for key in ["active_profile_id","pending_confirmations","briefing","crisis_mode","interaction_result","show_new_profile"]:
    if key not in st.session_state:
        st.session_state[key] = None if key in ["active_profile_id","briefing","interaction_result"] else (False if key in ["crisis_mode","show_new_profile"] else [])

with st.sidebar:
    st.markdown("### 🔵 CareCircle")
    st.markdown("---")
    st.markdown("---")
    st.markdown("**Care Profiles**")
    profiles = db_get_profiles()
    for p in profiles:
        is_active = st.session_state.active_profile_id == p["id"]
        if st.button(f"{'✅ ' if is_active else ''}{p['name']}, {p['age']}y", key=f"p_{p['id']}", use_container_width=True, type="primary" if is_active else "secondary"):
            st.session_state.active_profile_id = p["id"]
            st.session_state.briefing = None
            st.session_state.interaction_result = None
            st.rerun()
    if st.button("➕ Add new profile", use_container_width=True):
        st.session_state.show_new_profile = True
        st.rerun()
    if st.session_state.active_profile_id:
        meds    = db_get_medications(st.session_state.active_profile_id)
        alerts  = db_get_alerts(st.session_state.active_profile_id)
        labs    = db_get_lab_reports(st.session_state.active_profile_id)
        updates = db_get_caregiver_updates(st.session_state.active_profile_id)
        st.markdown("---")
        c1,c2 = st.columns(2)
        c1.metric("Medications", len(meds)); c2.metric("Alerts", len(alerts))
        c1.metric("Lab Reports", len(labs)); c2.metric("Updates", len(updates))
        st.markdown("---")
        st.markdown("**Navigation**")
        page = st.radio("", ["🏠  Daily Briefing","💊  Medications","📄  Prescriptions","🔬  Lab Reports","🗣️  Caregiver Updates","⚠️  Alerts","💬  Ask CareCircle"], label_visibility="collapsed")
    else:
        meds=alerts=labs=updates=[]; page="🏠  Daily Briefing"

if st.session_state.show_new_profile:
    st.markdown("### ➕ Add a Care Profile")
    c1,c2 = st.columns(2)
    with c1:
        nn = st.text_input("Name", placeholder="Dad")
        na = st.number_input("Age", min_value=1, max_value=120, value=67)
        nc = st.multiselect("Conditions", ["Type 2 Diabetes","Hypertension","Heart Disease","Post-cardiac episode","Kidney Disease","Arthritis","COPD","Hypothyroidism","Asthma","Other"])
    with c2:
        st.markdown("**Doctors**")
        d1r=st.text_input("Doctor 1 role",placeholder="Cardiologist"); d1h=st.text_input("Doctor 1 hospital",placeholder="Fortis Hospital")
        d2r=st.text_input("Doctor 2 role",placeholder="Endocrinologist"); d2h=st.text_input("Doctor 2 hospital",placeholder="Apollo Hospital")
    c1,c2=st.columns(2)
    with c1:
        if st.button("✅ Create Profile", type="primary", use_container_width=True):
            if nn:
                doctors=[]; 
                if d1r: doctors.append({"role":d1r,"hospital":d1h})
                if d2r: doctors.append({"role":d2r,"hospital":d2h})
                pid=db_create_profile(nn,na,nc,doctors)
                if pid:
                    st.session_state.active_profile_id=pid; st.session_state.show_new_profile=False
                    st.success(f"Profile created for {nn}!"); st.rerun()
    with c2:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_new_profile=False; st.rerun()
    st.stop()

if not st.session_state.active_profile_id:
    st.markdown('''<div class="cc-header"><h1>🔵 CareCircle</h1><p>Keeping families informed, so they can be family — not coordinators.</p></div>''', unsafe_allow_html=True)
    st.info("👈 Click **Add new profile** in the sidebar to get started." if not profiles else "👈 Select a profile from the sidebar.")
    st.stop()

active_profile = next((p for p in profiles if p["id"]==st.session_state.active_profile_id), None)
if not active_profile: st.error("Profile not found."); st.stop()

critical_count = sum(1 for a in alerts if a.get("severity")=="CRITICAL")
header_sub = f"⚠️ {critical_count} CRITICAL alert(s) for {active_profile['name']}." if critical_count else f"Keeping you informed about {active_profile['name']}."
st.markdown(f'''<div class="cc-header"><h1>🔵 CareCircle — {active_profile["name"]}</h1><p>{header_sub}</p></div>''', unsafe_allow_html=True)

if "Daily Briefing" in page:
    st.markdown(f"### Good morning.")
    st.markdown(f"Here is everything you need to know about **{active_profile['name']}** today.")
    stale_meds = sum(1 for m in meds if is_stale(m.get("date_prescribed"),90))
    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'''<div class="metric-card"><div class="label">Medications</div><div class="value">{len(meds)}</div><div class="sub">{stale_meds} possibly stale</div></div>''',unsafe_allow_html=True)
    with c2: st.markdown(f'''<div class="metric-card"><div class="label">Active Alerts</div><div class="value" style="color:{'#cc0000' if alerts else '#2e7d32'}">{len(alerts)}</div><div class="sub">{'Needs attention' if alerts else 'All clear'}</div></div>''',unsafe_allow_html=True)
    with c3: st.markdown(f'''<div class="metric-card"><div class="label">Lab Reports</div><div class="value">{len(labs)}</div><div class="sub">{'On file' if labs else 'None uploaded'}</div></div>''',unsafe_allow_html=True)
    with c4: st.markdown(f'''<div class="metric-card"><div class="label">Caregiver Updates</div><div class="value">{len(updates)}</div><div class="sub">{'Recent activity' if updates else 'No updates'}</div></div>''',unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)
    if st.button("🔄 Generate Today's Briefing", use_container_width=True, type="primary"):
        with st.spinner("Generating briefing..."):
            st.session_state.briefing = generate_briefing(active_profile, meds, labs, updates, alerts)
    if st.session_state.briefing:
        st.markdown(f'''<div class="briefing-box">{st.session_state.briefing}</div>''', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("#### 🚨 Emergency")
    if st.button("🚨 EMERGENCY — Get Crisis Card", use_container_width=True):
        st.session_state.crisis_mode = True
    if st.session_state.crisis_mode:
        with st.spinner("Generating emergency card..."):
            crisis = generate_crisis_card(active_profile, meds)
        st.markdown(f'''<div class="crisis-card"><h3>🚨 CRISIS CARD — {active_profile["name"].upper()}</h3>{crisis}</div>''', unsafe_allow_html=True)
        if st.button("✅ Emergency resolved"):
            st.session_state.crisis_mode=False; st.rerun()

elif "Medications" in page:
    st.markdown(f"### 💊 {active_profile['name']}'s Medications")
    with st.expander("➕ Upload a new prescription", expanded=not meds):
        uploaded = st.file_uploader("Upload prescription photo", type=["jpg","jpeg","png","webp"])
        if uploaded:
            st.image(uploaded, caption="Uploaded prescription", width=400)
            if st.button("🔍 Extract medications", type="primary"):
                with st.spinner("Reading prescription..."):
                    result, err = ingest_prescription(uploaded.read(), uploaded.name)
                if err: st.error(f"Error: {err}")
                elif result:
                    if not result.get("extraction_possible"): st.error(f"Could not read: {result.get('reason_if_low','Image unclear')}")
                    else:
                        added=0
                        extracted_names=[]
                        doctor_name="Unknown"
                        date_prescribed=None
                        for med in result.get("medications",[]):
                            if med.get("ready_to_add"):
                                db_add_medication(st.session_state.active_profile_id, {"id":str(uuid.uuid4())[:8],"name":med["medication_name"],"dosage":med["dosage"],"frequency":med["frequency"],"duration":med.get("duration"),"instructions":med.get("instructions"),"prescribing_doctor":med.get("prescribing_doctor","Unknown"),"date_prescribed":med.get("date_prescribed"),"source":uploaded.name,"date_ingested":datetime.now().strftime("%Y-%m-%d"),"verified":True,"confidence":"HIGH"})
                                extracted_names.append(f"{med['medication_name']} {med['dosage']}")
                                if med.get("prescribing_doctor"): doctor_name=med["prescribing_doctor"]
                                if med.get("date_prescribed"): date_prescribed=med["date_prescribed"]
                                added+=1
                            else: st.session_state.pending_confirmations.append({"medication_name":med.get("medication_name","Unknown"),"fields_to_confirm":med.get("needs_confirmation",[]),"partial_data":med,"source":uploaded.name})
                        db_save_prescription(st.session_state.active_profile_id, {"id":str(uuid.uuid4())[:8],"filename":uploaded.name,"prescribed_by":doctor_name,"date_prescribed":date_prescribed,"medications_extracted":extracted_names,"notes":result.get("document_notes",""),"date_uploaded":datetime.now().strftime("%Y-%m-%d")})
                        if added: st.success(f"✅ {added} medication(s) added.")
                        if result.get("document_notes"): st.info(f"📋 {result['document_notes']}")
                        st.rerun()
    if st.session_state.pending_confirmations:
        st.markdown("#### ⚠️ Needs Confirmation")
        for i,item in enumerate(st.session_state.pending_confirmations):
            st.markdown(f'''<div class="confirm-card"><strong>⚠️ {item["medication_name"]}</strong> — unclear: {", ".join(item["fields_to_confirm"])}</div>''',unsafe_allow_html=True)
            c1,c2=st.columns(2)
            with c1:
                cn=st.text_input("Name",value=item["medication_name"],key=f"cn{i}")
                cd=st.text_input("Dosage",value=item["partial_data"].get("dosage",""),key=f"cd{i}")
                cf=st.text_input("Frequency",value=item["partial_data"].get("frequency",""),key=f"cf{i}")
            with c2:
                if st.button("✅ Add",key=f"add{i}"):
                    db_add_medication(st.session_state.active_profile_id,{"id":str(uuid.uuid4())[:8],"name":cn,"dosage":cd,"frequency":cf,"source":item["source"],"date_ingested":datetime.now().strftime("%Y-%m-%d"),"verified":True,"confidence":"MANUALLY_CONFIRMED"})
                    st.session_state.pending_confirmations.pop(i); st.rerun()
                if st.button("❌ Discard",key=f"dis{i}"):
                    st.session_state.pending_confirmations.pop(i); st.rerun()
    meds=db_get_medications(st.session_state.active_profile_id)
    if not meds: st.info("No medications yet. Upload a prescription above.")
    else:
        st.markdown(f"#### Active Medications ({len(meds)})")
        for m in meds:
            stale=is_stale(m.get("date_prescribed"),90)
            tag='<span class="tag-stale">⚠️ POSSIBLY STALE</span>' if stale else '<span class="tag-verified">✓ VERIFIED</span>'
            col_med, col_del = st.columns([10,1])
            with col_med:
                st.markdown(f'''<div class="med-card {'stale' if stale else ''}"><div class="mname">{m["name"]} {m["dosage"]} &nbsp; {tag}</div><div class="minfo">📅 {m["frequency"]}{" &nbsp;·&nbsp; "+m["instructions"] if m.get("instructions") else ""}</div><div class="msrc">Prescribed {days_ago(m.get("date_prescribed"))} by {m.get("prescribing_doctor","Unknown")} &nbsp;·&nbsp; Source: {m.get("source","Unknown")}</div></div>''',unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_med_{m['id']}", help="Delete this medication"):
                    db_delete_medication(m["id"]); st.rerun()
        st.markdown("<br>",unsafe_allow_html=True)
        if len(meds)>=2:
            if st.button("🔍 Check for Drug Interactions", type="primary", use_container_width=True):
                with st.spinner("Checking interactions..."):
                    result=run_interaction_check(st.session_state.active_profile_id,meds,active_profile.get("conditions",[]))
                if result: st.session_state.interaction_result=result
        if st.session_state.get("interaction_result"):
            result=st.session_state.interaction_result
            icons={"CRITICAL":"🚨","HIGH":"⚠️","MEDIUM":"📋","LOW":"ℹ️","NONE":"✅"}
            st.markdown("---"); st.markdown("#### 🔍 Drug Interaction Results")
            if result["interactions_found"]:
                for ix in result.get("interactions",[]):
                    sev=ix["severity"]; cls="alert-critical" if sev=="CRITICAL" else "alert-high" if sev=="HIGH" else "alert-low"
                    st.markdown(f'''<div class="{cls}"><strong>{icons.get(sev,"ℹ️")} {sev}: {" + ".join(ix["drugs_involved"])}</strong><br><span style="font-size:14px">{ix["what_happens"]}</span><br><br><strong>What to do:</strong> {ix["what_to_do"]}<br><strong>Urgency:</strong> {ix["urgency"]}</div>''',unsafe_allow_html=True)
            else: st.success(f"✅ {result.get('reassurance','No significant interactions found.')}")

elif "Prescriptions" in page:
    st.markdown(f"### 📄 {active_profile['name']}'s Prescription History")
    st.markdown("Every prescription ever uploaded — your complete medication paper trail.")

    prescriptions = db_get_prescriptions(st.session_state.active_profile_id)

    if not prescriptions:
        st.info("No prescriptions uploaded yet. Go to 💊 Medications to upload one.")
    else:
        st.markdown(f"**{len(prescriptions)} prescription(s) on file**")
        for rx in prescriptions:
            meds_list = ", ".join(rx.get("medications_extracted") or []) or "None extracted"
            col_rx, col_del = st.columns([10,1])
            with col_rx:
                st.markdown(f"""<div class="med-card">
                    <div class="mname">📄 {rx.get("filename","Unknown file")}</div>
                    <div class="minfo">
                        <strong>Prescribed by:</strong> {rx.get("prescribed_by","Unknown")} &nbsp;·&nbsp;
                        <strong>Date:</strong> {rx.get("date_prescribed","Not specified")}
                    </div>
                    <div class="minfo"><strong>Medications extracted:</strong> {meds_list}</div>
                    {f'<div class="minfo"><strong>Notes:</strong> {rx["notes"]}</div>' if rx.get("notes") else ""}
                    <div class="msrc">Uploaded {days_ago(rx.get("date_uploaded"))}</div>
                </div>""", unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_rx_{rx['id']}", help="Delete this prescription record"):
                    db_delete_prescription(rx["id"])
                    st.rerun()

elif "Lab Reports" in page:
    st.markdown(f"### 🔬 {active_profile['name']}'s Lab Reports")
    with st.expander("➕ Add a lab result", expanded=True):
        c1,c2,c3=st.columns(3)
        with c1: tn=st.text_input("Test name",placeholder="Fasting Blood Sugar"); tv=st.text_input("Value",placeholder="180"); tu=st.selectbox("Unit",["mg/dL","mmol/L","g/dL","%","IU/L","mEq/L","other"])
        with c2: rr=st.text_input("Reference range",placeholder="70-100"); td=st.date_input("Date of test",value=date.today()); ln=st.text_input("Lab / Hospital")
        with c3:
            st.markdown("<br><br>",unsafe_allow_html=True)
            if st.button("➕ Add",type="primary",use_container_width=True):
                if tn and tv:
                    db_add_lab_report(st.session_state.active_profile_id,{"id":str(uuid.uuid4())[:8],"test":tn,"value":tv,"unit":tu,"reference_range":rr,"date":str(td),"lab":ln,"date_ingested":datetime.now().strftime("%Y-%m-%d")})
                    st.success(f"✅ {tn} added."); st.rerun()
    labs=db_get_lab_reports(st.session_state.active_profile_id)
    if not labs: st.info("No lab reports yet.")
    else:
        for r in labs:
            stale=is_stale(r.get("date"),30)
            tag='<span class="tag-stale">⚠️ STALE</span>' if stale else '<span class="tag-verified">✓ RECENT</span>'
            col_lab, col_del = st.columns([10,1])
            with col_lab:
                st.markdown(f'''<div class="med-card {'stale' if stale else ''}"><div class="mname">{r["test"]}: {r["value"]} {r["unit"]} &nbsp; {tag}</div><div class="minfo">Reference range: {r.get("reference_range","Not specified")}</div><div class="msrc">Date: {r.get("date","?")} &nbsp;·&nbsp; Lab: {r.get("lab","?")}</div></div>''',unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_lab_{r['id']}", help="Delete this report"):
                    db_delete_lab_report(r["id"]); st.rerun()

elif "Caregiver" in page:
    st.markdown(f"### 🗣️ Caregiver Updates for {active_profile['name']}")
    with st.expander("➕ Log an update", expanded=True):
        ut=st.text_area("What did the caregiver report?",placeholder="Uncle ne aaj BP ki dawai li...")
        c1,c2,c3=st.columns(3)
        with c1: ud=st.date_input("Date",value=date.today()); mt=st.checkbox("Medications taken")
        with c2: hm=st.checkbox("Had meals"); sym=st.text_input("Symptoms (if any)")
        with c3:
            st.markdown("<br><br>",unsafe_allow_html=True)
            if st.button("➕ Log Update",type="primary",use_container_width=True):
                if ut:
                    db_add_caregiver_update(st.session_state.active_profile_id,{"id":str(uuid.uuid4())[:8],"text":ut,"date":str(ud),"medications_taken":mt,"had_meals":hm,"symptoms":sym,"source":"Caregiver-A","date_ingested":datetime.now().strftime("%Y-%m-%d")})
                    st.success("✅ Update logged."); st.rerun()
    updates=db_get_caregiver_updates(st.session_state.active_profile_id)
    if updates:
        for u in updates:
            sym=f" · Symptoms: _{u['symptoms']}_" if u.get("symptoms") else ""
            col_upd, col_del = st.columns([10,1])
            with col_upd:
                st.markdown(f'''<div class="med-card"><div class="mname">Caregiver-A · {days_ago(u.get("date"))}</div><div class="minfo">{u["text"]}</div><div class="msrc">Meds: {'✓' if u.get("medications_taken") else '?'} · Meals: {'✓' if u.get("had_meals") else '?'}{sym} · <em>interpreted</em></div></div>''',unsafe_allow_html=True)
            with col_del:
                if st.button("🗑️", key=f"del_upd_{u['id']}", help="Delete this update"):
                    db_delete_caregiver_update(u["id"]); st.rerun()

elif "Alerts" in page:
    st.markdown(f"### ⚠️ Alerts — {active_profile['name']}")
    alerts=db_get_alerts(st.session_state.active_profile_id)
    if not alerts: st.success("✅ No active alerts.")
    else:
        for a in alerts:
            sev=a.get("severity","LOW"); cls="alert-critical" if sev=="CRITICAL" else "alert-high" if sev=="HIGH" else "alert-low"
            icon="🚨" if sev=="CRITICAL" else "⚠️" if sev=="HIGH" else "ℹ️"
            drugs=" + ".join(a.get("drugs") or [])
            st.markdown(f'''<div class="{cls}"><strong>{icon} {sev}: {drugs}</strong><br><span style="font-size:14px">{a.get("summary","")}</span><br><br><strong>What to do:</strong> {a.get("action","")}<br><strong>Urgency:</strong> {a.get("urgency","")}</div>''',unsafe_allow_html=True)
    st.markdown("---"); st.markdown("**Staleness Check**")
    sm=[m for m in meds if is_stale(m.get("date_prescribed"),90)]; sl=[r for r in labs if is_stale(r.get("date"),30)]
    if sm: st.warning(f"⚠️ {len(sm)} prescription(s) older than 90 days."); [st.markdown(f"  · {m['name']} {m['dosage']} — {days_ago(m.get('date_prescribed'))}") for m in sm]
    if sl: st.warning(f"⚠️ {len(sl)} lab report(s) older than 30 days.")
    if not sm and not sl: st.success("✅ All data within freshness thresholds.")

elif "Ask" in page:
    st.markdown(f"### 💬 Ask about {active_profile['name']}")
    query=st.text_input("Your question",placeholder=f"What medications is {active_profile['name']} on?")
    if query:
        if detect_crisis(query): st.error("🚨 Emergency detected. Go to Daily Briefing and use the Crisis Card button immediately.")
        else:
            if st.button("Ask",type="primary"):
                with st.spinner("Checking profile..."):
                    answer=answer_query(query,active_profile,meds,labs,updates)
                st.markdown(f'''<div class="briefing-box">{answer}</div>''',unsafe_allow_html=True)
    st.markdown("---"); st.markdown("**Example questions:**")
    [st.markdown(f"  · _{e}_") for e in [f"What medications is {active_profile['name']} on?","When was the last lab report?","What did the caregiver say today?","Are any prescriptions out of date?","Is there anything urgent?"]]

st.markdown("---")
st.markdown('<p style="font-size:11px;color:#aaa;text-align:center;">CareCircle · 100xEngineers Applied AI Capstone · Not a medical device. Always consult a doctor.</p>',unsafe_allow_html=True)
