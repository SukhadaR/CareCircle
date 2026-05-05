import streamlit as st
# CARECIRCLE v3.0 - COURSE TRACKING TEST
from datetime import datetime, date, timedelta
import re, calendar as cal

st.title("🔵 CareCircle v3.0")

def parse_any_date(date_str):
    if not date_str: return None
    for fmt in ["%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y"]:
        try: return datetime.strptime(date_str.strip()[:20], fmt).date()
        except: continue
    return None

def get_course_status(date_prescribed, duration_str):
    dur = str(duration_str or "").strip()
    dt = str(date_prescribed or "").strip()
    if not dur or not dt: return None
    start = parse_any_date(dt)
    if not start: return None
    dl = dur.lower()
    if any(x in dl for x in ["ongoing","continue"]): return None
    month_match = re.search(r"(\d+)\s*month", dl)
    if month_match:
        months = int(month_match.group(1))
        m = start.month + months
        y = start.year + (m-1)//12
        m = ((m-1)%12)+1
        d = min(start.day, cal.monthrange(y,m)[1])
        end = date(y,m,d)
    else:
        day_match = re.search(r"(\d+)\s*day", dl)
        if not day_match: return None
        end = start + timedelta(days=int(day_match.group(1)))
    return (end - date.today()).days

# Test data
meds = [
    {"name": "Pantoprazole 40mg", "date_prescribed": "30 April 2026", "duration": "7 days only"},
    {"name": "Amlodipine 5mg", "date_prescribed": "10 February 2026", "duration": "3 months"},
    {"name": "Metformin 500mg", "date_prescribed": "10 February 2026", "duration": "Ongoing"},
]

for m in meds:
    status = get_course_status(m["date_prescribed"], m["duration"])
    st.write(f"**{m['name']}** | date={m['date_prescribed']} | dur={m['duration']} | status={status}")
    if status is not None:
        if status > 3: st.success(f"⏱️ {status} days left")
        elif status > 0: st.warning(f"⚠️ {status} day(s) left")
        elif status == 0: st.error("🔴 Course ends TODAY")
        else: st.error(f"🔴 Course ended {abs(status)} day(s) ago")
    else:
        st.info("No end date — ongoing")
    st.markdown("---")
