"""The analysis job for one take: M3 -> M4 -> M5/M6 -> M7.

Runs outside the request (FastAPI BackgroundTasks); the frontend polls
GET /api/takes/{id} and shows Oli thinking while `step` changes.
"""

import json
import logging
import os
import threading
import time
import traceback
from functools import lru_cache
from pathlib import Path

from analyzers import analyze
from feedback import build_report, change_facts, storage, summarize
from inference import InferenceEngine
from knowledge_base import FactBase, KnowledgeBase
from preprocessing import PreprocessError, preprocess
from preprocessing.ffmpeg import run_ffmpeg

from . import video_store
from .video_store import take_dir

log = logging.getLogger("podium.pipeline")

# Whisper and MediaPipe are CPU heavy; extra takes wait their turn ("queued").
_jobs = threading.BoundedSemaphore(int(os.getenv("PODIUM_MAX_CONCURRENT_JOBS", "2")))


@lru_cache(maxsize=1)
def knowledge_base() -> KnowledgeBase:
    return KnowledgeBase.load()


def run_take(take_id: int) -> None:
    with _jobs:
        _run_take(take_id)


def _run_take(take_id: int) -> None:
    take = storage.get_take(take_id)
    rehearsal = storage.get_rehearsal(take["rehearsal_id"])
    work = take_dir(take_id)
    step = lambda name: storage.update_take(take_id, status="processing", step=name)

    try:
        pre = preprocess(take["video_path"], str(work), on_step=step)

        step("playback")
        playback = _make_playback(take["video_path"], work, pre["has_video"])

        step("analyzing")
        oli_turns = [t for t in storage.list_turns(take_id) if t["speaker"] == "oli" and t["start"] is not None]
        context = {
            "occasion": rehearsal["occasion"],
            "mode": take["mode"],
            "audience": rehearsal["audience"],
            "time_limit_s": (rehearsal["time_limit"] or 0) * 60 or None,
            "oli_turns": oli_turns,
        }
        analysis = analyze(pre, context)

        step("reasoning")
        summary = summarize(analysis["facts"])
        previous = storage.previous_done_takes(rehearsal["id"], take["number"])
        facts = list(analysis["facts"])
        if previous:
            facts += change_facts(summary, previous[-1]["summary"])
        fact_base = FactBase(facts)
        kb = knowledge_base()
        result = InferenceEngine(kb).run(fact_base, rehearsal["occasion"],
                                         recent_focus=[p["focus_rule_ids"] for p in previous])
        result_dict = result.to_dict()

        step("report")
        report = build_report(
            rehearsal=rehearsal, take=take,
            analysis={**analysis, "words": pre["transcript"]["words"]},
            result=result_dict, summary=summary, previous=previous, scoring=kb.scoring,
        )
        playback_key = None
        if playback:
            step("saving")
            playback_key = video_store.save_playback(take_id, f"user-{rehearsal['user_id']}", playback)
        report["playback"] = playback_key is not None
        all_facts = [f.to_dict() for f in fact_base.all()]
        storage.save_analysis(take_id, all_facts, result_dict)
        video_store.cleanup_after_analysis(take_id, keep=Path(playback) if playback else None)
        storage.update_take(
            take_id, status="done", step=None, score=report["score"], duration=pre["duration_s"],
            finished_at=time.time(), playback_key=playback_key, video_path=None,
            metrics_json=json.dumps({"summary": summary, "metrics": analysis["metrics"]}, default=_jsonable),
            report_json=json.dumps(report, default=_jsonable),
        )
    except PreprocessError as exc:
        storage.update_take(take_id, status="failed", step=None, error=str(exc))
    except Exception as exc:  # report any failure to the user instead of spinning forever
        log.error("take %s failed:\n%s", take_id, traceback.format_exc())
        storage.update_take(take_id, status="failed", step=None, error=f"Analysis failed: {exc}")


def _make_playback(video_path: str, work: Path, has_video: bool) -> str | None:
    """The one copy we keep: a 480p MP4 (a few MB a minute). Browser WebM often can't seek; MP4 can."""
    out = work / ("playback.mp4" if has_video else "playback.m4a")
    try:
        if has_video:
            run_ffmpeg(["-i", video_path, "-vf", "scale=-2:'min(480,ih)'", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "30", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(out)])
        else:
            run_ffmpeg(["-i", video_path, "-vn", "-c:a", "aac", str(out)])
        return str(out)
    except Exception:
        log.warning("could not make playback file for %s", video_path)
        return None


def _jsonable(o):
    if hasattr(o, "item"):  # numpy scalars
        return o.item()
    if hasattr(o, "tolist"):
        return o.tolist()
    raise TypeError(f"not JSON serializable: {type(o)}")
