"""M4: feature analyzers. Turns M3 preprocessing output into timed facts.

    result = analyze(preprocessed, context)
    result["facts"]    -> list of facts for the inference engine
    result["metrics"]  -> the raw measurements, used for the report's charts

`context` = {occasion, mode, audience, time_limit_s, oli_turns: [{start, end, text}]}
While Oli is speaking (oli_turns) doesn't count against the user's pace,
pauses, or eye contact.

The transcript, voice, and camera analyzers don't depend on each other, so
voice and camera run in parallel threads.
"""

from concurrent.futures import ThreadPoolExecutor

from .answers import analyze_answers
from .facts import setup_facts, transcript_facts, vision_facts, voice_facts
from .fillers import analyze_fillers
from .language import APOLOGIES, HEDGES, analyze_content, clarity, phrase_instances
from .pace import analyze_pace
from .pauses import analyze_pauses
from .text_utils import sentences
from .vision import analyze_vision
from .voice import analyze_voice


def analyze(pre: dict, context: dict) -> dict:
    words = pre["transcript"]["words"]
    oli = context.get("oli_turns") or []
    oli_spans = [(q["start"], q["end"]) for q in oli if q.get("end")]

    with ThreadPoolExecutor(max_workers=2) as pool:
        voice_job = pool.submit(analyze_voice, pre["audio"]["path"], sentences(words))
        vision_job = pool.submit(analyze_vision, pre["frames"], oli_spans)

        pace = analyze_pace(words, exclude=oli_spans)
        metrics = {
            "duration_s": pre["duration_s"],
            "word_count": len(words),
            "speech_start": words[0]["start"] if words else 0.0,
            "speech_end": words[-1]["end"] if words else 0.0,
            "pace": pace,
            "fillers": analyze_fillers(words, pace.get("speaking_s", 0) / 60),
            "pauses": analyze_pauses(words, exclude=oli_spans),
            "clarity": clarity(words),
            "hedges": phrase_instances(words, HEDGES),
            "apologies": phrase_instances(words, APOLOGIES),
            "content": analyze_content(words),
            "answers": analyze_answers(words, oli, pre["duration_s"]),
        }
        metrics["voice"] = voice_job.result()
        metrics["vision"] = vision_job.result()

    facts = (setup_facts(context) + transcript_facts(metrics, context)
             + voice_facts(metrics["voice"]) + vision_facts(metrics["vision"]))
    return {"facts": facts, "metrics": metrics}


__all__ = ["analyze"]
