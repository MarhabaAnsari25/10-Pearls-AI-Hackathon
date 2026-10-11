"""Level-2 customer Q&A grounded in the bill (guide §6)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .gemini_client import GeminiClient

# Guide §6.2 sample questions for local dry-run on KESC_0008
SAMPLE_QUESTIONS: list[tuple[str, str]] = [
    ("Q1", "How much of my bill is taxes?"),
    ("Q2", "How many months in my history went above 200 units?"),
]


def _pct(part: float, whole: float) -> float:
    if whole == 0:
        return 0.0
    return round(100.0 * part / whole, 2)


def build_calc_hints(level1: dict[str, Any]) -> str:
    """Deterministic helpers the model can use; code does the math (guide §6.1)."""
    total_taxes = level1.get("total_taxes")
    current_bill = level1.get("current_bill")
    total_charges = level1.get("total_charges")
    units = level1.get("units_consumed")

    tax_lines = level1.get("taxes") or []
    charge_lines = level1.get("charges") or []

    hints: dict[str, Any] = {
        "units_consumed": units,
        "total_taxes": total_taxes,
        "total_charges": total_charges,
        "current_bill": current_bill,
        "tax_lines": tax_lines,
        "charge_lines": charge_lines,
    }

    if isinstance(total_taxes, (int, float)) and isinstance(current_bill, (int, float)):
        hints["taxes_as_pct_of_current_bill"] = _pct(float(total_taxes), float(current_bill))
    if isinstance(total_charges, (int, float)) and isinstance(current_bill, (int, float)):
        hints["charges_as_pct_of_current_bill"] = _pct(float(total_charges), float(current_bill))
    if isinstance(total_taxes, (int, float)) and isinstance(total_charges, (int, float)):
        denom = float(total_taxes) + float(total_charges)
        if denom:
            hints["charges_vs_taxes_split_pct"] = {
                "charges_pct": _pct(float(total_charges), denom),
                "taxes_pct": _pct(float(total_taxes), denom),
            }

    return json.dumps(hints, ensure_ascii=False, indent=2)


ANSWER_RULES = """
Answer rules (must follow):
1. Get numbers right. Prefer the provided calculation_hints for averages, differences, counts, percentages.
2. Ground the answer only in this bill image and the extracted JSON. Do NOT use outside tariff tables or rates.
3. If a needed value is not on the bill, say so clearly. Do not guess.
4. Label estimates and briefly explain how you calculated them.
5. If a question has more than one reasonable meaning, state the meaning you used or answer both.
6. Exclude personal identifiers (names, addresses, CNIC, account/reference/consumer/meter numbers).
7. Write the entire answer in English, even if parts of the bill are in Urdu.
8. Return ONLY the answer text — no JSON, no markdown title, no preface like "Answer:".
""".strip()


def answer_question(
    client: GeminiClient,
    image_path: Path,
    level1: dict[str, Any],
    question: str,
) -> str:
    hints = build_calc_hints(level1)
    prompt = f"""You are a helpful utility-bill assistant for Pakistani electricity bills (KE, LESCO, IESCO).

{ANSWER_RULES}

Extracted Level-1 JSON for this bill:
{json.dumps(level1, ensure_ascii=False)}

Pre-computed calculation_hints (trust these numbers for math):
{hints}

Customer question:
{question}
"""
    text = client.generate(prompt, image_path=image_path, temperature=0.2)
    return _clean_answer(text)


def _clean_answer(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Drop a leading "Answer:" label if present
    text = re.sub(r"^answer\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return text
