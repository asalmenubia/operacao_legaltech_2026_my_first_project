#!/usr/bin/env python3
"""Create an auditable allocation and credit review for synthetic overpayments."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "cleanned"
OUTPUT = ROOT / "data" / "review" / "overpaid_invoice_review.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def main() -> None:
    invoices = {row["invoice_id"]: row for row in read_rows(DATA / "invoices_clean.csv")}
    payments_by_invoice: dict[str, list[dict[str, str]]] = defaultdict(list)
    for payment in read_rows(DATA / "payments_clean.csv"):
        payments_by_invoice[payment["invoice_id"]].append(payment)

    output_rows: list[dict[str, str]] = []
    for invoice_id, payments in payments_by_invoice.items():
        invoice = invoices[invoice_id]
        invoice_amount = Decimal(invoice["amount"])
        total_received = sum((Decimal(row["amount"]) for row in payments), Decimal("0"))
        if total_received <= invoice_amount:
            continue

        payments.sort(key=lambda row: (date.fromisoformat(row["payment_date"]), int(row["payment_id"])))
        remaining = invoice_amount
        for sequence, payment in enumerate(payments, 1):
            received = Decimal(payment["amount"])
            allocated = min(received, remaining)
            credit = received - allocated
            remaining -= allocated
            if credit and allocated:
                reason = "payment_exceeds_remaining_balance"
            elif credit:
                reason = "invoice_already_fully_allocated"
            else:
                reason = "payment_fully_allocated"
            output_rows.append({
                "invoice_id": invoice_id,
                "client_id": invoice["client_id"],
                "matter_id": invoice["matter_id"],
                "invoice_status_before": invoice["status"],
                "invoice_amount": money(invoice_amount),
                "payment_count": str(len(payments)),
                "total_received": money(total_received),
                "invoice_excess_total": money(total_received - invoice_amount),
                "payment_sequence": str(sequence),
                "payment_id": payment["payment_id"],
                "payment_date": payment["payment_date"],
                "payment_method": payment["method"],
                "payment_reference": payment["reference"],
                "original_payment_amount": money(received),
                "invoice_allocation_amount": money(allocated),
                "client_credit_amount": money(credit),
                "reason_code": reason,
                "recommended_action": "allocate_to_invoice_and_create_client_credit" if credit else "allocate_to_invoice",
                "resolution_status": "modeled_pending_database_load",
                "review_notes": "",
            })

    output_rows.sort(
        key=lambda row: (
            -Decimal(row["invoice_excess_total"]),
            int(row["invoice_id"]),
            int(row["payment_sequence"]),
        )
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)

    credit_total = sum((Decimal(row["client_credit_amount"]) for row in output_rows), Decimal("0"))
    print(f"review_rows={len(output_rows)}")
    print(f"overpaid_invoices={len({row['invoice_id'] for row in output_rows})}")
    print(f"client_credit_total={money(credit_total)}")
    print(OUTPUT)


if __name__ == "__main__":
    main()
