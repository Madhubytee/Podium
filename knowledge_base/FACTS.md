# Writing rules for Podium

Rules live in [rules.json](rules.json). Domain experts can change thresholds there without touching code. Run `python -m pytest inference` afterwards; the tests load the real file and catch typos.

## Rule shape

```json
{
  "id": 15, "key": "nervous_rushing", "name": "Nervous rushing", "area": "Combined",
  "kind": "fix",                 // "fix" or "strength"
  "severity": 0.8,               // 0 to 1
  "occasions": ["presentation", "pitch"],   // or ["all"]
  "occasion_weight": {"pitch": 1.2},        // optional: matters more for some occasions
  "if": { ...condition... },
  "moments": { ...condition... },           // optional: which facts become video clips
  "suppresses": [1, 3],                     // optional: hide these rules when this one fires
  "then": {"why": "...", "tip": "...", "drill": "..."}
}
```

When a rule fires, the engine adds a fact named after its `key` with value `true`. Later rules can build on it. Rule 20, for example, checks `nervous_rushing == true` and `weak_opening == true`.

## Conditions

| Form | Meaning |
| --- | --- |
| `{"fact": "pace_wpm", "op": ">", "value": 170}` | Some `pace_wpm` fact is over 170 |
| `{"fact": "pause", "tag": "mid_sentence", "op": ">=", "value": 2, "min_count": 2}` | At least 2 mid sentence pauses of 2 s or more |
| `{"fact": "sentence_end_drop", "op": ">", "value": 6, "min_ratio": 0.4}` | Over 40% of sentence endings dropped more than 6 dB |
| `{"fact": "filler", "within": "first_15s"}` | Any filler in the first 15 seconds (`first_15s`, `first_20pct`, `last_20pct`) |
| `{"fact": "pause", "same_time_as": "looking_away"}` | A pause that overlaps a moment of looking away |
| `{"fact": "answer"}` | The fact exists at all |
| `{"all": [...]}`, `{"any": [...]}`, `{"not": {...}}` | Combine conditions |

Ops: `>`, `>=`, `<`, `<=`, `==`, `!=`, `between` (value `[low, high]`), `in` (value is a list). A missing fact never matches, so camera rules don't fire when the camera is off.

## Fact vocabulary

| Fact | Value | Timed | Source |
| --- | --- | --- | --- |
| `occasion`, `mode`, `audience` | text | no | setup |
| `time_limit_s` | seconds | no | setup |
| `duration_s`, `word_count` | number | whole take | transcript |
| `time_used_ratio` | duration / time limit | whole take | transcript |
| `pace_wpm` | words per minute | speech span | transcript |
| `pace_window` | wpm over a 15 s window | yes | transcript |
| `filler` | the filler word, tagged with it | yes | transcript |
| `filler_count`, `filler_per_min` | number | whole take | transcript |
| `pause` | seconds; tags `mid_sentence` or `between_sentences`, plus `long` | yes | audio |
| `pause_per_min`, `emphasis_pause_per_min` | number | whole take | audio |
| `clarity` | average Whisper confidence, 0 to 1 | whole take | transcript |
| `unclear_word` | word with confidence under 0.4 | yes | transcript |
| `hedge`, `apology`, `cta` | the phrase | yes | transcript |
| `hedge_count`, `apology_count` | number | whole take | transcript |
| `has_hook` | true/false (first 15 s) | opening | transcript |
| `has_cta_end` | true/false (last 20%) | closing | transcript |
| `answer` | seconds from Oli finishing to the last word; tags are the STAR parts found | yes | transcript |
| `star_ratio` | share of answers with 3+ STAR parts | whole take | transcript |
| `pitch_sd_hz`, `pitch_range_hz`, `pitch_mean_hz` | Hz | no | audio |
| `volume_db` | mean dBFS while speaking | no | audio |
| `sentence_end_drop` | dB drop in a sentence's last 0.5 s | yes | audio |
| `energy` | mean dB over 5 s | yes | audio |
| `camera_on` | true/false | no | video |
| `eye_contact_pct`, `looking_down_pct` | percent of face frames | no | video |
| `looking_away` | seconds (3 s or longer) | yes | video |
| `smiles_per_min`, `face_animated_pct` | number | no | video |
| `gesture_pct`, `hands_still_pct` | percent of frames | no | video |
| `sway` / `sway_per_10s` | one per swing / rate | yes / no | video |
| `metric_change` | percent improvement since the last take; tag is the metric | no | progress |
| *any rule key* | `true` once that rule fires | no | engine |
