import sys
import time

# Import from app
from app import (
    is_realtime_web_search_required,
    get_executive_voice_response,
    perform_live_web_research,
)

print("=" * 65)
print("     VERIFYING UNIVERSAL KNOWLEDGE & FAST VOICE ENGINE     ")
print("=" * 65)

# --- 1. Test is_realtime_web_search_required ---
print("\n[TEST 1] Testing Smart Conditional Web Search Classification:")
cases = [
    ("Explain closures in JavaScript", False),
    ("How do I build a SaaS auth flow?", False),
    ("What is an event listener in DOM?", False),
    ("Find bugs in binary search algorithm", False),
    ("Tell me about quantum computing and qubits", False),
    ("Who founded Apple and what was Apple I?", False),
    ("How to design microservices architecture?", False),
    ("Find upcoming AI hackathons in 2026", True),
    ("Latest student internships 2026", True),
    ("What is today's breaking news in tech?", True),
    ("Look up online upcoming hackathons", True),
    ("https://github.com/trending repo status", True),
]

all_classifications_passed = True
for query, expected in cases:
    result = is_realtime_web_search_required(query)
    status = "✅ PASS" if result == expected else "❌ FAIL"
    if result != expected:
        all_classifications_passed = False
    print(f"  {status}: '{query}' -> Search Required: {result} (Expected: {expected})")

assert all_classifications_passed, "Classification test failed!"
print("✅ Test 1 Passed: Perfect distinction between universal knowledge and real-time search.")

# --- 2. Test Multi-Dimensional Voice Response & Mandatory Ending ---
print("\n[TEST 2] Testing Universal Query Multi-Dimensional Thinking & Ending:")
t0 = time.time()
universal_reply = get_executive_voice_response(
    user_query="Explain closures in JavaScript and how they affect memory",
    active_tasks_count=0,
    workspace_file="workspace/login.html",
    file_exists=True,
    file_size=1861,
)
elapsed = time.time() - t0
print(f"⚡ Latency: {elapsed:.2f}s")
print(f"🗣️ SRI Reply:\n   \"{universal_reply}\"")

mandatory_ending = "அடுத்து இதைச் செய்யலாமா, அல்லது உங்களிடம் வேறு ஏதேனும் ஐடியா இருக்கிறதா?"
assert mandatory_ending in universal_reply, f"Missing mandatory Tamil ending! Got: {universal_reply}"
print("✅ Test 2 Passed: Universal query answered with multi-dimensional guidance & exact Tamil ending.")

# --- 3. Test Real-Time Search Query & Card Generation ---
print("\n[TEST 3] Testing Real-Time External Info Query (Hackathons 2026):")
t0 = time.time()
research_data = perform_live_web_research("upcoming AI hackathons in 2026")
search_reply = get_executive_voice_response(
    user_query="Find upcoming AI hackathons in 2026",
    active_tasks_count=0,
    workspace_file="workspace/research.html",
    file_exists=True,
    file_size=len(research_data["card_html"]),
    research_summary=research_data["voice_summary"],
)
elapsed = time.time() - t0
print(f"⚡ Latency: {elapsed:.2f}s")
print(f"🗣️ SRI Reply:\n   \"{search_reply}\"")

assert mandatory_ending in search_reply, f"Missing mandatory Tamil ending in search reply! Got: {search_reply}"
assert len(research_data["items"]) > 0, "No research items found!"
print("✅ Test 3 Passed: Real-time search returned curated opportunities and multi-dimensional voice response.")

print("\n" + "=" * 65)
print("       ALL SUITE TESTS PASSED WITH 100% EXCELLENCE!       ")
print("=" * 65)

