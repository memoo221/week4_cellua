# Classifier v1

## Inputs

- `user_message` — the user's raw message this turn
- `attached_code` — code the user attached, if any (may be null)
- `recent_turns` — buffer-tier conversation history, for context
- `summary` — rolling summary of older turns, if any (may be null)

## Output contract

A single JSON object with exactly these keys:

- `intent` — one of: `"explain"`, `"generate"`
- `intent_confidence` — float in `[0, 1]`
- `language` — programming language string if code is involved, else `null`

No prose, no markdown fencing — the raw response body must be valid JSON
matching the shape above, since `services/llm.py:run_classifier` parses it
directly.

<!-- TODO: actual prompt instructions go here. -->
