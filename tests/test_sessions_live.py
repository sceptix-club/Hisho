"""
Live LLM session tests — actually hit Ollama via ADK Runner.

These are the *real* backend correctness checks: do multi-turn
conversations preserve context when resuming an older session?

Run:  uv run pytest tests/test_sessions_live.py -v -s
Requires: Postgres + Ollama (qwen2.5:3b) reachable.
Results are saved to tests/live_session_results.txt for inspection.

Unlike tests/test_sessions.py (which mocks the Runner), this file
exercises runner.run_async -> LiteLlm -> Ollama -> ADK DB.
"""

import json
import time
import uuid
from pathlib import Path

import httpx
import pytest

# Skip entirely if Ollama not reachable — but in this repo it is.
def _ollama_reachable() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

pytestmark = pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable at :11434")

RESULT_PATH = Path(__file__).with_name("live_session_results.txt")

def _append_result(text: str):
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULT_PATH, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def _sse_parse(raw: str):
    """Parse raw SSE `data: {...}\\n\\n` stream into list of dicts."""
    events = []
    for chunk in raw.split("\n\n"):
        for line in chunk.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except Exception:
                    pass
    return events

def _call_chat(client, headers, query: str, session_id: str | None = None, timeout=120):
    params = {"query": query}
    if session_id:
        params["session_id"] = session_id
    r = client.post("/chat", params=params, headers=headers, timeout=timeout)
    return r

def _call_chat_stream(client, headers, query: str, session_id: str | None = None, timeout=120) -> tuple[str, str, list[dict]]:
    """Call POST /chat/stream and return (session_id, final_text, all_events)."""
    payload = {"query": query, "session_id": session_id}
    # Use streaming context manager so we don't OOM on long streams
    with client.stream("POST", "/chat/stream", json=payload, headers=headers, timeout=timeout) as resp:
        assert resp.status_code != 404, f"Session not found: {resp.text[:500]}"
        # collect raw SSE
        raw = ""
        for chunk in resp.iter_text():
            raw += chunk
        # also check status after streaming (httpx buffers headers early)
        # If the server returned an error as SSE, raw will contain {"type":"error"}
    events = _sse_parse(raw)
    # Extract session_id from done event and final text from message/delta
    sid = session_id
    final_text = ""
    deltas = []
    for ev in events:
        if ev.get("type") == "done" and ev.get("session_id"):
            sid = ev["session_id"]
        elif ev.get("type") == "message":
            final_text = ev.get("text", "")
        elif ev.get("type") == "delta":
            deltas.append(ev.get("text", ""))
    # If no final message, coalesce deltas (some models stream only deltas)
    if not final_text and deltas:
        final_text = "".join(deltas)
    return sid, final_text, events


# ---------------------------------------------------------------------------

def test_live_session_context_preserved_via_chat_and_stream(client, test_user, auth_headers, demo_queries):
    """
    End-to-end live test:
      Q1 -> new session
      Q2 -> same session (should recall Q1 context, e.g. fever -> formal, roll 123)
      Q3 -> same session summarize (should mention both earlier turns)
      GET /sessions/{id} -> verify messages shape for frontend resume
      New session -> isolation check
    All responses are written to live_session_results.txt
    """
    # Fresh results file for this run
    RESULT_PATH.write_text("", encoding="utf-8")
    header = f"=== Live session test {time.strftime('%Y-%m-%d %H:%M:%S')} user={test_user.id} ===\n"
    _append_result(header)
    print(header)

    q1 = demo_queries["q1"]
    q2 = demo_queries["q2"]
    q3 = demo_queries["q3"]

    # --- TURN 1: new session via /chat (non-streaming) ---
    print(f"\n[Q1] {q1}")
    _append_result(f"[Q1] {q1}")
    t0 = time.time()
    r1 = _call_chat(client, auth_headers, q1, session_id=None)
    dt1 = time.time() - t0
    assert r1.status_code == 200, f"/chat Q1 failed {r1.status_code}: {r1.text[:800]}"
    body1 = r1.json()
    sid = body1["session_id"]
    resp1 = body1["response"]
    assert sid, "No session_id returned"
    assert resp1 and len(resp1.strip()) > 10, f"Empty response for Q1: {body1}"
    msg1 = f"[R1] session={sid} ({dt1:.1f}s)\n{resp1}\n"
    print(msg1)
    _append_result(msg1)

    # Verify GET /sessions/{id} after turn 1 (what frontend calls on resume)
    r = client.get(f"/sessions/{sid}", headers=auth_headers)
    assert r.status_code == 200, f"GET /sessions/{sid} failed: {r.text[:500]}"
    sess1 = r.json()
    assert sess1["id"] == sid
    assert len(sess1["messages"]) == 2, f"Expected 2 msgs after Q1, got {sess1['messages']}"
    assert sess1["messages"][0]["role"] == "user" and "fever" in sess1["messages"][0]["text"].lower() or "leave" in sess1["messages"][0]["text"].lower()
    assert sess1["messages"][1]["role"] == "assistant" and len(sess1["messages"][1]["text"]) > 10
    _append_result(f"[GET /sessions/{sid} after Q1] messages={json.dumps(sess1['messages'], indent=2, ensure_ascii=False)}\n")

    # List should contain our session with correct title
    r = client.get("/sessions", headers=auth_headers)
    assert r.status_code == 200
    listed = [s for s in r.json() if s["id"] == sid]
    assert listed, "New session not in list"
    assert listed[0]["title"] != "New chat"  # should be truncated Q1
    _append_result(f"[GET /sessions] title for {sid}: {listed[0]['title']}\n")

    # --- TURN 2: same session, follow-up referencing "it" (tests context) ---
    print(f"\n[Q2] {q2}")
    _append_result(f"[Q2] {q2}")
    t0 = time.time()
    r2 = _call_chat(client, auth_headers, q2, session_id=sid)
    dt2 = time.time() - t0
    assert r2.status_code == 200, f"/chat Q2 failed {r2.status_code}: {r2.text[:800]}"
    body2 = r2.json()
    sid2 = body2["session_id"]
    resp2 = body2["response"]
    assert sid2 == sid, f"Session changed on resume: {sid2} != {sid}"
    assert resp2 and len(resp2.strip()) > 10
    msg2 = f"[R2] ({dt2:.1f}s)\n{resp2}\n"
    print(msg2)
    _append_result(msg2)

    # Strong check: Q2 explicitly asked for roll number 123 — second turn should contain it
    # (lenient: if model ignored, log warning but don't fail hard, just record)
    if "123" not in resp2:
        warn = "WARNING: R2 does not contain '123' (model may not have followed instruction)"
        print(warn)
        _append_result(warn + "\n")
    else:
        _append_result("CHECK: R2 contains '123' as requested ✓\n")

    # Verify history now 4 messages (user/assistant x2)
    r = client.get(f"/sessions/{sid}", headers=auth_headers)
    assert r.status_code == 200
    sess2 = r.json()
    assert len(sess2["messages"]) == 4, f"Expected 4 msgs after Q2, got {len(sess2['messages'])}: {sess2['messages']}"
    _append_result(f"[GET /sessions/{sid} after Q2] messages={json.dumps(sess2['messages'], indent=2, ensure_ascii=False)}\n")

    # --- TURN 3: same session via STREAMING endpoint (frontend's actual path) ---
    print(f"\n[Q3 streaming] {q3}")
    _append_result(f"[Q3 streaming] {q3}")
    t0 = time.time()
    sid3, resp3, events = _call_chat_stream(client, auth_headers, q3, session_id=sid)
    dt3 = time.time() - t0
    assert sid3 == sid, f"Streaming changed session: {sid3} != {sid}"
    assert resp3 and len(resp3.strip()) > 10, f"Empty streaming response, events={events[:5]}"
    # Also check no error event
    assert not any(e.get("type") == "error" for e in events), f"Stream had error: {events}"
    msg3 = f"[R3 streaming] ({dt3:.1f}s) events={len(events)}\n{resp3}\n"
    print(msg3)
    _append_result(msg3)
    _append_result(f"[SSE raw truncated]\n{json.dumps(events, indent=2, ensure_ascii=False)[:3000]}\n")

    # Summarization should mention earlier context (fever/leave/formal). Lenient check.
    low3 = resp3.lower()
    hits = [kw for kw in ["fever", "leave", "formal", "roll", "123", "casual"] if kw in low3]
    if hits:
        _append_result(f"CHECK: R3 mentions {hits} ✓ (context preserved)\n")
    else:
        _append_result("WARNING: R3 does not mention any of fever/leave/formal/123 — context may be lost\n")

    # Final history should be 6 messages
    r = client.get(f"/sessions/{sid}", headers=auth_headers)
    assert r.status_code == 200
    sess3 = r.json()
    assert len(sess3["messages"]) == 6, f"Expected 6 msgs after Q3, got {sess3['messages']}"
    _append_result(f"[GET /sessions/{sid} after Q3] final messages count=6 ✓\n{json.dumps(sess3['messages'], indent=2, ensure_ascii=False)}\n")

    # --- ISOLATION: new session should not see old history ---
    q_iso = "What is my favourite colour? My colour is blue, remember blue."
    print(f"\n[Isolation Q] {q_iso}")
    _append_result(f"[Isolation Q new session] {q_iso}")
    r_iso = _call_chat(client, auth_headers, q_iso, session_id=None)
    assert r_iso.status_code == 200
    sid_iso = r_iso.json()["session_id"]
    assert sid_iso != sid, "Isolation session should be different id"
    _append_result(f"[Isolation R] sid={sid_iso}\n{r_iso.json()['response'][:800]}\n")

    # Old session should still have 6, new session 2
    assert len(client.get(f"/sessions/{sid}", headers=auth_headers).json()["messages"]) == 6
    assert len(client.get(f"/sessions/{sid_iso}", headers=auth_headers).json()["messages"]) == 2
    _append_result(f"CHECK: isolation — old={sid} still 6 msgs, new={sid_iso} has 2 msgs ✓\n")

    # Cleanup both sessions
    for cleanup_sid in [sid, sid_iso]:
        client.delete(f"/sessions/{cleanup_sid}", headers=auth_headers)
    _append_result(f"\n=== Done — cleaned up {sid} and {sid_iso} ===\n")
    print(f"\n=== Done — results saved to {RESULT_PATH} ===")


def test_live_memory_pin_recall(client, test_user, auth_headers):
    """
    Minimal memory test with unambiguous assertion:
      Turn1: 'Remember my PIN is 8421 and my pet is hamster'
      Turn2 (same session): 'What is my PIN and pet?'
      Expect: 8421 and hamster in response.

    This isolates ADK session memory from domain prompt complexity.
    """
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print("\n=== PIN recall memory test ===")
    _append_result("\n=== PIN recall memory test ===")

    q1 = "Remember this: my PIN is 8421 and my pet is hamster. Just acknowledge."
    q2 = "What is my PIN and what is my pet? Answer exactly."

    # Use streaming for turn1 to also exercise that path
    sid, resp1, ev1 = _call_chat_stream(client, auth_headers, q1, session_id=None)
    _append_result(f"[PIN Q1] {q1}\n[PIN R1] sid={sid}\n{resp1}\n")
    print(f"[PIN Q1 sid={sid}] {resp1[:400]}")
    assert sid and resp1

    sid2, resp2, ev2 = _call_chat_stream(client, auth_headers, q2, session_id=sid)
    _append_result(f"[PIN Q2] {q2}\n[PIN R2] sid={sid2}\n{resp2}\n")
    print(f"[PIN R2] {resp2[:800]}")
    assert sid2 == sid

    # Strict assertions for context preservation
    assert "8421" in resp2, f"PIN 8421 not recalled in R2: {resp2[:1000]}"
    assert "hamster" in resp2.lower(), f"hamster not recalled in R2: {resp2[:1000]}"
    _append_result("CHECK: 8421 and hamster recalled ✓ context preserved\n")

    # Also verify GET shows 4 messages
    r = client.get(f"/sessions/{sid}", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["messages"]) == 4

    client.delete(f"/sessions/{sid}", headers=auth_headers)
    _append_result(f"Cleaned up {sid}\n")
