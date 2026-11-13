# M3: Media preprocessing

Owner: Madhurishitha Boddu

Turns one recording (any audio or video file the browser or user gives us) into what the analyzers need:

1. **Audio extraction**: 16 kHz mono WAV with FFmpeg (`audio.py`)
2. **Transcription**: Whisper with a timestamp on every word (`transcribe.py`)
3. **Frame extraction**: 5 JPEG frames per second for body language (`frames.py`)

## Use it

```python
from preprocessing import preprocess

result = preprocess("raw.webm", "storage/takes/12", on_step=print)
```

or from the command line:

```bash
python -m preprocessing path/to/recording.mp4 --out work_dir
```

## Output contract (what M4 analyzers read)

```json
{
  "media_path": "raw.webm",
  "duration_s": 27.1,
  "has_video": true,
  "audio": {"path": ".../audio.wav", "sample_rate": 16000},
  "transcript": {
    "text": "Um, so, hi everyone...",
    "language": "en",
    "segments": [{"start": 0.0, "end": 3.2, "text": "Um, so, hi everyone."}],
    "words": [{"text": "Um,", "start": 0.0, "end": 0.32, "conf": 0.41}]
  },
  "frames": [{"t": 0.1, "path": ".../frames/frame_00001.jpg"}],
  "frame_fps": 5
}
```

The same dict is saved to `<work_dir>/preprocessed.json`. Recordings with no audio track raise `PreprocessError` with a message for the user.

## Whisper

| Setting (`.env`) | Default | Notes |
| --- | --- | --- |
| `PODIUM_WHISPER_BACKEND` | `local` | `local` = faster-whisper on the CPU (free). `openai` = OpenAI Whisper API (needs `OPENAI_API_KEY`). |
| `PODIUM_WHISPER_MODEL` | `small.en` | Local model. `base.en` is faster, `medium.en` more accurate. Downloads once (about 480 MB for small.en). |
| `PODIUM_WHISPER_API_MODEL` | `whisper-1` | API model. Live mode always uses the API to transcribe each answer. |

**Filler words:** Whisper normally cleans up "um" and "uh". We pass a disfluent initial prompt so it keeps them, which is what filler counting depends on. On a test recording it kept all 14 fillers.

**PyAV note:** faster-whisper's own audio decoder breaks with newer PyAV releases, so we hand it the decoded samples from our WAV instead of a file path.

## FFmpeg

Uses `ffmpeg` from your PATH, or falls back to the binary bundled with `imageio-ffmpeg`, so nobody has to install FFmpeg by hand.

## Tests

```bash
pip install -r preprocessing/requirements.txt
python -m pytest preprocessing
```

The tests generate their own media with FFmpeg and check the 16 kHz mono WAV, the frame timestamps, the silent-video error, and the full pipeline (with Whisper stubbed out).
