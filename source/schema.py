"""Level-1 JSON schema and field rules from the participant guide §5."""

from __future__ import annotations

from typing import Any

CHARGE_TYPES = frozenset(
    {
        "energy",
        "fixed",
        "fpa",
        "quarterly_adjustment",
        "surcharge",
        "meter_rent",
        "subsidy",
        "other",
    }
)

TAX_TYPES = frozenset(
    {
        "gst",
        "electricity_duty",
        "income_tax",
        "municipal_tax",
        "other_tax",
    }
)

PROVIDERS = frozenset({"KE", "LESCO", "IESCO"})

TOP_LEVEL_FIELDS = (
    "provider",
    "tariff",
    "sanctioned_load_kw",
    "bill_month",
    "reading_date",
    "issue_date",
    "due_date",
    "previous_reading",
    "current_reading",
    "units_consumed",
    "charges",
    "total_charges",
    "taxes",
    "total_taxes",
    "current_bill",
    "arrears",
    "payable_within_due_date",
    "payable_after_due_date",
)

# Guide §5.7 — correct JSON for training bill KESC_0008
KESC_0008_EXPECTED: dict[str, Any] = {
    "provider": "KE",
    "tariff": "A1-R",
    "sanctioned_load_kw": 3,
    "bill_month": "2026-04",
    "reading_date": "2026-04-03",
    "issue_date": "2026-04-07",
    "due_date": "2026-04-21",
    "previous_reading": 8819,
    "current_reading": 8970,
    "units_consumed": 151,
    "charges": [
        {"type": "fixed", "amount": 900},
        {"type": "energy", "amount": 1054},
        {"type": "energy", "amount": 663.51},
        {"type": "quarterly_adjustment", "amount": 52.91},
        {"type": "fpa", "amount": 125.27},
        {"type": "surcharge", "amount": 64.93},
    ],
    "total_charges": 2860.62,
    "taxes": [
        {"type": "electricity_duty", "amount": 29.41},
        {"type": "gst", "amount": 520.21},
        {"type": "municipal_tax", "amount": 20},
    ],
    "total_taxes": 569.62,
    "current_bill": 3430.24,
    "arrears": -0.53,
    "payable_within_due_date": 3430,
    "payable_after_due_date": 3716,
}

LEVEL1_SCHEMA_HINT = """
{
  "provider": "KE | LESCO | IESCO",
  "tariff": "string",
  "sanctioned_load_kw": number or null,
  "bill_month": "YYYY-MM" or null,
  "reading_date": "YYYY-MM-DD" or null,
  "issue_date": "YYYY-MM-DD" or null,
  "due_date": "YYYY-MM-DD" or null,
  "previous_reading": number or null,
  "current_reading": number or null,
  "units_consumed": number or null,
  "charges": [{"type": "energy|fixed|fpa|quarterly_adjustment|surcharge|meter_rent|subsidy|other", "amount": number}],
  "total_charges": number or null,
  "taxes": [{"type": "gst|electricity_duty|income_tax|municipal_tax|other_tax", "amount": number}],
  "total_taxes": number or null,
  "current_bill": number or null,
  "arrears": number or null,
  "payable_within_due_date": number or null,
  "payable_after_due_date": number or null
}
""".strip()
