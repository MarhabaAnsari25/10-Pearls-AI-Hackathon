# Utility Bill Decoder (WTQ Build Track)

AI assistant that reads Pakistani electricity bills (K-Electric / LESCO / IESCO), extracts structured JSON (Level 1), and answers customer questions in plain English (Level 2).

**Runtime:** Python 3.14 (requires Python 3.11+)

## Setup

```bash
cd c:\bill-decoder
py -m pip install -r source\requirements.txt
copy source\.env.example .env
```

Edit `.env` and set your Google AI Studio API key:

```env
MODEL_PROVIDER=google
MODEL_NAME=gemini-3.5-flash-lite
MODEL_FALLBACK=gemini-3.1-flash-lite
API_KEY=your-api-key-here
```

Do **not** commit `.env` or include it in the submission ZIP.

## Run on training bills

```bash
cd c:\bill-decoder
py -m source.main --bills-dir train_bills --out-dir output --verify-kesc-0008
```

Outputs:

- `output/level1.csv` — one JSON object per bill
- `output/level2.csv` — sample Q&A rows (guide §6.2 questions until test template arrives)
- `output/json/*.json` — pretty Level-1 dumps for debugging

Level-1 only:

```bash
py -m source.main --bills-dir train_bills --out-dir output --skip-level2 --verify-kesc-0008
```

## Run on organizer test folder (when available)

```bash
py -m source.main ^
  --bills-dir test\bills ^
  --level1-template test\csv\level1.csv ^
  --level2-template test\csv\level2.csv ^
  --out-dir output
```

Copy `output/level1.csv` and `output/level2.csv` into your submission `output/` folder.

## Project layout

```
source/
  main.py              CLI entry
  config.py            env loading
  gemini_client.py     Gemini 3.5 primary + 3.1 fallback
  schema.py            Level-1 field definitions
  level1_extract.py    vision extraction + validation
  level2_answer.py     Q&A + calculation hints
  csv_io.py            CSV read/write
  requirements.txt
  .env.example
  README.md
```

## AI usage

| Category | Used |
|---|---|
| Models | `gemini-3.5-flash-lite` (primary), `gemini-3.1-flash-lite` (fallback) |
| APIs / services | Google AI Studio / Gemini API (`google-genai`) |
| Local OCR | none |
| Invoice/receipt extraction agents | none (prohibited) |
| AI coding assistants | Cursor (Composer) — used to help write this project |
| Other chatbots | none |

## Notes

- Level-1 extracts printed values only (no recalculation). Unreadable / grey-boxed fields are `null`.
- Personal identifiers are never returned.
- Free-tier Gemini limits apply (~15 requests/min). The client retries and falls back to 3.1 on failures.
