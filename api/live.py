"""WS /api/takes/{id}/live: the live conversation with Oli.

Client -> server (JSON text frames, plus binary audio frames):
  {"type": "start"}                               Oli greets and asks the first question
  {"type": "oli_spoken", "turn_id", "start", "end"}  when Oli's line played, in recording seconds
  <binary>                                        audio chunks (~250 ms) of the current answer
  {"type": "answer_done", "start", "end", "draft"}  answer finished; draft = browser's live transcript
  {"type": "hint"} / {"type": "skip"} / {"type": "end"}

Server -> client:
  {"type": "oli", "turn_id", "text", "final"}     Oli's next line (the browser speaks it)
  {"type": "transcript", "text"}                  Whisper's transcript of the last answer
  {"type": "hint", "text"}
  {"type": "error", "message"}

Each answer's audio goes to the Whisper API for an accurate transcript that
Oli can respond to. The full recording is still uploaded at the end for the
deep analysis, same as record mode.
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from feedback import storage
from preprocessing.transcribe import transcribe_openai

from . import oli
from .auth import token_from, user_from_token
from .ratelimit import RateLimited, limiter

# Messages that cost an OpenAI call count against the user's "oli" budget.
PAID = {"start", "answer_done", "skip", "hint", "end"}
MAX_ANSWER_BYTES = 25 * 1024 * 1024  # Whisper API's file limit

log = logging.getLogger("podium.live")


def question_budget(rehearsal: dict) -> int:
    minutes = rehearsal.get("time_limit") or 15
    return max(3, min(8, round(minutes / 3)))


async def live_session(ws: WebSocket, take_id: int) -> None:
    await ws.accept()
    try:
        user = user_from_token(token_from(ws))
    except HTTPException as exc:
        await ws.send_json({"type": "error", "message": exc.detail, "code": 401})
        await ws.close(code=4401)
        return
    take = storage.get_take(take_id)
    rehearsal = storage.get_rehearsal(take["rehearsal_id"]) if take else None
    if not take or rehearsal["user_id"] != user.id:
        await ws.close(code=4404)
        return
    files = storage.list_files(rehearsal["id"])
    n_questions = question_budget(rehearsal)
    audio = bytearray()

    async def say(instruction: str | None = None) -> None:
        turns = storage.list_turns(take_id)
        text, final = await asyncio.to_thread(oli.next_line, rehearsal, files, turns, n_questions, instruction)
        turn_id = storage.add_turn(take_id, "oli", text)
        await ws.send_json({"type": "oli", "turn_id": turn_id, "text": text, "final": final})

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes"):
                if len(audio) + len(msg["bytes"]) <= MAX_ANSWER_BYTES:
                    audio.extend(msg["bytes"])
                continue
            data = json.loads(msg.get("text") or "{}")
            kind = data.get("type")
            try:
                if kind in PAID:
                    limiter.hit("oli", f"user:{user.id}")
                if kind == "start":
                    await say()
                elif kind == "oli_spoken":
                    storage.update_turn_times(int(data["turn_id"]), data.get("start"), data.get("end"))
                elif kind == "answer_done":
                    text = await _transcribe_answer(bytes(audio), data.get("draft") or "")
                    audio.clear()
                    storage.add_turn(take_id, "user", text or "(no answer)", data.get("start"), data.get("end"))
                    await ws.send_json({"type": "transcript", "text": text})
                    await say()
                elif kind == "skip":
                    audio.clear()
                    storage.add_turn(take_id, "user", "(skipped this question)")
                    await say("The user skipped that question. Move on to a different one.")
                elif kind == "hint":
                    text = await asyncio.to_thread(oli.hint, rehearsal, files, storage.list_turns(take_id))
                    await ws.send_json({"type": "hint", "text": text})
                elif kind == "end":
                    await say("The user wants to finish now. Wrap up in one sentence.")
            except RateLimited as exc:
                if kind == "answer_done":
                    audio.clear()
                await ws.send_json({"type": "error", "message": str(exc), "code": 429})
            except oli.OliUnavailable as exc:
                await ws.send_json({"type": "error", "message": str(exc)})
            except Exception as exc:
                log.exception("live session %s", take_id)
                await ws.send_json({"type": "error", "message": f"Oli lost his train of thought: {exc}"})
    except WebSocketDisconnect:
        pass


async def _transcribe_answer(data: bytes, draft: str) -> str:
    """Whisper API transcript of one answer, falling back to the browser's draft."""
    if len(data) < 2000:
        return draft.strip()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "answer.webm"
        path.write_bytes(data)
        try:
            result = await asyncio.to_thread(transcribe_openai, str(path))
            return result["text"] or draft.strip()
        except Exception as exc:
            log.warning("Whisper API failed, using browser transcript: %s", exc)
            return draft.strip()
