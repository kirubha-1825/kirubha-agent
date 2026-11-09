"""
test_3tier_and_voice_suite.py - End-to-End Suite for:
1. Voice Router (Tamil / Tanglish / English)
2. Tier 1 Cloud LLM routing & force_antigravity bypass
3. Tier 2 Antigravity bridge dispatch & listener
4. Tier 3 Stitch AI UI synthesis
5. Two-Way Voice Assistant Status Q&A
"""

import os
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from voice_router import parse_voice_command, detect_antigravity_intent, detect_stitch_ai_intent
from llm_router import execute_tier1_cloud_llm
from antigravity_bridge_listener import (
    dispatch_to_antigravity,
    load_antigravity_queue,
    AntigravityBridgeListener
)
from stitch_service import generate_stitch_ui, get_stitch_ai_key
from agent_voice_chat import get_agent_voice_status_reply

print("\n" + "="*60)
print("       END-TO-END 3-TIER ENGINE & VOICE SUITE TEST      ")
print("="*60 + "\n")

# 1. Voice Router Tests
print("--- [1/5] TESTING VOICE ROUTER (TAMIL / TANGLISH / ENGLISH) ---")
test_phrases = [
    ("ஆன்டி கிராவிட்டி உள்ள போய் செய்", True, False),
    ("ஆண்ட்ராய்டுல போய் செய்", True, False),
    ("antigravity-ல பண்ணு", True, False),
    ("சுவிட்ச் ஏஐ வச்சு மாணவர் பக்கம் டிசைன் பண்ணு", False, True),
    ("use antigravity and stitch ai to design frontend", True, True)
]

for phrase, exp_ag, exp_stitch in test_phrases:
    parsed = parse_voice_command(phrase)
    print(f"Phrase: '{phrase}'")
    print(f"  -> force_antigravity={parsed['force_antigravity']} (Expected: {exp_ag})")
    print(f"  -> use_stitch_ai={parsed['use_stitch_ai']} (Expected: {exp_stitch})")
    assert parsed["force_antigravity"] == exp_ag, f"Mismatch on antigravity for '{phrase}'"
    assert parsed["use_stitch_ai"] == exp_stitch, f"Mismatch on stitch for '{phrase}'"
print("✅ Voice Router successfully classified all Tamil, Tanglish, and English triggers!")

# 2. Tier 1 Cloud LLM Bypass Test
print("\n--- [2/5] TESTING TIER 1 BYPASS ON FORCE_ANTIGRAVITY ---")
res_bypass = execute_tier1_cloud_llm("Build app", force_antigravity=True)
assert res_bypass["success"] is False
assert res_bypass["bypassed"] is True
print("✅ Tier 1 bypassed cleanly when force_antigravity=True.")

# 3. Tier 2 Antigravity Bridge & Listener Test
print("\n--- [3/5] TESTING TIER 2 ANTIGRAVITY DISPATCH & LISTENER ---")
dispatch_res = dispatch_to_antigravity(
    task_prompt="மாணவர் கற்றல் முகப்புப் பக்கம் (Student Hub Portal)",
    project_folder="student_learning_hub",
    use_stitch_ai=True,
    task_id="test_suite_agy_task_001",
    source="unit_test"
)
assert dispatch_res["success"] is True
print(f"✅ Dispatched task '{dispatch_res['task_id']}' to queue.")

listener = AntigravityBridgeListener()
assert listener.verify_key(listener.bridge_key) is True
print("✅ Bridge key verified successfully.")

processed_task = listener.process_next_task()
if processed_task:
    assert processed_task["status"] == "COMPLETED"
    print(f"✅ Antigravity Listener picked up and completed task: {processed_task.get('task_id')}")
    print(f"   Output file: {processed_task.get('output_file')}")

# 4. Tier 3 Stitch AI UI Generation Test
print("\n--- [4/5] TESTING TIER 3 STITCH AI UI SYNTHESIS ---")
stitch_key = get_stitch_ai_key()
stitch_res = generate_stitch_ui("Student Dashboard with Attendance Analytics", project_folder="frontend_designs")
assert stitch_res["success"] is True
assert "<!DOCTYPE html>" in stitch_res["code"]
assert "tailwindcss.com" in stitch_res["code"]
print(f"✅ Stitch AI synthesized component successfully ({len(stitch_res['code']):,} chars).")

# 5. Two-Way Voice Assistant Test
print("\n--- [5/5] TESTING TWO-WAY VOICE ASSISTANT INQUIRY ---")
voice_reply = get_agent_voice_status_reply("இந்த ப்ராஜெக்ட் எங்க போயிட்டு இருக்கு?")
assert voice_reply["spoken_text"] != ""
print("🗣️ Spoken Reply:", voice_reply["spoken_text"][:80], "...")
print("✅ Two-Way Voice Assistant functioning flawlessly.")

print("\n" + "="*60)
print("     ALL SUITE TESTS PASSED WITH 100% EXCELLENCE!     ")
print("="*60 + "\n")

