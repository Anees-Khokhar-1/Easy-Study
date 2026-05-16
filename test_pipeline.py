import requests, json, sys

BASE = "http://localhost:8000"

# Test flashcards
print("=== FLASHCARD GENERATION ===")
r = requests.post(f"{BASE}/api/generate/flashcards", json={"topic": "machine learning", "count": 3}, timeout=300)
print(f"Status: {r.status_code}")
d = r.json()
if r.ok:
    cards = d.get("flashcards", [])
    print(f"Generated: {len(cards)} cards")
    for c in cards:
        print(f"  Card {c['id']+1}: Q: {c['front'][:80]}")
        print(f"           A: {c['back'][:80]}")
        print(f"           Difficulty: {c['difficulty']}")
else:
    print(f"Error: {d}")

print()

# Test quiz
print("=== QUIZ GENERATION ===")
r = requests.post(f"{BASE}/api/generate/quiz", json={"topic": "machine learning", "count": 2}, timeout=300)
print(f"Status: {r.status_code}")
d = r.json()
if r.ok:
    qs = d.get("questions", [])
    print(f"Generated: {len(qs)} questions")
    for q in qs:
        print(f"  Q{q['id']+1}: {q['question'][:80]}")
        for i, opt in enumerate(q['options']):
            marker = " ✅" if i == q['correct'] else ""
            print(f"    {chr(65+i)}) {opt[:60]}{marker}")
        print(f"    Explanation: {q['explanation'][:80]}")
else:
    print(f"Error: {d}")

print()

# Test summary
print("=== SUMMARY GENERATION ===")
r = requests.post(f"{BASE}/api/generate/summary", json={"topic": "machine learning", "length": "short"}, timeout=300)
print(f"Status: {r.status_code}")
d = r.json()
if r.ok:
    print(f"Summary: {d.get('summary', '')[:200]}")
    kps = d.get("key_points", [])
    print(f"Key points ({len(kps)}):")
    for kp in kps:
        print(f"  - {kp[:80]}")
else:
    print(f"Error: {d}")

print("\n=== ALL PIPELINE TESTS COMPLETE ===")
