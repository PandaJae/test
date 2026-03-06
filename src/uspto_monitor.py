#!/usr/bin/env python3
"""筛选中国企业 USPTO 宣誓窗口并匹配在美销售线索。"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class UsptoCase:
    registration_number: str
    serial_number: str
    mark_text: str
    owner_name: str
    owner_country: str
    registration_date: date


@dataclass
class SalesSignal:
    source: str
    seller_name: str
    brand_or_mark: str
    url: str
    confidence: float


def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法识别日期格式: {value}")


def years_since(start: date, end: Optional[date] = None) -> float:
    end = end or date.today()
    return (end - start).days / 365.2425


def declaration_window(reg_date: date, today: Optional[date] = None) -> Optional[str]:
    y = years_since(reg_date, today)
    if 5.0 <= y <= 6.0:
        return "year_5_6"
    if 8.0 <= y <= 9.0:
        return "year_8_9"
    return None


def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text.strip() if ch.isalnum())


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def load_uspto_cases(path: Path) -> List[UsptoCase]:
    cases: List[UsptoCase] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "registration_number",
            "serial_number",
            "mark_text",
            "owner_name",
            "owner_country",
            "registration_date",
        }
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"USPTO CSV 缺少字段: {', '.join(sorted(missing))}")

        for row in reader:
            try:
                cases.append(
                    UsptoCase(
                        registration_number=row["registration_number"].strip(),
                        serial_number=row["serial_number"].strip(),
                        mark_text=row["mark_text"].strip(),
                        owner_name=row["owner_name"].strip(),
                        owner_country=row["owner_country"].strip(),
                        registration_date=parse_date(row["registration_date"]),
                    )
                )
            except Exception as exc:
                print(f"[WARN] 跳过无效 USPTO 行: {exc}; row={row}")
    return cases


def load_sales_signals(path: Path) -> List[SalesSignal]:
    signals: List[SalesSignal] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"source", "seller_name", "brand_or_mark", "url"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"销售线索 CSV 缺少字段: {', '.join(sorted(missing))}")

        for row in reader:
            confidence_raw = (row.get("confidence") or "").strip()
            try:
                confidence = float(confidence_raw) if confidence_raw else 0.5
            except ValueError:
                confidence = 0.5

            signals.append(
                SalesSignal(
                    source=row["source"].strip(),
                    seller_name=row["seller_name"].strip(),
                    brand_or_mark=row["brand_or_mark"].strip(),
                    url=row["url"].strip(),
                    confidence=max(0.0, min(1.0, confidence)),
                )
            )
    return signals


def find_sales_match(case: UsptoCase, signals: Iterable[SalesSignal]) -> Tuple[bool, Optional[SalesSignal], float]:
    best_signal: Optional[SalesSignal] = None
    best_score = 0.0

    for sig in signals:
        score_mark = similarity(case.mark_text, sig.brand_or_mark)
        score_owner = similarity(case.owner_name, sig.seller_name)
        weighted = (score_mark * 0.65 + score_owner * 0.35) * sig.confidence
        if weighted > best_score:
            best_score = weighted
            best_signal = sig

    return (best_score >= 0.52), best_signal, best_score


def filter_targets(cases: Iterable[UsptoCase]) -> List[Tuple[UsptoCase, str, float]]:
    targets: List[Tuple[UsptoCase, str, float]] = []
    for case in cases:
        if case.owner_country.upper() not in {"CN", "CHINA", "中国"}:
            continue
        window = declaration_window(case.registration_date)
        if not window:
            continue
        targets.append((case, window, years_since(case.registration_date)))
    return targets


def write_report(output: Path, rows: List[Dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "registration_number",
        "serial_number",
        "mark_text",
        "owner_name",
        "owner_country",
        "registration_date",
        "declaration_window",
        "years_since_registration",
        "sales_match",
        "matched_source",
        "matched_seller",
        "matched_brand",
        "matched_url",
        "match_score",
    ]
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(uspto_csv: Path, sales_csv: Path, output: Path) -> int:
    cases = load_uspto_cases(uspto_csv)
    sales = load_sales_signals(sales_csv)
    targets = filter_targets(cases)

    report_rows: List[Dict[str, str]] = []
    for case, window, years in targets:
        matched, signal, score = find_sales_match(case, sales)
        report_rows.append(
            {
                "registration_number": case.registration_number,
                "serial_number": case.serial_number,
                "mark_text": case.mark_text,
                "owner_name": case.owner_name,
                "owner_country": case.owner_country,
                "registration_date": case.registration_date.isoformat(),
                "declaration_window": window,
                "years_since_registration": f"{years:.2f}",
                "sales_match": "yes" if matched else "no",
                "matched_source": signal.source if signal else "",
                "matched_seller": signal.seller_name if signal else "",
                "matched_brand": signal.brand_or_mark if signal else "",
                "matched_url": signal.url if signal else "",
                "match_score": f"{score:.3f}",
            }
        )

    write_report(output, report_rows)

    print(f"总 USPTO 记录: {len(cases)}")
    print(f"符合中国 + 宣誓窗口: {len(targets)}")
    print(f"输出报告: {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="USPTO 中国企业宣誓窗口监控")
    parser.add_argument("--uspto-csv", type=Path, required=True, help="USPTO 导出的案件 CSV")
    parser.add_argument("--sales-csv", type=Path, required=True, help="在美销售线索 CSV")
    parser.add_argument("--output", type=Path, default=Path("reports/targets.csv"), help="输出报告路径")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run(args.uspto_csv, args.sales_csv, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
