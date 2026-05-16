"""Full A-to-Z integration test for Easy-Study v2.0"""
import requests
import json
import sys
import time

BASE = "http://127.0.0.1:8000"

def test(name, fn):
    try:
        result = fn()
        print(f"  [PASS] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return None

print("=" * 60)
print("  EASY-STUDY v2.0 — FULL INTEGRATION TEST")
print("=" * 60)

# ── 1. Health Check ──
print("\n--- 1. HEALTH CHECK ---")
def t1():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"
    assert d["version"] == "2.0.0"
    assert "database" in d["components"]
    assert "rate_limiting" in d["components"]
    assert "cache" in d
    assert "database" in d
    print(f"    Version: {d['version']}")
    print(f"    DB: {d['components']['database']}")
    print(f"    Rate Limit: {d['components']['rate_limiting']}")
    return d
test("Health endpoint", t1)

# ── 2. Models API ──
print("\n--- 2. MODELS API ---")
def t2():
    r = requests.get(f"{BASE}/api/models", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "ollama" in d
    assert "groq" in d
    print(f"    Providers: {list(d.keys())}")
    return d
test("List models", t2)

def t2b():
    r = requests.get(f"{BASE}/api/models/active", timeout=10)
    assert r.status_code == 200
    d = r.json()
    print(f"    Active: {d['provider']}/{d['model']}")
    return d
test("Active model", t2b)

# ── 3. Ingest Text Content ──
print("\n--- 3. INGEST CONTENT ---")
study_text = """
Machine Learning (ML) is a subset of artificial intelligence (AI) that enables systems to learn from data.

Types of Machine Learning:
1. Supervised Learning: Learns from labeled data. Examples: linear regression, decision trees, SVM.
2. Unsupervised Learning: Finds patterns in unlabeled data. Examples: K-means, PCA.
3. Reinforcement Learning: Agent learns via rewards. Examples: Q-learning, DQN.

Key Concepts:
- Training Data: Dataset used to train the model
- Features: Input variables for predictions
- Overfitting: Model works on training data but fails on new data
- Gradient Descent: Optimization algorithm to minimize loss
- Neural Networks: Layers of interconnected nodes inspired by biology

Deep Learning architectures:
- CNNs: Image recognition and computer vision
- RNNs: Sequential data like text and time series
- Transformers: NLP models like BERT and GPT
- GANs: Generate realistic synthetic data

Evaluation Metrics:
- Accuracy: Percentage of correct predictions
- Precision: True positives / predicted positives
- Recall: True positives / actual positives
- F1 Score: Harmonic mean of precision and recall
"""

def t3():
    r = requests.post(f"{BASE}/api/ingest/text",
        json={"text": study_text, "title": "Machine Learning Fundamentals"},
        timeout=60)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    print(f"    Chunks: {d.get('chunks_created', '?')}")
    print(f"    Sources: {d.get('sources', [])}")
    return d
test("Ingest text notes", t3)

# ── 4. Sources Tracking ──
print("\n--- 4. SOURCES DATABASE ---")
def t4():
    r = requests.get(f"{BASE}/api/sources", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert len(d["sources"]) > 0
    s = d["sources"][0]
    print(f"    Total sources: {d['stats']['total_sources']}")
    print(f"    Latest: {s['source_name']} ({s['source_type']}, {s['chunks']} chunks)")
    return d
test("Sources tracked in DB", t4)

# ── 5. Query (RAG) ──
print("\n--- 5. RAG QUERY ---")
def t5():
    r = requests.post(f"{BASE}/api/query",
        json={"question": "What are the types of machine learning?", "top_k": 3},
        timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert "answer" in d
    assert len(d["answer"]) > 20
    print(f"    Source: {d.get('source', '?')}")
    print(f"    Provider: {d.get('provider', '?')}")
    print(f"    Model: {d.get('model', '?')}")
    print(f"    Confidence: {d.get('confidence', '?')}")
    print(f"    Cached: {d.get('cached', False)}")
    print(f"    Answer: {d['answer'][:120]}...")
    return d
test("RAG query", t5)

# ── 6. Cache Test ──
print("\n--- 6. CACHE TEST ---")
def t6():
    r = requests.post(f"{BASE}/api/query",
        json={"question": "What are the types of machine learning?", "top_k": 3},
        timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("cached") == True
    print(f"    Cached: {d['cached']} (instant response)")
    return d
test("Cache hit on repeat query", t6)

# ── 7. Chat History ──
print("\n--- 7. CHAT HISTORY ---")
def t7():
    r = requests.get(f"{BASE}/api/history", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["stats"]["total_messages"] >= 1
    msg = d["messages"][0]
    print(f"    Total messages: {d['stats']['total_messages']}")
    print(f"    Latest Q: {msg['question'][:60]}")
    print(f"    Provider: {msg['provider']}, Model: {msg['model']}")
    return d
test("Chat history persisted", t7)

# ── 8. Flashcards ──
print("\n--- 8. FLASHCARD GENERATION ---")
def t8():
    r = requests.post(f"{BASE}/api/generate/flashcards",
        json={"topic": "machine learning", "count": 3},
        timeout=300)
    assert r.status_code == 200
    d = r.json()
    cards = d.get("flashcards", [])
    assert len(cards) >= 1
    print(f"    Generated: {len(cards)} flashcards")
    for c in cards:
        print(f"      Q: {c['front'][:60]}")
        print(f"      A: {c['back'][:60]}")
    return d
test("Flashcard generation", t8)

# ── 9. Quiz (MCQs) ──
print("\n--- 9. QUIZ GENERATION ---")
def t9():
    r = requests.post(f"{BASE}/api/generate/quiz",
        json={"topic": "machine learning", "count": 2},
        timeout=300)
    assert r.status_code == 200
    d = r.json()
    questions = d.get("questions", [])
    assert len(questions) >= 1
    print(f"    Generated: {len(questions)} questions")
    for q in questions:
        print(f"      Q: {q['question'][:60]}")
        for i, opt in enumerate(q.get("options", [])):
            mark = " <--" if i == q.get("correct") else ""
            print(f"        {chr(65+i)}) {opt[:50]}{mark}")
    return d
test("Quiz/MCQ generation", t9)

# ── 10. Summary ──
print("\n--- 10. SUMMARY GENERATION ---")
def t10():
    r = requests.post(f"{BASE}/api/generate/summary",
        json={"topic": "machine learning", "length": "short"},
        timeout=300)
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d
    assert len(d["summary"]) > 20
    print(f"    Summary: {d['summary'][:150]}...")
    kps = d.get("key_points", [])
    print(f"    Key points: {len(kps)}")
    return d
test("Summary generation", t10)

# ── 11. Health (post-test) ──
print("\n--- 11. FINAL HEALTH CHECK ---")
def t11():
    r = requests.get(f"{BASE}/api/health", timeout=10)
    d = r.json()
    cache = d["cache"]
    db = d["database"]
    print(f"    Cache: {cache['hits']} hits, {cache['misses']} misses, rate={cache['hit_rate']}")
    print(f"    DB Chat: {db['chat']['total_messages']} messages")
    print(f"    DB Sources: {db['sources']['total_sources']} sources, {db['sources']['total_chunks']} chunks")
    return d
test("Final health check", t11)

print("\n" + "=" * 60)
print("  ALL TESTS COMPLETE")
print("=" * 60)
