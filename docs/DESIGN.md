# Podium design spec

The approved design lives in `home-page/index.html` (open it in a browser to see it). This file explains the rules behind it so new screens match.

## The idea

Podium looks like **a rehearsal script and a coach's notes**, not a dashboard. Content sits straight on warm paper. Structure comes from type, thin rules, and spacing.

**Never use white bordered cards, panels, or boxes around content.** That was the main thing that made earlier versions look AI generated. The only filled shapes are red buttons and the sidebar.

The forest only appears in the landing hero, as a looping video (`forest.mp4`, 7 seconds, seamless, falling leaves) with `forest-poster.webp` as the poster and the reduced motion fallback. Everything past the hero, and the whole app, is plain paper.

## Colors

| Token | Hex | Use |
| --- | --- | --- |
| `--ink` | #33261C | Main text |
| `--ink-soft` | #6B5544 | Secondary text |
| `--ink-mute` | #8A725F | Labels, placeholders, meta |
| `--line` | #4A3527 | Illustration style outlines (speech bubble) |
| `--page` | #FAF3E8 | Page background |
| `--sky` | #F4DBC1 | Top nav, hero, final call to action band |
| `--side` | #F1E7D9 | App sidebar |
| `--rule` | #E2D2BD | Thin divider lines |
| `--tomato` | #C4513A | Buttons, wavy filler marks, active tab underline |
| `--tomato-deep` | #A23F2A | Hover, kickers, OLI cue, links |
| `--olive` | #5F6E33 | Pause marks, "keep doing this", avatar |

No blue anywhere. No gradients.

## Type

- **Bricolage Grotesque** (500, 600, 700): headings, big numbers, Oli's questions.
- **Figtree** (400 to 700): body and UI. Body is 500, labels 600, buttons 700.
- **Courier Prime** (400, 700): anything that is speech: script lines, transcripts, the "OLI" / "YOU" cues, the timer.

All from Google Fonts.

## Patterns

- **Script lines:** a small uppercase Courier cue (`OLI` in tomato deep, `YOU` in ink mute), then the line in Courier.
- **Coach's marks:** fillers get `text-decoration: underline wavy var(--tomato)`. Pauses show inline as `‖ 3.4s` in olive. Superscript numbers link the transcript to margin notes.
- **Margin notes:** a list with a 2px tomato left rule, no box.
- **Stats:** big Bricolage numbers in a row, separated by 1px vertical rules, a rule above.
- **Columns:** separated by 1px vertical rules, not cards.
- **Lists:** dotted leaders between the label and the value, like a menu.
- **Tabs:** text with a 3px tomato underline on the active one, sitting on a 1px baseline rule.
- **Inputs:** the setup reads as a sentence: "It runs about [30 minutes] and I'm talking to [recruiters]." Selects are tomato words with a tomato underline. The notes field is lined paper (only ruled lines, no border box). Radio options are a plain list divided by rules.
- **Corners:** small (4 to 6px) on the few things that have a shape. Nothing pill shaped except the illustrated speech bubble.
- **Shadows:** none, except a soft one on the sidebar drawer on mobile.

## Oli

- One Oli per screen, never a crowd of them.
- His pose matches the context: `oli-interview` (listening), `oli-pitch` (proud), `oli-presentation` (waving), `oli-speech` (cheering), `oli-debate` (thinking).
- Landing: `oli-hello.webp` plays once (he flies in and lands on the stump), then swaps to `oli-idle.webp` at 10 seconds. With reduced motion, use `oli-still.webp`.
- His hero speech bubble is drawn with the illustration's brown outline (`--line`, 2.5px), not a white card.
- The webp files in `home-page/` have transparent backgrounds. Use those, not the cream background PNGs and MP4s in `Oli/`.

## Copy voice

Plain, warm, specific. Oli talks in contractions and stays in character for the occasion. No hyphens or em dashes in UI copy.
