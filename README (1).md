# CareCircle — Setup & Run Guide

## Project Structure
```
carecircle/
├── core/
│   └── ingest_prescription.py   ← START HERE
├── data/
│   ├── profiles/
│   │   └── dad_001.json         ← patient profile (the source of truth)
│   └── uploads/                 ← drop prescription images here
└── utils/
```

## Setup (one time)

```bash
pip install anthropic pillow
export ANTHROPIC_API_KEY="your-key-here"
```

Get your API key from: https://console.anthropic.com

## Run the prescription ingester

```bash
cd carecircle
python core/ingest_prescription.py data/uploads/your_prescription.jpg
```

## What it does

1. Reads the prescription image using Claude Vision
2. Extracts: medication name, dosage, frequency, doctor, date
3. Confidence scores every field (HIGH / MEDIUM / LOW)
4. Only adds to dad_001.json if name + dosage + frequency are ALL high confidence
5. Flags anything uncertain for Meera to confirm manually

## The hard rule

**Nothing enters the medication list unverified.**
If the system isn't sure what it read — it says so.

## Check the profile after ingestion

```bash
cat data/profiles/dad_001.json
```

## What's next (Day 2)
- `core/ingest_lab_report.py` — PDF lab report ingester
- `core/check_interactions.py` — drug interaction checker
- `core/daily_briefing.py`    — "Is Dad okay?" generator
