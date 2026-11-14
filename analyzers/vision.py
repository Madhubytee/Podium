"""Camera analysis with MediaPipe: eye contact, expressiveness, gestures, swaying.

Runs the Face, Pose, and Hand Landmarkers over the frames M3 extracted (5 per
second). The camera is optional; with no frames or no face, this returns
{"available": False} and the body language rules simply don't fire.
"""

import math
import os
import urllib.request
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

MODEL_URLS = {
    "face": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
    "hand": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
}

YAW_OK_DEG = 15
PITCH_OK_DEG = 12
SMILE = 0.4
ANIMATED_DELTA = 0.02     # mean blendshape change between frames
WRIST_MOVE = 0.02         # normalized image units between frames
SWAY_AMPLITUDE = 0.03     # normalized image width


def _model_path(kind: str) -> str:
    folder = Path(os.getenv("PODIUM_STORAGE_DIR", "storage")) / "models"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / Path(MODEL_URLS[kind]).name
    if not path.exists():
        urllib.request.urlretrieve(MODEL_URLS[kind], path)
    return str(path)


def _options(kind: str):
    base = mp.tasks.BaseOptions(model_asset_path=_model_path(kind))
    video = vision.RunningMode.VIDEO
    if kind == "face":
        return vision.FaceLandmarker, vision.FaceLandmarkerOptions(
            base_options=base, running_mode=video,
            output_face_blendshapes=True, output_facial_transformation_matrixes=True)
    if kind == "pose":
        return vision.PoseLandmarker, vision.PoseLandmarkerOptions(base_options=base, running_mode=video)
    return vision.HandLandmarker, vision.HandLandmarkerOptions(base_options=base, running_mode=video, num_hands=2)


def head_angles(matrix) -> tuple[float, float]:
    """(yaw, pitch) in degrees from the face transformation matrix. Pitch > 0 = looking up."""
    r = np.asarray(matrix)[:3, :3]
    fwd = r[:, 2]  # where the face points, in camera space
    yaw = math.degrees(math.atan2(fwd[0], fwd[2]))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, fwd[1]))))
    return yaw, pitch


def analyze_vision(frames: list[dict], exclude: list[tuple[float, float]] = ()) -> dict:
    frames = [f for f in frames if not any(s <= f["t"] < e for s, e in exclude)]
    if not frames:
        return {"available": False, "reason": "camera was off"}

    face_cls, face_opt = _options("face")
    pose_cls, pose_opt = _options("pose")
    hand_cls, hand_opt = _options("hand")

    per_frame = []
    with face_cls.create_from_options(face_opt) as face, \
            pose_cls.create_from_options(pose_opt) as pose, \
            hand_cls.create_from_options(hand_opt) as hands:
        for f in frames:
            image = mp.Image.create_from_file(f["path"])
            ts = int(f["t"] * 1000)
            per_frame.append({
                "t": f["t"],
                "face": face.detect_for_video(image, ts),
                "pose": pose.detect_for_video(image, ts),
                "hands": hands.detect_for_video(image, ts),
            })
    return summarize(per_frame)


def summarize(per_frame: list[dict]) -> dict:
    face_frames, looking, looking_down, smiles, animated = 0, [], [], [], 0
    prev_shapes = None
    gesture_frames = 0
    prev_wrists: dict[str, tuple[float, float]] = {}
    sway_x = []

    for fr in per_frame:
        t = fr["t"]
        face = fr["face"]
        if face.face_landmarks:
            face_frames += 1
            yaw, pitch = head_angles(face.facial_transformation_matrixes[0])
            ok = abs(yaw) <= YAW_OK_DEG and abs(pitch) <= PITCH_OK_DEG
            looking.append((t, ok))
            looking_down.append((t, pitch < -PITCH_OK_DEG))

            shapes = {b.category_name: b.score for b in face.face_blendshapes[0]}
            smiles.append((t, (shapes.get("mouthSmileLeft", 0) + shapes.get("mouthSmileRight", 0)) / 2 > SMILE))
            vec = np.array([shapes[k] for k in sorted(shapes)])
            if prev_shapes is not None and len(vec) == len(prev_shapes):
                if float(np.mean(np.abs(vec - prev_shapes))) > ANIMATED_DELTA:
                    animated += 1
            prev_shapes = vec

        moving = False
        hands = fr["hands"]
        for lm, hd in zip(hands.hand_landmarks or [], hands.handedness or []):
            side = hd[0].category_name
            wrist = (lm[0].x, lm[0].y)
            if side in prev_wrists:
                dx, dy = wrist[0] - prev_wrists[side][0], wrist[1] - prev_wrists[side][1]
                moving |= math.hypot(dx, dy) > WRIST_MOVE
            prev_wrists[side] = wrist
        if not hands.hand_landmarks:
            prev_wrists.clear()
        gesture_frames += moving

        pose = fr["pose"]
        if pose.pose_landmarks:
            lm = pose.pose_landmarks[0]
            hips_visible = min(lm[23].visibility, lm[24].visibility) > 0.5
            a, b = (lm[23], lm[24]) if hips_visible else (lm[11], lm[12])
            sway_x.append((t, (a.x + b.x) / 2))

    if face_frames == 0:
        return {"available": False, "reason": "no face found on camera"}

    duration_min = max((per_frame[-1]["t"] - per_frame[0]["t"]) / 60, 1 / 60)
    sways = _sway_events(sway_x)
    smile_starts = [t for i, (t, s) in enumerate(smiles) if s and (i == 0 or not smiles[i - 1][1])]
    return {
        "available": True,
        "frames": len(per_frame),
        "eye_contact_pct": round(100 * sum(ok for _, ok in looking) / face_frames, 1),
        "looking_down_pct": round(100 * sum(d for _, d in looking_down) / face_frames, 1),
        "looking_away_spans": _spans([(t, not ok) for t, ok in looking], min_s=3.0),
        "smiles_per_min": round(len(smile_starts) / duration_min, 2),
        "face_animated_pct": round(100 * animated / face_frames, 1),
        "gesture_pct": round(100 * gesture_frames / len(per_frame), 1),
        "hands_still_pct": round(100 - 100 * gesture_frames / len(per_frame), 1),
        "sway_events": sways,
        "sway_per_10s": round(len(sways) / max(duration_min * 6, 1 / 6), 2),
        "timeline": _eye_timeline(looking),
    }


def _sway_events(series: list[tuple[float, float]]) -> list[dict]:
    """Side to side swings: direction reversals of the body midpoint bigger than SWAY_AMPLITUDE."""
    if len(series) < 5:
        return []
    xs = np.array([x for _, x in series])
    xs = np.convolve(xs - np.median(xs), np.ones(3) / 3, mode="same")
    events, anchor_i, direction = [], 0, 0
    for i in range(1, len(xs)):
        delta = xs[i] - xs[anchor_i]
        if abs(delta) >= SWAY_AMPLITUDE:
            new_dir = 1 if delta > 0 else -1
            if direction and new_dir != direction:
                events.append({"start": round(series[anchor_i][0], 2), "end": round(series[i][0], 2)})
            direction, anchor_i = new_dir, i
    return events


def _spans(flags: list[tuple[float, bool]], min_s: float) -> list[dict]:
    spans, start = [], None
    for t, on in flags:
        if on and start is None:
            start = t
        elif not on and start is not None:
            if t - start >= min_s:
                spans.append({"start": round(start, 2), "end": round(t, 2)})
            start = None
    if start is not None and flags and flags[-1][0] - start >= min_s:
        spans.append({"start": round(start, 2), "end": round(flags[-1][0], 2)})
    return spans


def _eye_timeline(looking: list[tuple[float, bool]]) -> list[dict]:
    buckets: dict[int, list[bool]] = {}
    for t, ok in looking:
        buckets.setdefault(int(t // 5) * 5, []).append(ok)
    return [{"t": k, "eye_contact_pct": round(100 * sum(v) / len(v), 1)} for k, v in sorted(buckets.items())]
