"""
test_voice_assistant_and_tracker.py - Automated Verification Suite for:
1. Persistent 'Running the Task' live tracker.
2. Two-Way Voice Assistant Q&A in Tamil & English.
3. Web Speech API synthesis generation.
"""

import os
import sys
import json
import time

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agent_voice_chat import (
    load_tasks_db,
    get_agent_voice_status_reply,
    generate_speech_synthesis_html,
    is_tamil_query
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks_db.json")

print("\n" + "="*60)
print("     VERIFYING PERSISTENT TRACKER & TWO-WAY VOICE ASSISTANT     ")
print("="*60 + "\n")

# Backup original database
original_db_content = None
if os.path.exists(DB_PATH):
    with open(DB_PATH, "r", encoding="utf-8") as f:
        original_db_content = f.read()

try:
    # --------------------------------------------------------------------------
    # TEST 1: SIMULATE RUNNING TASK IN TASKS_DB.JSON
    # --------------------------------------------------------------------------
    print("--- [TEST 1] SIMULATING RUNNING TASK IN tasks_db.json ---")
    simulated_task_id = "task_test_running_live_001"
    simulated_db = {
        "tasks": {
            simulated_task_id: {
                "id": simulated_task_id,
                "title": "மாணவர் கற்றல் போர்டல் (Student Learning Hub)",
                "prompt": "மாணவர்களுக்கான முழுமையான கற்றல் போர்டல் மற்றும் தேர்வு மேலாண்மை தளம்",
                "task_type": "frontend",
                "folder_name": "student_learning_hub",
                "status": "RUNNING",
                "current_step": 3,
                "max_steps": 5,
                "progress_percent": 60,
                "current_action": "Synthesizing Core Code & Responsive UI",
                "active_model_or_bridge": "Gemini 2.5 Flash / OpenRouter Free Loop",
                "created_at": "2026-11-09T11:10:00.000000",
                "updated_at": "2026-11-09T11:15:00.000000",
                "logs": [
                    "[11:10:00] Task initialized. Background worker dispatched.",
                    "[11:11:30] Step 1/5 Completed: 5D Plan formulated via Gemini 2.5 Flash.",
                    "[11:13:00] Step 2/5 Completed: Schema & mock dataset initialized.",
                    "[11:15:00] Step 3/5 In Progress: Synthesizing complete core logic and responsive interface..."
                ]
            }
        },
        "metrics": {
            "total_tasks": 1,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "total_tokens": 1250
        }
    }

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(simulated_db, f, indent=2, ensure_ascii=False)

    loaded_db = load_tasks_db()
    running_task = [t for t in loaded_db["tasks"].values() if t.get("status") == "RUNNING"][0]
    assert running_task["current_step"] == 3
    assert running_task["progress_percent"] == 60
    assert running_task["status"] == "RUNNING"
    print("✅ Simulated RUNNING task successfully written and verified in tasks_db.json.")
    print(f"   Task: '{running_task['title']}' | Step: {running_task['current_step']}/5 ({running_task['progress_percent']}%)")

    # --------------------------------------------------------------------------
    # TEST 2: TAMIL STATUS INQUIRIES ("இந்த ப்ராஜெக்ட் எங்க போயிட்டு இருக்கு?")
    # --------------------------------------------------------------------------
    print("\n--- [TEST 2] ASKING: 'இந்த ப்ராஜெக்ட் எங்க போயிட்டு இருக்கு?' (Tamil Status) ---")
    q1 = "இந்த ப்ராஜெக்ட் எங்க போயிட்டு இருக்கு?"
    assert is_tamil_query(q1) is True
    res1 = get_agent_voice_status_reply(q1, simulated_db)

    print("🗣️ Agent Spoken Reply:", res1["spoken_text"])
    print("🖥️ Agent Display Text:\n", res1["display_text"])
    assert res1["lang"] == "ta-IN"
    assert res1["current_step"] == 3
    assert res1["progress_percent"] == 60
    assert "மாணவர் கற்றல் போர்டல்" in res1["spoken_text"]
    assert "3" in res1["spoken_text"]
    print("✅ Test 2 Passed: Accurate spoken progress delivered in Tamil.")

    # --------------------------------------------------------------------------
    # TEST 3: TAMIL ACTION INQUIRY ("இப்ப என்ன பண்ணுது?")
    # --------------------------------------------------------------------------
    print("\n--- [TEST 3] ASKING: 'இப்ப என்ன பண்ணுது?' (Tamil Action Query) ---")
    q2 = "இப்ப என்ன பண்ணுது?"
    res2 = get_agent_voice_status_reply(q2, simulated_db)

    print("🗣️ Agent Spoken Reply:", res2["spoken_text"])
    assert res2["lang"] == "ta-IN"
    assert "Synthesizing Core Code" in res2["spoken_text"] or "பணி" in res2["spoken_text"]
    print("✅ Test 3 Passed: Live current action accurately reported in Tamil.")

    # --------------------------------------------------------------------------
    # TEST 4: TAMIL MODEL INQUIRY ("எந்த மாடல் யூஸ் பண்ணுது?")
    # --------------------------------------------------------------------------
    print("\n--- [TEST 4] ASKING: 'எந்த மாடல் யூஸ் பண்ணுது?' (Tamil Model Query) ---")
    q3 = "எந்த மாடல் யூஸ் பண்ணுது?"
    res3 = get_agent_voice_status_reply(q3, simulated_db)

    print("🗣️ Agent Spoken Reply:", res3["spoken_text"])
    assert res3["lang"] == "ta-IN"
    assert "Gemini 2.5 Flash" in res3["spoken_text"] or "OpenRouter" in res3["spoken_text"]
    print("✅ Test 4 Passed: Active model/engine clearly spoken in Tamil.")

    # --------------------------------------------------------------------------
    # TEST 5: ENGLISH QUERY ("Where is this project at?")
    # --------------------------------------------------------------------------
    print("\n--- [TEST 5] ASKING: 'Where is this project at?' (English Query) ---")
    q4 = "Where is this project at?"
    res4 = get_agent_voice_status_reply(q4, simulated_db)

    print("🗣️ Agent Spoken Reply:", res4["spoken_text"])
    assert res4["lang"] == "en-US"
    assert "Step 3" in res4["spoken_text"]
    assert "60" in res4["spoken_text"]
    print("✅ Test 5 Passed: Natural English response returned for English query.")

    # --------------------------------------------------------------------------
    # TEST 6: WEB SPEECH API HTML COMPONENT GENERATION
    # --------------------------------------------------------------------------
    print("\n--- [TEST 6] TESTING WEB SPEECH API HTML GENERATION ---")
    tts_html = generate_speech_synthesis_html(res1["spoken_text"], lang=res1["lang"], autoplay=True)
    assert "window.speechSynthesis" in tts_html
    assert "SpeechSynthesisUtterance" in tts_html
    assert "ta-IN" in tts_html
    assert "speakAgentResponse" in tts_html
    print("✅ Test 6 Passed: High-fidelity browser Web Speech API component generated.")

    # --------------------------------------------------------------------------
    # TEST 7: SIMULATE TASK COMPLETION & COMPLETED STATUS CHECK
    # --------------------------------------------------------------------------
    print("\n--- [TEST 7] SIMULATING TASK COMPLETION ('டாஸ்க் முடிஞ்சுடுச்சா?') ---")
    simulated_db["tasks"][simulated_task_id]["status"] = "COMPLETED"
    simulated_db["tasks"][simulated_task_id]["current_step"] = 5
    simulated_db["tasks"][simulated_task_id]["progress_percent"] = 100
    simulated_db["tasks"][simulated_task_id]["output_file"] = "workspace/student_learning_hub/index.html"
    simulated_db["tasks"][simulated_task_id]["duration_seconds"] = int(45.2)

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(simulated_db, f, indent=2, ensure_ascii=False)

    q5 = "டாஸ்க் முடிஞ்சுடுச்சா?"
    res5 = get_agent_voice_status_reply(q5, simulated_db)
    print("🗣️ Agent Spoken Reply:", res5["spoken_text"])
    assert "வெற்றிகரமாக முடிவடைந்துவிட்டது" in res5["spoken_text"] or "100%" in res5["spoken_text"]
    print("✅ Test 7 Passed: Completed task accurately recognized and celebrated in speech.")

    print("\n" + "="*60)
    print("       ALL 7 TESTS PASSED WITH 100% SUCCESS!       ")
    print("="*60 + "\n")

finally:
    # Restore original tasks_db.json
    if original_db_content is not None:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            f.write(original_db_content)
        print("ℹ️ Original tasks_db.json restored.")

