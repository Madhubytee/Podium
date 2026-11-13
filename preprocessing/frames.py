"""Video frame extraction for body-language analysis (eye contact, looking down)."""

from pathlib import Path

from .ffmpeg import run_ffmpeg

DEFAULT_FPS = 5  # guide: 5 frames per second is enough for body language
FRAME_WIDTH = 480


def extract_frames(media_path: str, out_dir: str, fps: float = DEFAULT_FPS) -> list[dict]:
    """Sample `fps` frames per second as JPEGs. Returns [{t, path}] in time order."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("frame_*.jpg"):
        old.unlink()

    run_ffmpeg([
        "-i", media_path,
        "-vf", f"fps={fps},scale={FRAME_WIDTH}:-2",
        "-q:v", "4",
        str(out / "frame_%05d.jpg"),
    ])

    # With the fps filter, frame N (1-based) covers time (N - 1) / fps; use the midpoint.
    frames = []
    for path in sorted(out.glob("frame_*.jpg")):
        index = int(path.stem.split("_")[1]) - 1
        frames.append({"t": round((index + 0.5) / fps, 3), "path": str(path)})
    return frames
