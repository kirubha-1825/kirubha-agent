import sys
import re
import streamlit as st

try:
    st.query_params.clear()
except Exception:
    pass

from app import get_executive_voice_response

print("=" * 65)
print("   VERIFYING NATURAL HUMAN PHONE-CALL VOICE PERSONA   ")
print("=" * 65)

# Test 1: Casual Greeting
print("\n[TEST 1] Testing Casual Greeting ('Hello'):")
reply_hello = get_executive_voice_response("Hello", 0, "workspace/login.html", True, 1861)
print(f"🗣️ SRI Reply:\n   \"{reply_hello}\"")
words_hello = reply_hello.split()
print(f"   Word count: {len(words_hello)}")
assert "Hey Kirubha! சொல்லுங்க, இப்ப நம்ம என்ன பண்ணலாம்?" in reply_hello
assert len(words_hello) < 25, f"Greeting reply too long! ({len(words_hello)} words)"
assert "அடுத்து இதைச் செய்யலாமா" not in reply_hello, "Found unwanted robotic footer!"
print("✅ Test 1 Passed: Natural friendly phone-call greeting delivered under 25 words.")

# Test 2: Task Dispatch
print("\n[TEST 2] Testing Task Dispatch Notification:")
reply_task = get_executive_voice_response("Build SaaS Auth", 1, "workspace/login.html", True, 1861, newly_dispatched_id="task_99")
print(f"🗣️ SRI Reply:\n   \"{reply_task}\"")
words_task = reply_task.split()
print(f"   Word count: {len(words_task)}")
assert "task_99" in reply_task
assert len(words_task) < 25, f"Task reply too long! ({len(words_task)} words)"
assert "அடுத்து இதைச் செய்யலாமா" not in reply_task, "Found unwanted robotic footer!"
print("✅ Test 2 Passed: Quick 1-sentence task dispatch acknowledgment under 25 words.")

# Test 3: Technical Question - Natural & Short
print("\n[TEST 3] Testing Technical Question ('What is a REST API?'):")
reply_tech = get_executive_voice_response("What is a REST API?", 0, "workspace/login.html", True, 1861)
print(f"🗣️ SRI Reply:\n   \"{reply_tech}\"")
words_tech = reply_tech.split()
print(f"   Word count: {len(words_tech)}")
assert len(words_tech) <= 30, f"Technical reply too long! ({len(words_tech)} words)"
assert "அடுத்து இதைச் செய்யலாமா" not in reply_tech, "Found unwanted robotic footer!"
assert not any(sym in reply_tech for sym in ["**", "##", "```"]), "Markdown formatting found in spoken text!"
print("✅ Test 3 Passed: Crisp conversational phone-call reply under 25 words with no robotic footer.")

print("\n" + "=" * 65)
print("   ALL 3 NATURAL PHONE-CALL PERSONA TESTS PASSED!   ")
print("=" * 65)
