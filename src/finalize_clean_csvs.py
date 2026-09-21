#!/usr/bin/env python3
"""Apply deterministic business-rule corrections to the cleaned synthetic CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path


DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y")


def parse_date(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date: {value!r}")


def format_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header")
        return reader.fieldnames, list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def set_value(row: dict[str, str], column: str, value: str, changes: Counter[str]) -> None:
    if row[column] != value:
        row[column] = value
        changes[column] += 1


def clean_clients(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    status_map = {
        "consultation_only": "former_client",
        "inactive_account": "churned",
        "prospect": "potential_lead",
    }
    for row in rows:
        status = status_map.get(token(row["status"]), token(row["status"]))
        set_value(row, "status", status, changes)
        set_value(row, "preferred_channel", token(row["preferred_channel"]), changes)
        set_value(row, "email", row["email"].strip().lower(), changes)
        phone = row["phone"].strip()
        if phone:
            phone = "+" + re.sub(r"\D", "", phone).lstrip("0")
        set_value(row, "phone", phone, changes)
        created = min(parse_date(row["created_at"]), today)
        set_value(row, "created_at", format_date(created), changes)


def clean_inquiries(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    menu_map = {"scheduled": "schedule", "delayed": "pending"}
    outcome_map = {"scheduled": "schedule", "completed": "approved"}
    for row in rows:
        received = min(parse_date(row["received_at"]), today)
        response = parse_date(row["first_response_at"])
        if response:
            response = min(response, today)
            response = max(response, received)
        set_value(row, "received_at", format_date(received), changes)
        set_value(row, "first_response_at", format_date(response), changes)
        delay = str((response - received).days * 1440) if response else ""
        set_value(row, "response_delay_minutes", delay, changes)
        menu = token(row["menu_option"])
        set_value(row, "menu_option", menu_map.get(menu, menu), changes)
        outcome = token(row["outcome"])
        set_value(row, "outcome", outcome_map.get(outcome, outcome), changes)


def clean_consultations(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    status_map = {"paid": "completed", "delivered": "completed"}
    for row in rows:
        scheduled = parse_date(row["scheduled_at"])
        held = parse_date(row["held_at"])
        if held and held > today:
            held = None
        if held and held < scheduled:
            held = scheduled if scheduled <= today else None
        set_value(row, "scheduled_at", format_date(scheduled), changes)
        set_value(row, "held_at", format_date(held), changes)
        if not held:
            set_value(row, "case_accepted", "", changes)
        status = token(row["paid_status"])
        set_value(row, "paid_status", status_map.get(status, status), changes)


def clean_matters(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    type_map = {"consultation_only_service": "consultation"}
    stage_map = {
        "completed": "closed",
        "finalized": "closed",
        "in_progress": "in_process",
        "on_hold": "pending",
        "pending_approval": "pending",
        "pending_review": "under_review",
        "reviewing": "under_review",
    }
    final_outcomes = {
        "office_declined", "completed", "cancelled", "settled",
        "client_withdrawal", "resolved", "lost_case",
    }
    for row in rows:
        matter_type = token(row["matter_type"])
        set_value(row, "matter_type", type_map.get(matter_type, matter_type), changes)
        set_value(row, "origin_channel", token(row["origin_channel"]), changes)
        outcome = token(row["outcome"])
        if outcome == "client_withdrew":
            outcome = "client_withdrawal"
        set_value(row, "outcome", outcome, changes)
        opened = min(parse_date(row["opened_at"]), today)
        closed = parse_date(row["closed_at"])
        stage = stage_map.get(token(row["current_stage"]), token(row["current_stage"]))
        if outcome in final_outcomes:
            stage = "closed"
            closed = min(closed or today, today)
            closed = max(closed, opened)
        else:
            closed = None
            if stage == "closed":
                stage = "in_process"
        set_value(row, "opened_at", format_date(opened), changes)
        set_value(row, "closed_at", format_date(closed), changes)
        set_value(row, "current_stage", stage, changes)


def clean_documents(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    for row in rows:
        received = parse_date(row["received_at"])
        if received and received > today:
            received = None
        set_value(row, "received_at", format_date(received), changes)
        if not received:
            set_value(row, "received_via", "", changes)
        else:
            set_value(row, "received_via", token(row["received_via"]), changes)
        required = token(row["is_required"]) in {"true", "yes", "1"}
        missing = required and received is None
        set_value(row, "is_required", str(required).lower(), changes)
        set_value(row, "is_missing", str(missing).lower(), changes)
        set_value(row, "document_type", token(row["document_type"]), changes)


def clean_invoices(rows: list[dict[str, str]], today: date, changes: Counter[str]) -> None:
    for row in rows:
        issued = min(parse_date(row["issued_at"]), today)
        due = max(parse_date(row["due_date"]), issued)
        set_value(row, "issued_at", format_date(issued), changes)
        set_value(row, "due_date", format_date(due), changes)
        set_value(row, "invoice_type", token(row["invoice_type"]), changes)
        set_value(row, "status", token(row["status"]), changes)


def clean_payments(
    rows: list[dict[str, str]],
    today: date,
    invoice_dates: dict[str, date],
    changes: Counter[str],
) -> None:
    method_map = {"stripe": "card"}
    for row in rows:
        paid = min(parse_date(row["payment_date"]), today)
        issued = invoice_dates[row["invoice_id"]]
        paid = max(paid, issued)
        set_value(row, "payment_date", format_date(paid), changes)
        method = token(row["method"])
        set_value(row, "method", method_map.get(method, method), changes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/cleaned"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()

    files = {
        "clients": "clients_cleaned.csv",
        "users": "users_clean.csv",
        "inquiries": "inquiries_clean.csv",
        "consultations": "consultations_clean.csv",
        "matters": "matters_clean.csv",
        "documents": "documents_clean.csv",
        "invoices": "invoices_clean.csv",
        "payments": "payments_clean.csv",
    }
    copied_clients = args.data_dir / "clients_cleaned copy.csv"
    canonical_clients = args.data_dir / files["clients"]
    if copied_clients.exists() and not canonical_clients.exists():
        copied_clients.rename(canonical_clients)

    loaded: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for table, filename in files.items():
        loaded[table] = read_csv(args.data_dir / filename)

    audit: dict[str, object] = {"as_of": args.as_of.isoformat(), "tables": {}}
    cleaners = {
        "clients": clean_clients,
        "inquiries": clean_inquiries,
        "consultations": clean_consultations,
        "matters": clean_matters,
        "documents": clean_documents,
        "invoices": clean_invoices,
    }
    for table in ("clients", "inquiries", "consultations", "matters", "documents", "invoices"):
        fields, rows = loaded[table]
        changes: Counter[str] = Counter()
        cleaners[table](rows, args.as_of, changes)
        write_csv(args.data_dir / files[table], fields, rows)
        audit["tables"][table] = {"rows": len(rows), "changed_cells": dict(changes)}

    invoice_dates = {
        row["invoice_id"]: parse_date(row["issued_at"])
        for row in loaded["invoices"][1]
    }
    fields, rows = loaded["payments"]
    payment_changes: Counter[str] = Counter()
    clean_payments(rows, args.as_of, invoice_dates, payment_changes)
    write_csv(args.data_dir / files["payments"], fields, rows)
    audit["tables"]["payments"] = {"rows": len(rows), "changed_cells": dict(payment_changes)}

    user_fields, user_rows = loaded["users"]
    write_csv(args.data_dir / files["users"], user_fields, user_rows)
    audit["tables"]["users"] = {"rows": len(user_rows), "changed_cells": {}}

    audit_path = args.data_dir / "final_cleaning_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
