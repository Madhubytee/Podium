"""Podium API. Run from the repo root:  uvicorn api.main:app --reload"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from feedback import storage
from preprocessing.ffmpeg import run_ffmpeg

from . import video_store
from .auth import User, auth_enabled, current_user
from .documents import UnsupportedFile, extract_text, guess_kind
from .live import live_session
from .pipeline import run_take
from .ratelimit import MAX_PROCESSING_PER_USER, RateLimited, client_ip, limit, limiter
from .video_store import take_dir

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("podium.api")

OCCASIONS = {"interview", "pitch", "presentation", "speech", "debate"}
MODES = {"live", "record", "upload"}
OCCASION_TITLES = {"interview": "Job interview", "pitch": "Pitch", "presentation": "Presentation",
                   "speech": "Speech or toast", "debate": "Debate"}
MAX_UPLOAD_MB = 500
MAX_FILE_MB = 20


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage.init_db()
    if not auth_enabled():
        log.warning("SUPABASE_URL is not set: login is OFF and everyone shares the demo account.")
    days = int(os.getenv("PODIUM_VIDEO_RETENTION_DAYS", "30"))
    for take in storage.expire_videos(days):
        video_store.delete(take["id"], take["playback_key"])
    yield


app = FastAPI(title="Podium", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("PODIUM_CORS_ORIGIN", "http://localhost:5173").split(",")],
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def per_ip_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        try:
            limiter.hit("ip", f"ip:{client_ip(request)}")
        except RateLimited as exc:
            return JSONResponse({"detail": str(exc)}, status_code=429,
                                headers={"Retry-After": str(exc.retry_after)})
    return await call_next(request)


# --- ownership helpers --------------------------------------------------------

def owned_rehearsal(rid: int, user: User) -> dict:
    r = storage.get_rehearsal(rid)
    if not r or r["user_id"] != user.id:  # someone else's looks the same as missing
        raise HTTPException(404, "Rehearsal not found")
    return r


def owned_take(tid: int, user: User) -> dict:
    take = storage.get_take(tid)
    if not take:
        raise HTTPException(404, "Take not found")
    owned_rehearsal(take["rehearsal_id"], user)
    return take


@app.get("/api/health")
def health():
    return {"ok": True, "oli": bool(os.getenv("OPENAI_API_KEY")), "auth": auth_enabled()}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "auth": auth_enabled()}


# --- rehearsals ---------------------------------------------------------------

class RehearsalIn(BaseModel):
    occasion: str
    mode: str = "record"
    title: str | None = Field(None, max_length=120)
    details: str | None = Field(None, max_length=5000)
    audience: str | None = Field(None, max_length=80)
    time_limit: int | None = Field(None, ge=1, le=180, description="minutes")


@app.post("/api/rehearsals")
def create_rehearsal(body: RehearsalIn, user: User = Depends(limit("rehearsal"))):
    if body.occasion not in OCCASIONS:
        raise HTTPException(400, f"occasion must be one of {sorted(OCCASIONS)}")
    if body.mode not in MODES:
        raise HTTPException(400, f"mode must be one of {sorted(MODES)}")
    title = body.title or _title_from(body.details) or OCCASION_TITLES[body.occasion]
    return storage.create_rehearsal(title, body.occasion, body.mode, body.time_limit, body.audience,
                                    body.details, user_id=user.id)


def _title_from(details: str | None) -> str | None:
    if not details or not details.strip():
        return None
    first = details.strip().split("\n")[0]
    return first if len(first) <= 60 else first[:57].rsplit(" ", 1)[0] + "..."


@app.get("/api/rehearsals")
def list_rehearsals(user: User = Depends(current_user)):
    return storage.list_rehearsals(user.id)


@app.get("/api/rehearsals/{rid}")
def get_rehearsal(rid: int, user: User = Depends(current_user)):
    r = owned_rehearsal(rid, user)
    r["files"] = [{"id": f["id"], "filename": f["filename"], "kind": f["kind"], "chars": len(f["extracted_text"] or "")}
                  for f in storage.list_files(rid)]
    r["takes"] = [{k: v for k, v in t.items() if k != "metrics"} for t in storage.list_takes(rid)]
    return r


@app.delete("/api/rehearsals/{rid}")
def delete_rehearsal(rid: int, user: User = Depends(current_user)):
    """Privacy: delete a rehearsal, its videos, and everything computed from them."""
    owned_rehearsal(rid, user)
    for take in storage.delete_rehearsal(rid):
        video_store.delete(take["id"], take["playback_key"])
    return {"deleted": rid}


@app.post("/api/rehearsals/{rid}/files")
async def upload_files(rid: int, files: list[UploadFile] = File(...), user: User = Depends(limit("files"))):
    owned_rehearsal(rid, user)
    out = []
    for f in files:
        data = await f.read(MAX_FILE_MB * 1024 * 1024 + 1)
        if len(data) > MAX_FILE_MB * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} is over {MAX_FILE_MB} MB.")
        try:
            text = extract_text(f.filename, data)
        except UnsupportedFile as exc:
            raise HTTPException(400, str(exc))
        except Exception as exc:
            raise HTTPException(400, f"Couldn't read {f.filename}: {exc}")
        out.append(storage.add_file(rid, f.filename, guess_kind(f.filename, text), text))
    return out


@app.get("/api/rehearsals/{rid}/progress")
def progress(rid: int, user: User = Depends(current_user)):
    owned_rehearsal(rid, user)
    return [{"take": t["number"], "take_id": t["id"], "score": t["score"],
             **((t["metrics"] or {}).get("summary") or {})}
            for t in storage.list_takes(rid) if t["status"] == "done"]


# --- takes --------------------------------------------------------------------

class TakeIn(BaseModel):
    mode: str | None = None


@app.post("/api/rehearsals/{rid}/takes")
def create_take(rid: int, body: TakeIn | None = None, user: User = Depends(limit("take"))):
    r = owned_rehearsal(rid, user)
    mode = (body.mode if body and body.mode else None) or r["mode"]
    if mode not in MODES:
        raise HTTPException(400, f"mode must be one of {sorted(MODES)}")
    return storage.create_take(rid, mode)


@app.post("/api/takes/{tid}/upload")
async def upload_take(tid: int, background: BackgroundTasks, file: UploadFile = File(...),
                      user: User = Depends(limit("upload"))):
    take = owned_take(tid, user)
    if take["status"] in ("processing", "done"):
        raise HTTPException(409, "This take was already uploaded. Start a new take to try again.")
    if storage.processing_count(user.id) >= MAX_PROCESSING_PER_USER:
        raise HTTPException(429, "Oli is still working on your other takes. Try again when one finishes.")
    ext = Path(file.filename or "").suffix.lower()
    ext = ext if ext in {".webm", ".mp4", ".mov", ".m4a", ".mp3", ".wav", ".ogg", ".mkv"} else ".webm"
    path = take_dir(tid) / f"raw{ext}"
    size = 0
    with open(path, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB << 20:
                out.close()
                path.unlink(missing_ok=True)
                raise HTTPException(413, f"Recordings can be up to {MAX_UPLOAD_MB} MB.")
            out.write(chunk)
    storage.update_take(tid, video_path=str(path), status="processing", step="queued", error=None)
    background.add_task(run_take, tid)
    return {"id": tid, "status": "processing"}


@app.get("/api/takes/{tid}")
def get_take(tid: int, user: User = Depends(current_user)):
    take = owned_take(tid, user)
    for private in ("metrics", "video_path", "playback_key"):
        take.pop(private, None)
    return take


@app.get("/api/takes/{tid}/facts")
def take_facts(tid: int, ids: str = Query("", description="comma separated fact ids"),
               user: User = Depends(current_user)):
    """'Why this feedback?': the facts behind a diagnosis."""
    owned_take(tid, user)
    wanted = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    return storage.get_facts(tid, wanted or None)


def _playback_file(take: dict) -> Path:
    path = video_store.local_copy(take["id"], take.get("playback_key"))
    if not path:
        raise HTTPException(404, "No video for this take (videos are deleted after 30 days).")
    return path


@app.get("/api/takes/{tid}/video")
def take_video(tid: int, user: User = Depends(limit("media"))):
    path = _playback_file(owned_take(tid, user))
    return FileResponse(path, media_type="video/mp4" if path.suffix == ".mp4" else "audio/mp4")


@app.get("/api/takes/{tid}/clip")
def take_clip(tid: int, start: float = Query(..., ge=0), end: float = Query(..., gt=0),
              user: User = Depends(limit("media"))):
    if end <= start or end - start > 120:
        raise HTTPException(400, "A clip must be between 0 and 120 seconds long.")
    source = _playback_file(owned_take(tid, user))
    clips = take_dir(tid) / "clips"
    clips.mkdir(exist_ok=True)
    out = clips / f"{start:.2f}-{end:.2f}{source.suffix}"
    if not out.exists():
        # Re-encode (clips are short) so the cut lands exactly on the moment, not the nearest keyframe.
        video = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"] if source.suffix == ".mp4" else ["-vn"]
        run_ffmpeg(["-ss", f"{start:.2f}", "-i", str(source), "-t", f"{end - start:.2f}",
                    *video, "-c:a", "aac", "-movflags", "+faststart", str(out)])
    return FileResponse(out, media_type="video/mp4" if out.suffix == ".mp4" else "audio/mp4")


@app.websocket("/api/takes/{tid}/live")
async def live(ws: WebSocket, tid: int):
    await live_session(ws, tid)


# Serve the built frontend (npm run build) from the same server, if it exists.
# Asset files are served as-is; any other path gets index.html so React Router
# can handle deep links like /practice/takes/12.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        file = (_dist / path).resolve()
        if path and file.is_file() and _dist.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(_dist / "index.html")
