"""Try alternate models to avoid rate limits"""
import requests, time, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = "http://127.0.0.1:8001"

# Test: Gemini 2.5 Flash (different model, separate rate limit)
print("TEST 1: Gemini 2.5 Flash")
requests.post(f"{BASE}/api/models/switch", json={"provider": "gemini", "model": "gemini-2.5-flash"})
t0 = time.time()
r = requests.post(f"{BASE}/api/query", json={"question": "Define machine learning in one sentence."})
d = r.json()
t = time.time()-t0
print(f"  Time: {t:.2f}s | Source: {d.get('source')}")
ans = d.get('answer','')[:300]
print(f"  Answer: {ans}")

# Test: OpenRouter Nemotron 120B
print("\nTEST 2: OpenRouter Nemotron 120B")
requests.post(f"{BASE}/api/models/switch", json={"provider": "openrouter", "model": "nemotron-120b"})
t0 = time.time()
r = requests.post(f"{BASE}/api/query", json={"question": "What is Python? One sentence."})
d = r.json()
t = time.time()-t0
print(f"  Time: {t:.2f}s | Source: {d.get('source')}")
ans = d.get('answer','')[:300]
print(f"  Answer: {ans}")

# Test: OpenRouter MiniMax
print("\nTEST 3: OpenRouter MiniMax M2.5")
requests.post(f"{BASE}/api/models/switch", json={"provider": "openrouter", "model": "minimax-m2.5"})
t0 = time.time()
r = requests.post(f"{BASE}/api/query", json={"question": "What is JavaScript? One sentence."})
d = r.json()
t = time.time()-t0
print(f"  Time: {t:.2f}s | Source: {d.get('source')}")
ans = d.get('answer','')[:300]
print(f"  Answer: {ans}")
print("\nDONE")
