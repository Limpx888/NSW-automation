import requests
import sqlite3
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ================= CONFIGURATION AREA =================
API_URL = "http://127.0.0.1:8000/workflow/diagnose"
TARGET_EMAIL = "cx330.june@gmail.com"  # Configured for current user account
DB_PATH = "data/scan_cases.db" if Path("data/scan_cases.db").exists() else "data/dara.db"
TOTAL_CASES = 100
# ======================================================

# Define 10 realistic mixed industrial defect profiles (Defect class + Operator answers)
profiles = [
    {"class": "excess_volume", "answers": {"amount": "too_large", "frequency": "progressive", "recent_change": "none", "location": "multiple", "problem_description": "Paste slumping and spreading beyond pads."}},
    {"class": "excess_volume", "answers": {"amount": "spreading", "frequency": "continuous", "recent_change": "parameters", "location": "single", "problem_description": "Bridging on QFN pins after parameter adjustment."}},
    {"class": "insufficient_volume", "answers": {"amount": "too_small", "frequency": "after_idle", "recent_change": "none", "location": "multiple", "problem_description": "First few boards have starved joints after lunch break."}},
    {"class": "missing_deposit", "answers": {"amount": "missing", "frequency": "continuous", "recent_change": "nozzle", "location": "single", "problem_description": "No paste on pad after stencil cleaning."}},
    {"class": "voiding", "answers": {"amount": "unknown", "frequency": "occasional", "recent_change": "none", "location": "multiple", "problem_description": "X-ray shows voids in thermal pads."}},
    {"class": "tombstoning", "answers": {"amount": "inconsistent", "frequency": "occasional", "recent_change": "none", "location": "multiple", "problem_description": "0402 components standing up on one end."}},
    {"class": "solder_balling", "answers": {"amount": "spreading", "frequency": "continuous", "recent_change": "syringe", "location": "multiple", "problem_description": "Micro solder balls scattered across the board."}},
    {"class": "stringing", "answers": {"amount": "stringing", "frequency": "continuous", "recent_change": "parameters", "location": "multiple", "problem_description": "Dog-ears and tailing on every dispense point."}},
    {"class": "cold_joint", "answers": {"amount": "unknown", "frequency": "progressive", "recent_change": "none", "location": "multiple", "problem_description": "Dull joints with poor wetting."}},
    {"class": "shifting", "answers": {"amount": "unknown", "frequency": "occasional", "recent_change": "none", "location": "single", "problem_description": "Components skewed after placement."}}
]

print(f"🚀 [1/2] Simulating diagnostics for {TOTAL_CASES} historical cases via API ({API_URL})...")
print(f"   Target user email: {TARGET_EMAIL}")
print(f"   Target database: {DB_PATH}")

# Step 1: Generate complete scan and learning records via API
success_count = 0
for i in range(TOTAL_CASES):
    profile = random.choice(profiles)
    payload = {
        "defect_class": profile["class"],
        "confidence": round(random.uniform(0.75, 0.98), 2),
        "detection_count": random.randint(1, 5),
        "user_email": TARGET_EMAIL,
        "answers": profile["answers"]
    }
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            success_count += 1
        else:
            print(f"⚠️ API returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"⚠️ API request failed, please check if the backend is running: {e}")
        break
    
    if (i + 1) % 10 == 0:
        print(f"   -> {i + 1}/{TOTAL_CASES} cases generated...")

print(f"✅ Case generation complete! Total successfully created: {success_count}")
print(f"⏳ [2/2] Starting the time machine to randomly scatter data between Jan and Sep 2026...")

# Step 2: Connect to SQLite database and tamper with timestamps
# Set the time range: January 1, 2026 to September 17, 2026 (Today)
start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
end_date = datetime(2026, 9, 17, 11, 45, tzinfo=timezone.utc)
time_difference = end_date - start_date

def get_random_date():
    random_seconds = random.randint(0, int(time_difference.total_seconds()))
    return (start_date + timedelta(seconds=random_seconds)).isoformat()

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Inspect column names to handle schema differences safely
    cursor.execute("PRAGMA table_info(scan_cases)")
    scan_cols = [col[1] for col in cursor.fetchall()]
    scan_id_col = "case_id" if "case_id" in scan_cols else ("session_id" if "session_id" in scan_cols else "id")
    
    # Find all scan_cases belonging to the user and update the time
    cursor.execute(f"SELECT {scan_id_col} FROM scan_cases WHERE user_email = ?", (TARGET_EMAIL,))
    scan_cases = cursor.fetchall()
    
    for case in scan_cases:
        fake_date = get_random_date()
        cursor.execute(f"UPDATE scan_cases SET created_at = ?, updated_at = ? WHERE {scan_id_col} = ?", 
                       (fake_date, fake_date, case[0]))
        
    cursor.execute("PRAGMA table_info(learning_cases)")
    learn_cols = [col[1] for col in cursor.fetchall()]
    learn_id_col = "case_id" if "case_id" in learn_cols else ("session_id" if "session_id" in learn_cols else "id")

    # Synchronize the time for learning_cases
    cursor.execute(f"SELECT {learn_id_col} FROM learning_cases WHERE user_email = ?", (TARGET_EMAIL,))
    learning_cases = cursor.fetchall()
    
    for case in learning_cases:
        fake_date = get_random_date()
        cursor.execute(f"UPDATE learning_cases SET created_at = ?, updated_at = ? WHERE {learn_id_col} = ?", 
                       (fake_date, fake_date, case[0]))
        
    conn.commit()
    conn.close()
    print(f"🎉 Success! Updated {len(scan_cases)} scan cases and {len(learning_cases)} learning cases for '{TARGET_EMAIL}'.")
    print(f"🎉 Your dashboard is now backed by 9 months of realistic historical data!")
    print(f"👉 Go ahead and refresh your DARA Dashboard and History pages to see the results!")
    
except Exception as e:
    print(f"⚠️ Database update failed, please verify if the DB_PATH '{DB_PATH}' is correct: {e}")
