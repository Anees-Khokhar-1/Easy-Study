"""Quick test: switch to Gemini, ask a question, measure response time."""
import requests, json, time

BASE = "http://127.0.0.1:8001"

# 1) Switch to Gemini
print("=" * 60)
print("TEST 1: Switch to Gemini 2.0 Flash")
r = requests.post(f"{BASE}/api/models/switch", json={"provider": "gemini", "model": "gemini-2.0-flash"})
print(f"  Result: {r.json()}")
print()

# 2) Chat query
print("TEST 2: Chat query (Gemini)")
t0 = time.time()
r = requests.post(f"{BASE}/api/query", json={"question": "What is machine learning? Explain briefly."})
t1 = time.time()
d = r.json()
print(f"  Response time: {t1-t0:.1f}s")
print(f"  Provider: {d.get('provider')}/{d.get('model')}")
print(f"  Fallback: {d.get('triggered_fallback')}")
print(f"  Answer: {d.get('answer','')[:400]}")
print()

# 3) Switch to OpenRouter and test
print("TEST 3: Switch to OpenRouter (Llama 3.3 70B)")
r = requests.post(f"{BASE}/api/models/switch", json={"provider": "openrouter", "model": "llama-3.3-70b-free"})
print(f"  Result: {r.json()}")

t0 = time.time()
r = requests.post(f"{BASE}/api/query", json={"question": "What is artificial intelligence?"})
t1 = time.time()
d = r.json()
print(f"  Response time: {t1-t0:.1f}s")
print(f"  Provider: {d.get('provider')}/{d.get('model')}")
print(f"  Answer: {d.get('answer','')[:400]}")
print()

# 4) Test flashcards
print("TEST 4: Generate Flashcards (Gemini)")
requests.post(f"{BASE}/api/models/switch", json={"provider": "gemini", "model": "gemini-2.0-flash"})
t0 = time.time()
r = requests.post(f"{BASE}/api/generate/flashcards", json={"topic": "Python basics", "count": 3})
t1 = time.time()
d = r.json()
print(f"  Response time: {t1-t0:.1f}s")
print(f"  Status: {d.get('status', 'error')}")
cards = d.get("flashcards", [])
for c in cards[:3]:
    print(f"    Q: {c.get('front','')[:80]}")
    print(f"    A: {c.get('back','')[:80]}")
print()

# 5) Test quiz
print("TEST 5: Generate Quiz (Gemini)")
t0 = time.time()
r = requests.post(f"{BASE}/api/generate/quiz", json={"topic": "Data structures", "count": 2})
t1 = time.time()
d = r.json()
print(f"  Response time: {t1-t0:.1f}s")
print(f"  Status: {d.get('status', 'error')}")
qs = d.get("questions", [])
for q in qs[:2]:
    print(f"    Q: {q.get('question','')[:80]}")
    print(f"    Options: {q.get('options', [])}")
    print(f"    Answer: {q.get('correct_answer','')}")
print()

# 6) Test summary
print("TEST 6: Generate Summary (Gemini)")
t0 = time.time()
r = requests.post(f"{BASE}/api/generate/summary", json={"topic": "Machine learning", "length": "short"})
t1 = time.time()
d = r.json()
print(f"  Response time: {t1-t0:.1f}s")
print(f"  Status: {d.get('status', 'error')}")
print(f"  Summary: {d.get('summary','')[:300]}")
print()

print("=" * 60)
print("ALL TESTS COMPLETE!")
