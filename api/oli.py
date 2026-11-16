"""Oli's side of the live conversation, played by ChatGPT.

Design choice: the language model only plays the role (asks questions, argues
back). It never grades. All coaching comes from the rule engine, so feedback is
consistent, explainable, and based on our experts' rules.
"""

import os
from functools import lru_cache

MODEL = os.getenv("PODIUM_OLI_MODEL", "gpt-4o-mini")
END_TAG = "[END]"
MAX_FILE_CHARS = 12_000  # per file; keeps prompts small for a cheap, fast model

ROLES = {
    "interview": (
        "You are Oli, a friendly but realistic interviewer for the role described below. "
        "Ask one question at a time, under 40 words. Mix behavioral and role specific questions. "
        "Ask a natural follow up when an answer is vague or missing a result."
    ),
    "pitch": (
        "You are Oli, a sharp but kind investor hearing this pitch. First ask them to give their pitch. "
        "Then ask one tough investor question at a time, under 40 words: market, traction, competition, "
        "the team, the business model, and what they're asking for."
    ),
    "debate": (
        "You are Oli, a debate opponent. Take the opposite side of the user's position on the motion below. "
        "Make one short counter argument at a time (under 50 words) and end it with a direct challenge "
        "the user has to answer. Be respectful and stick to the arguments."
    ),
    "presentation": (
        "You are Oli, an engaged audience member at this presentation. First invite them to present. "
        "Then ask one audience question at a time, under 40 words, about what they said."
    ),
    "speech": (
        "You are Oli, a warm guest at this event. First invite them to give their speech or toast. "
        "Afterwards, react in one short friendly line and ask if they'd like to take it from the top."
    ),
}


class OliUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _client():
    if not os.getenv("OPENAI_API_KEY"):
        raise OliUnavailable("Add OPENAI_API_KEY to .env so Oli can talk back in live mode.")
    from openai import OpenAI

    return OpenAI()


def system_prompt(rehearsal: dict, files: list[dict], n_questions: int) -> str:
    occasion = rehearsal["occasion"]
    parts = [
        ROLES.get(occasion, ROLES["interview"]),
        "Never give feedback, scores, or coaching on how they speak. A separate system does that.",
        "Speak naturally, as your words will be read aloud. No lists, no markdown, no stage directions.",
        f"After about {n_questions} questions, thank them, say the session is over, and end your message with {END_TAG}.",
        f"If they ask to stop, wrap up politely and end with {END_TAG}.",
        "",
        f"Occasion: {occasion}.",
    ]
    if rehearsal.get("audience"):
        parts.append(f"Audience: {rehearsal['audience']}.")
    if rehearsal.get("details"):
        parts.append(f"What the user told us about it: {rehearsal['details']}")
    for f in files:
        text = (f["extracted_text"] or "")[:MAX_FILE_CHARS]
        if text:
            parts.append(f"\n--- {f['kind']} ({f['filename']}) ---\n{text}")
    return "\n".join(parts)


def next_line(rehearsal: dict, files: list[dict], turns: list[dict], n_questions: int,
              instruction: str | None = None) -> tuple[str, bool]:
    """Oli's next line given the conversation so far. Returns (text, is_final)."""
    messages = [{"role": "system", "content": system_prompt(rehearsal, files, n_questions)}]
    for t in turns:
        messages.append({"role": "assistant" if t["speaker"] == "oli" else "user", "content": t["text"]})
    if not turns:
        messages.append({"role": "user", "content": "(The user is ready. Greet them in one short sentence and start.)"})
    if instruction:
        messages.append({"role": "user", "content": f"({instruction})"})

    resp = _client().chat.completions.create(model=MODEL, messages=messages, max_completion_tokens=300)
    text = (resp.choices[0].message.content or "").strip()
    final = END_TAG in text
    return text.replace(END_TAG, "").strip(), final


def hint(rehearsal: dict, files: list[dict], turns: list[dict]) -> str:
    """A nudge for the current question: what a strong answer would cover, not a script."""
    last_q = next((t["text"] for t in reversed(turns) if t["speaker"] == "oli"), "")
    messages = [
        {"role": "system", "content": system_prompt(rehearsal, files, 5)},
        {"role": "user", "content": (
            f"(Step out of role for a moment. The user asked for a hint on: \"{last_q}\". "
            "In one or two short sentences, suggest what a strong answer would cover, drawing on their "
            "files if relevant. Don't write the answer for them.)")},
    ]
    resp = _client().chat.completions.create(model=MODEL, messages=messages, max_completion_tokens=150)
    return (resp.choices[0].message.content or "").strip()
