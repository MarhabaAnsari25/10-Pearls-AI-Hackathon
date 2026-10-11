"""CSV template read/write helpers (guide §7.1–7.2)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def bill_id_from_path(path: Path) -> str:
    return path.stem


def list_bill_images(bills_dir: Path) -> list[Path]:
    paths = [
        p
        for p in sorted(bills_dir.iterdir())
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    return paths


def write_level1_csv(rows: list[tuple[str, dict[str, Any]]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["bill_id", "json"], quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for bill_id, obj in rows:
            # Keep JSON on one line; csv module doubles quotes inside cells
            writer.writerow(
                {
                    "bill_id": bill_id,
                    "json": json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                }
            )


def write_level2_csv(
    rows: list[tuple[str, str, str, str]],
    out_path: Path,
) -> None:
    """rows: (bill_id, question_id, question, answer)"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["bill_id", "question_id", "question", "answer"],
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for bill_id, qid, question, answer in rows:
            writer.writerow(
                {
                    "bill_id": bill_id,
                    "question_id": qid,
                    "question": question,
                    "answer": answer,
                }
            )


def read_level1_template(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "bill_id" not in reader.fieldnames:
            raise ValueError(f"Invalid level1 template: {path}")
        return [row["bill_id"] for row in reader]


def read_level2_template(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"bill_id", "question_id", "question", "answer"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"Invalid level2 template: {path}")
        return [
            {
                "bill_id": row["bill_id"],
                "question_id": row["question_id"],
                "question": row["question"],
                "answer": row.get("answer") or "",
            }
            for row in reader
        ]


def find_bill_image(bills_dir: Path, bill_id: str) -> Path:
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".PNG", ".JPG", ".JPEG"):
        candidate = bills_dir / f"{bill_id}{ext}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No image found for bill_id={bill_id} in {bills_dir}")
