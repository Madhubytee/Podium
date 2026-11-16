import io

import pytest
from fastapi.testclient import TestClient

from preprocessing.ffmpeg import run_ffmpeg

WORDS = "Um, so, hi everyone. Today I want to talk about, uh, our app. I think maybe it could, like, help. Thank you."


def fake_transcript(*_a, **_k):
    words, t = [], 0.5
    for token in WORDS.split():
        words.append({"text": token, "start": round(t, 2), "end": round(t + 0.3, 2), "conf": 0.95})
        t += 0.45 if not token.endswith(".") else 1.4
    return {"text": WORDS, "language": "en", "segments": [{"start": 0.5, "end": t, "text": WORDS}], "words": words}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PODIUM_STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr("preprocessing.pipeline.transcribe", fake_transcript)
    from api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def recording(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "take.webm"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=12",
                "-f", "lavfi", "-i", "sine=frequency=180:duration=12",
                "-shortest", "-c:v", "libvpx", "-c:a", "libopus", str(path)])
    return path.read_bytes()


def make_docx(text: str) -> bytes:
    import docx

    d = docx.Document()
    d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_full_record_flow(client, recording):
    r = client.post("/api/rehearsals", json={"occasion": "pitch", "mode": "record", "time_limit": 1,
                                              "details": "Seed pitch for our study app"}).json()
    assert r["title"] == "Seed pitch for our study app"

    files = client.post(f"/api/rehearsals/{r['id']}/files",
                        files=[("files", ("my_script.docx", make_docx("We help students find notes."), "application/octet-stream"))])
    assert files.status_code == 200 and files.json()[0]["kind"] == "script"

    take = client.post(f"/api/rehearsals/{r['id']}/takes", json={}).json()
    assert take["number"] == 1 and take["status"] == "recording"

    up = client.post(f"/api/takes/{take['id']}/upload", files={"file": ("take.webm", recording, "video/webm")})
    assert up.status_code == 200

    done = client.get(f"/api/takes/{take['id']}").json()  # TestClient runs the background job before returning
    assert done["status"] == "done", done["error"]
    report = done["report"]
    assert 0 <= report["score"] <= 100
    keys = [d["key"] for d in report["focus"] + report["secondary"]]
    assert "no_call_to_action" in keys and "filler_heavy" in keys
    assert any("filler" in w["tags"] for w in report["transcript"])

    filler = next(d for d in report["focus"] + report["secondary"] if d["key"] == "filler_heavy")
    facts = client.get(f"/api/takes/{take['id']}/facts", params={"ids": ",".join(map(str, filler["fact_ids"]))}).json()
    assert {f["name"] for f in facts} >= {"filler_per_min", "filler"}

    moment = filler["moments"][0]
    clip = client.get(f"/api/takes/{take['id']}/clip", params={"start": moment["start"], "end": moment["end"]})
    assert clip.status_code == 200 and clip.headers["content-type"] == "video/mp4"
    assert client.get(f"/api/takes/{take['id']}/video").status_code == 200

    again = client.post(f"/api/takes/{take['id']}/upload", files={"file": ("take.webm", recording, "video/webm")})
    assert again.status_code == 409

    take2 = client.post(f"/api/rehearsals/{r['id']}/takes", json={}).json()
    client.post(f"/api/takes/{take2['id']}/upload", files={"file": ("take.webm", recording, "video/webm")})
    second = client.get(f"/api/takes/{take2['id']}").json()["report"]
    assert second["progress"]["previous_take"] == 1

    prog = client.get(f"/api/rehearsals/{r['id']}/progress").json()
    assert [p["take"] for p in prog] == [1, 2]

    sidebar = client.get("/api/rehearsals").json()
    assert sidebar[0]["take_count"] == 2 and sidebar[0]["last_score"] == second["score"]

    assert client.delete(f"/api/rehearsals/{r['id']}").status_code == 200
    assert client.get(f"/api/rehearsals/{r['id']}").status_code == 404


def test_validation(client):
    assert client.post("/api/rehearsals", json={"occasion": "karaoke"}).status_code == 400
    r = client.post("/api/rehearsals", json={"occasion": "debate", "mode": "live"}).json()
    bad = client.post(f"/api/rehearsals/{r['id']}/files", files=[("files", ("a.exe", b"x", "application/octet-stream"))])
    assert bad.status_code == 400
    assert client.get("/api/takes/999").status_code == 404


def test_live_websocket(client, monkeypatch):
    lines = iter([("Hi! Tell me about yourself.", False), ("Nice. What was your biggest win?", False),
                  ("Thanks, that's the interview. Great chatting!", True)])
    monkeypatch.setattr("api.oli.next_line", lambda *a, **k: next(lines))
    monkeypatch.setattr("api.oli.hint", lambda *a, **k: "Mention a result with a number.")

    r = client.post("/api/rehearsals", json={"occasion": "interview", "mode": "live"}).json()
    take = client.post(f"/api/rehearsals/{r['id']}/takes", json={}).json()
    with client.websocket_connect(f"/api/takes/{take['id']}/live") as ws:
        ws.send_json({"type": "start"})
        first = ws.receive_json()
        assert first["type"] == "oli" and first["text"].startswith("Hi")
        ws.send_json({"type": "oli_spoken", "turn_id": first["turn_id"], "start": 0.0, "end": 2.5})
        ws.send_json({"type": "hint"})
        assert ws.receive_json() == {"type": "hint", "text": "Mention a result with a number."}
        ws.send_json({"type": "answer_done", "start": 3.0, "end": 20.0, "draft": "I study computer science."})
        assert ws.receive_json() == {"type": "transcript", "text": "I study computer science."}
        assert ws.receive_json()["text"].startswith("Nice")
        ws.send_json({"type": "end"})
        assert ws.receive_json()["final"] is True

    from feedback import storage
    turns = storage.list_turns(take["id"])
    assert [t["speaker"] for t in turns] == ["oli", "user", "oli", "oli"]
    assert (turns[0]["start"], turns[0]["end"]) == (0.0, 2.5)
