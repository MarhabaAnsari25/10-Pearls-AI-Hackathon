"""CLI: extract Level-1 JSON and Level-2 answers for a folder of bill images."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .csv_io import (
    bill_id_from_path,
    find_bill_image,
    list_bill_images,
    read_level1_template,
    read_level2_template,
    write_level1_csv,
    write_level2_csv,
)
from .gemini_client import GeminiClient
from .level1_extract import compare_to_expected, extract_bill
from .level2_answer import SAMPLE_QUESTIONS, answer_question


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Utility Bill Decoder — extract JSON and answer questions (WTQ)."
    )
    p.add_argument(
        "--bills-dir",
        type=Path,
        required=True,
        help="Folder of bill images (.png/.jpg)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Folder for level1.csv and level2.csv",
    )
    p.add_argument(
        "--level1-template",
        type=Path,
        default=None,
        help="Optional organizer level1.csv (bill_id column). Preserves row order.",
    )
    p.add_argument(
        "--level2-template",
        type=Path,
        default=None,
        help="Optional organizer level2.csv with questions. Fills answer column.",
    )
    p.add_argument(
        "--verify-kesc-0008",
        action="store_true",
        help="After extracting KESC_0008, compare to guide §5.7 sample JSON.",
    )
    p.add_argument(
        "--skip-level2",
        action="store_true",
        help="Only run Level-1 extraction.",
    )
    return p.parse_args(argv)


def resolve_bill_ids(bills_dir: Path, level1_template: Path | None) -> list[str]:
    if level1_template is not None:
        return read_level1_template(level1_template)
    return [bill_id_from_path(p) for p in list_bill_images(bills_dir)]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bills_dir: Path = args.bills_dir
    out_dir: Path = args.out_dir

    if not bills_dir.is_dir():
        print(f"ERROR: bills dir not found: {bills_dir}", file=sys.stderr)
        return 1

    client = GeminiClient()
    bill_ids = resolve_bill_ids(bills_dir, args.level1_template)
    if not bill_ids:
        print(f"ERROR: no bills found in {bills_dir}", file=sys.stderr)
        return 1

    print(f"Processing {len(bill_ids)} bill(s) from {bills_dir}")

    extractions: dict[str, dict] = {}
    level1_rows: list[tuple[str, dict]] = []

    for bill_id in bill_ids:
        image = find_bill_image(bills_dir, bill_id)
        data = extract_bill(client, image)
        extractions[bill_id] = data
        level1_rows.append((bill_id, data))
        print(f"  [level1] {bill_id} provider={data.get('provider')} units={data.get('units_consumed')}")

        if args.verify_kesc_0008 and bill_id == "KESC_0008":
            mismatches = compare_to_expected(data)
            if mismatches:
                print("  [verify] KESC_0008 mismatches vs guide §5.7:")
                for m in mismatches:
                    print(f"    - {m}")
            else:
                print("  [verify] KESC_0008 matches guide §5.7 (within ±1)")

    out_dir.mkdir(parents=True, exist_ok=True)
    level1_path = out_dir / "level1.csv"
    write_level1_csv(level1_rows, level1_path)
    print(f"Wrote {level1_path}")

    # Also dump pretty JSON per bill for debugging
    debug_dir = out_dir / "json"
    debug_dir.mkdir(parents=True, exist_ok=True)
    for bill_id, data in extractions.items():
        (debug_dir / f"{bill_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.skip_level2:
        return 0

    level2_rows: list[tuple[str, str, str, str]] = []

    if args.level2_template is not None:
        template_rows = read_level2_template(args.level2_template)
        print(f"Answering {len(template_rows)} Level-2 question row(s) from template")
        for row in template_rows:
            bill_id = row["bill_id"]
            qid = row["question_id"]
            question = row["question"]
            image = find_bill_image(bills_dir, bill_id)
            level1 = extractions.get(bill_id)
            if level1 is None:
                level1 = extract_bill(client, image)
                extractions[bill_id] = level1
            print(f"  [level2] {bill_id} {qid}")
            answer = answer_question(client, image, level1, question)
            level2_rows.append((bill_id, qid, question, answer))
    else:
        # Training dry-run: sample questions from guide §6.2 for each bill
        print(f"No level2 template — using {len(SAMPLE_QUESTIONS)} sample question(s) per bill")
        for bill_id, level1 in extractions.items():
            image = find_bill_image(bills_dir, bill_id)
            for qid, question in SAMPLE_QUESTIONS:
                print(f"  [level2] {bill_id} {qid}")
                answer = answer_question(client, image, level1, question)
                level2_rows.append((bill_id, qid, question, answer))

    level2_path = out_dir / "level2.csv"
    write_level2_csv(level2_rows, level2_path)
    print(f"Wrote {level2_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
