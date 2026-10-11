"""Level-1 bill extraction via Gemini vision (guide §5)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .gemini_client import GeminiClient
from .schema import (
    CHARGE_TYPES,
    KESC_0008_EXPECTED,
    LEVEL1_SCHEMA_HINT,
    PROVIDERS,
    TAX_TYPES,
    TOP_LEVEL_FIELDS,
)

EXTRACTION_PROMPT = f"""You extract electricity bill fields from an image for a competition.

Return ONE JSON object only. No markdown fences. No commentary.

Schema (include every field; use null when unavailable; use [] for empty lists):
{LEVEL1_SCHEMA_HINT}

Rules (follow exactly):
1. Extract values as printed. Do NOT recalculate, round, or "fix" amounts.
2. Amounts are numbers in PKR. Remove currency labels and commas. Example: "Rs. 19,964" -> 19964.
3. Credits/subsidies are negative. Example: "38209CR" -> -38209. Subsidy charge amounts must be negative.
4. Dates: "22nd Sep 2026" -> "2026-09-22"; "MAR 2026" -> "2026-03".
5. Use null when not printed, blank, covered by a grey box, or unreadable. Do NOT guess.
6. Do NOT return names, addresses, CNIC, account numbers, reference numbers, consumer numbers, or meter numbers.
7. provider must be exactly one of: KE, LESCO, IESCO.
   - K-Electric / KE / KESC bills use provider "KE".
8. tariff: exact printed tariff code (e.g. A1-R or A-1a(01)).
9. sanctioned_load_kw: from Sanc Load / S.Load / San Load.
10. charges: one entry per non-blank, non-zero line in the charges section.
    - Keep separate entries when the same type appears more than once.
    - Skip lines printed as 0.
    - Classify by meaning:
      energy = Variable Upto ... Units / Cost of Electricity / Energy Charges
      fixed = Fixed charges
      fpa = FPA or FCA (fuel price / fuel cost adjustment)
      quarterly_adjustment = QTA / Uniform Quarterly Adjustment
      surcharge = Additional Surcharge (PHL), F.C Surcharge, etc.
      meter_rent = Meter rent / service rent
      subsidy = Government subsidy / relief (amount negative)
      other = anything else in charges
11. taxes: one entry per tax/government line. Classify by section, not only the name.
    - If only a combined tax amount is printed (no line split), return taxes=[] and put that amount in total_taxes.
    - gst = Sales tax / GST (including GST on FPA)
    - electricity_duty = ED / Electricity duty
    - income_tax = Income tax
    - municipal_tax = Municipal/local under taxes (e.g. KE MUCT (KMC))
    - other_tax = Extra tax, further tax, TV fee, etc.
12. total_charges / total_taxes: printed subtotals, or null if no subtotal printed.
13. arrears: previous dues carried forward; keep printed sign; null if blank.
14. payable_after_due_date: if several late-payment amounts are shown, use the HIGHEST.
15. Numeric fields must be JSON numbers, not quoted strings.

Return only the JSON object.
"""


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _to_number(value: Any) -> float | int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() in {"null", "none", "n/a", "-"}:
            return None
        negative = False
        if s.upper().endswith("CR"):
            negative = True
            s = s[:-2]
        s = s.replace("Rs.", "").replace("RS.", "").replace("PKR", "")
        s = s.replace(",", "").replace(" ", "").strip()
        if s.startswith("(") and s.endswith(")"):
            negative = True
            s = s[1:-1]
        try:
            num: float | int = float(s) if "." in s else int(s)
        except ValueError:
            return None
        if negative:
            num = -abs(float(num))
            if float(num).is_integer():
                return int(num)
            return float(num)
        if isinstance(num, float) and num.is_integer():
            return int(num)
        return num
    return None


def _normalize_item_list(items: Any, allowed: frozenset[str], *, force_negative_subsidy: bool) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        typ = str(item.get("type", "other")).strip().lower()
        if typ not in allowed:
            typ = "other" if allowed is CHARGE_TYPES else "other_tax"
        amount = _to_number(item.get("amount"))
        if amount is None:
            continue
        if amount == 0:
            continue
        if force_negative_subsidy and typ == "subsidy" and amount > 0:
            amount = -amount
        out.append({"type": typ, "amount": amount})
    return out


def normalize_level1(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce model output into the required schema shape."""
    provider = data.get("provider")
    if isinstance(provider, str):
        p = provider.strip().upper()
        if p in {"K-ELECTRIC", "KESC", "K.E", "K.E."}:
            p = "KE"
        provider = p if p in PROVIDERS else None
    else:
        provider = None

    result: dict[str, Any] = {field: None for field in TOP_LEVEL_FIELDS}
    result["provider"] = provider
    result["tariff"] = data.get("tariff") if isinstance(data.get("tariff"), str) and data.get("tariff").strip() else None
    if result["tariff"]:
        result["tariff"] = result["tariff"].strip()

    for key in (
        "sanctioned_load_kw",
        "previous_reading",
        "current_reading",
        "units_consumed",
        "total_charges",
        "total_taxes",
        "current_bill",
        "arrears",
        "payable_within_due_date",
        "payable_after_due_date",
    ):
        result[key] = _to_number(data.get(key))

    for key in ("bill_month", "reading_date", "issue_date", "due_date"):
        val = data.get(key)
        if isinstance(val, str) and val.strip() and val.strip().lower() != "null":
            result[key] = val.strip()
        else:
            result[key] = None

    result["charges"] = _normalize_item_list(
        data.get("charges"), CHARGE_TYPES, force_negative_subsidy=True
    )
    result["taxes"] = _normalize_item_list(
        data.get("taxes"), TAX_TYPES, force_negative_subsidy=False
    )
    return result


def parse_level1_response(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text)
    # If model wrapped extra text, pull the outermost JSON object
    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response")
        cleaned = match.group(0)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Level-1 response is not a JSON object")
    return normalize_level1(data)


def extract_bill(client: GeminiClient, image_path: Path) -> dict[str, Any]:
    print(f"  [level1] extracting {image_path.name}")
    text = client.generate(EXTRACTION_PROMPT, image_path=image_path, temperature=0.05)
    return parse_level1_response(text)


def compare_to_expected(
    actual: dict[str, Any],
    expected: dict[str, Any] | None = None,
    *,
    number_tol: float = 1.0,
) -> list[str]:
    """Return list of mismatch descriptions (empty if match). Guide: numbers ±1."""
    expected = expected or KESC_0008_EXPECTED
    mismatches: list[str] = []

    for key in TOP_LEVEL_FIELDS:
        if key in ("charges", "taxes"):
            continue
        a = actual.get(key)
        e = expected.get(key)
        if isinstance(e, (int, float)) and isinstance(a, (int, float)):
            if abs(float(a) - float(e)) > number_tol:
                mismatches.append(f"{key}: got {a}, expected {e}")
        elif a != e:
            mismatches.append(f"{key}: got {a!r}, expected {e!r}")

    for list_key in ("charges", "taxes"):
        a_list = actual.get(list_key) or []
        e_list = expected.get(list_key) or []
        if len(a_list) != len(e_list):
            mismatches.append(f"{list_key}: length {len(a_list)} vs {len(e_list)}")
            continue
        for i, (a_item, e_item) in enumerate(zip(a_list, e_list)):
            if a_item.get("type") != e_item.get("type"):
                mismatches.append(
                    f"{list_key}[{i}].type: got {a_item.get('type')}, expected {e_item.get('type')}"
                )
            aa = a_item.get("amount")
            ee = e_item.get("amount")
            if isinstance(aa, (int, float)) and isinstance(ee, (int, float)):
                if abs(float(aa) - float(ee)) > number_tol:
                    mismatches.append(f"{list_key}[{i}].amount: got {aa}, expected {ee}")
            elif aa != ee:
                mismatches.append(f"{list_key}[{i}].amount: got {aa!r}, expected {ee!r}")

    return mismatches
