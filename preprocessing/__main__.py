"""CLI: python -m preprocessing path/to/recording.mp4 [--out work_dir] [--fps 2]"""

import argparse
import json
from pathlib import Path

from .pipeline import preprocess


def main() -> None:
    parser = argparse.ArgumentParser(description="Podium M3 preprocessing")
    parser.add_argument("media", help="audio or video file")
    parser.add_argument("--out", help="work directory (default: <media>_preprocessed)")
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--language", default=None, help="force a language code, e.g. en")
    args = parser.parse_args()

    out = args.out or str(Path(args.media).with_suffix("")) + "_preprocessed"
    result = preprocess(args.media, out, fps=args.fps, language=args.language,
                        on_step=lambda s: print(f"-> {s}"))
    summary = {
        "duration_s": result["duration_s"],
        "words": len(result["transcript"]["words"]),
        "frames": len(result["frames"]),
        "transcript": result["transcript"]["text"][:300],
    }
    print(json.dumps(summary, indent=2))
    print(f"Full output: {Path(out) / 'preprocessed.json'}")


if __name__ == "__main__":
    main()
