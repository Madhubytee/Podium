"""Where take videos live.

The browser's raw upload is only kept on our server while it's analyzed. After
analysis we keep one compressed playback copy (480p MP4, a few MB a minute) for
the report's clips, and delete the raw file and extracted frames.

PODIUM_VIDEO_STORE picks where that playback copy goes:
  - "local"    (default): storage/takes/<id>/playback.mp4 on this server
  - "supabase": a private Supabase Storage bucket, at <user>/<take>.mp4.
                The server keeps a local cache for cutting clips.

Keys stored on the take: "local:<path>" or "supabase:<bucket>/<object path>".
Videos are deleted after PODIUM_VIDEO_RETENTION_DAYS (30) or when the user
deletes the rehearsal.
"""

import logging
import os
import shutil
from pathlib import Path

import httpx

from feedback import storage

log = logging.getLogger("podium.video")


def backend() -> str:
    return os.getenv("PODIUM_VIDEO_STORE", "local")


def take_dir(take_id: int) -> Path:
    path = storage.storage_dir() / "takes" / str(take_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _supabase():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("PODIUM_VIDEO_STORE=supabase needs SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "recordings")
    return url, {"Authorization": f"Bearer {key}", "apikey": key}, bucket


def save_playback(take_id: int, owner: str, local_path: str) -> str:
    """Store the playback copy and return its key."""
    if backend() != "supabase":
        return f"local:{local_path}"
    url, headers, bucket = _supabase()
    path = Path(local_path)
    object_path = f"{owner}/{take_id}{path.suffix}"
    with open(path, "rb") as f:
        resp = httpx.post(
            f"{url}/storage/v1/object/{bucket}/{object_path}",
            headers={**headers, "Content-Type": "video/mp4" if path.suffix == ".mp4" else "audio/mp4",
                     "x-upsert": "true"},
            content=f.read(), timeout=300,
        )
    resp.raise_for_status()
    return f"supabase:{bucket}/{object_path}"


def local_copy(take_id: int, key: str | None) -> Path | None:
    """A local file for this take's video, downloading it from Supabase if needed."""
    if not key:
        return None
    kind, _, ref = key.partition(":")
    if kind == "local":
        path = Path(ref)
        return path if path.exists() else None

    suffix = Path(ref).suffix
    cached = take_dir(take_id) / f"playback{suffix}"
    if cached.exists():
        return cached
    url, headers, _bucket = _supabase()
    with httpx.stream("GET", f"{url}/storage/v1/object/{ref}", headers=headers, timeout=300) as resp:
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        with open(cached, "wb") as out:
            for chunk in resp.iter_bytes():
                out.write(chunk)
    return cached


def delete(take_id: int, key: str | None) -> None:
    """Remove a take's video everywhere: the stored copy and the local folder."""
    if key and key.startswith("supabase:"):
        try:
            url, headers, _bucket = _supabase()
            bucket, _, object_path = key.removeprefix("supabase:").partition("/")
            httpx.request("DELETE", f"{url}/storage/v1/object/{bucket}",
                          headers=headers, json={"prefixes": [object_path]}, timeout=30).raise_for_status()
        except Exception as exc:
            log.warning("could not delete %s from Supabase: %s", key, exc)
    shutil.rmtree(storage.storage_dir() / "takes" / str(take_id), ignore_errors=True)


def cleanup_after_analysis(take_id: int, keep: Path | None) -> None:
    """Privacy: drop the raw upload and frames; keep only the playback copy (when stored locally)."""
    folder = take_dir(take_id)
    for item in folder.iterdir():
        if keep is not None and item == keep:
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
