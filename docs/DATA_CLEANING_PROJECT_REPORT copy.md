# LegalTech Data Cleaning Project Report

## 1. Project objective

This report documents the cleaning and validation performed on the LegalTech project's client, consultation, document, inquiry, invoice, matter, payment, and user datasets.

The objective was to create consistent, analysis-ready tables while protecting the original data. Safe formatting problems were corrected automatically. Values requiring business knowledge were preserved and written to separate review files with Boolean issue flags.

## 2. Data-processing approach

The cleaning process followed these principles:

1. Raw source files were never overwritten.
2. Column names and formats were standardized consistently.
3. Identifiers were treated as text rather than quantities.
4. Dates were converted to the unambiguous ISO format `YYYY-MM-DD`.
5. Monetary values were standardized to two decimal places.
6. Categories were converted to lowercase snake case where appropriate.
7. Missing values, duplicates, invalid formats, and logical conflicts were checked.
8. Questionable business values were flagged instead of guessed, deleted, or replaced.
9. Cross-table relationships were validated when the related source table was available.

## 3. Output files

Each dataset produced two files:

- A cleaned table containing normalized source columns.
- A review table containing questionable records and columns beginning with `issue_` that explain why each row needs review.

Recommended project locations:

```text
processed/
├── clients_clean.csv
├── consultations_clean.csv
├── documents_clean.csv
├── inquiries_clean.csv
├── invoices_clean.csv
├── matters_clean.csv
├── payments_clean.csv
└── users_clean.csv

docs/data_review/
├── clients_rows_to_review.csv
├── consultations_rows_to_review.csv
├── documents_rows_to_review.csv
├── inquiries_rows_to_review.csv
├── invoices_rows_to_review.csv
├── matters_rows_to_review.csv
├── payments_rows_to_review.csv
└── users_rows_to_review.csv
```

## 4. Common cleaning operations

### 4.1 Column names

Column names were stripped of unnecessary whitespace and standardized to lowercase snake case.

Examples:

```text
name  -> name
role  -> role
oppened_at -> opened_at
total_fee_agreed  -> total_fee_agreed
power_of_attorney_signed  -> power_of_attorney_signed
```

### 4.2 Whitespace and text

Leading and trailing spaces were removed. Repeated internal whitespace was reduced to one space in descriptive text and names. Categories were normalized to lowercase snake case.

Examples:

```text
on hold -> on_hold
under review -> under_review
not processed -> not_processed
```

### 4.3 Dates

Source dates in month/day/year format were parsed explicitly and exported as ISO dates.

Example:

```text
10/22/2018 -> 2018-10-22
```

Dates were checked for:

- Invalid calendar values
- Future dates
- End dates preceding start dates
- Dates that conflict with related events

### 4.4 Monetary values

Fees and payment amounts were converted to numeric values and exported with two decimal places.

Example:

```text
174.8 -> 174.80
```

Amounts were checked for missing, zero, negative, or unparseable values.

### 4.5 Boolean fields

Boolean-like values were normalized consistently.

Examples:

```text
TRUE -> true
FALSE -> false
yes -> true
no -> false
```

### 4.6 Duplicate handling

Fully identical rows were checked first. Dataset-specific primary identifiers were then checked for repetition. Duplicate records were removed only where the identity rule was clear. Ambiguous repeated values, such as people sharing the same name or document IDs appearing on different records, were retained and flagged.

## 5. Dataset results

### 5.1 Clients

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 26

Cleaning performed:

- Removed the invisible UTF-8 byte order mark from the first header.
- Preserved IDs, document numbers, and telephone numbers as text.
- Normalized names, emails, channels, statuses, and whitespace.
- Standardized creation dates to ISO format.
- Validated 9-digit document IDs, 10-digit telephone numbers, email structure, channels, and statuses.
- Checked duplicates across client ID, document ID, phone, and email.

Results:

- No missing values
- No duplicate identifiers or contact values
- No malformed emails, phones, or document IDs
- No invalid channels or statuses
- 26 records dated after the initial validation date

Future dates were preserved for manual confirmation.

### 5.2 Consultations

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 823

Cleaning performed:

- Standardized scheduled and held dates.
- Standardized fees to two decimal places.
- Converted `TRUE/FALSE` to `true/false`.
- Converted payment statuses to snake case.
- Normalized notes and identifiers.

Review findings:

- 491 consultations have `held_at` before `scheduled_at`.
- 387 scheduled dates were future-dated at validation time.
- 407 held dates were future-dated at validation time.

These dates were retained because the correct event dates cannot be inferred safely.

### 5.3 Documents

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 871

Cleaning performed:

- Standardized receipt dates.
- Converted Boolean values to `true/false`.
- Normalized document types.
- Cleaned corrupted receipt-channel values by extracting the recognized channel.

Examples:

```text
email456 -> email
emailDEF -> email
phoneGHI -> phone
whatsapp789 -> whatsapp
```

Review findings:

- 635 unique document IDs were present across 1,000 rows.
- 365 rows were additional occurrences of an existing document ID.
- 634 rows belonged to a duplicated document-ID group.
- 336 receipt dates were future-dated.
- 225 records were marked both not required and missing.
- 488 records were marked missing despite containing a receipt date.

Repeated document IDs and logical conflicts were preserved for business review.

### 5.4 Inquiries

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 1,000

Cleaning performed:

- Cleaned corrupted origin-channel values.
- Standardized menu options and outcomes to snake case.
- Converted working-hours values from `yes/no` to `true/false`.
- Standardized receipt and first-response dates.
- Normalized response-delay values as whole minutes.

Review findings:

- 520 first responses occur before their inquiries were received.
- 111 inquiry receipt dates were future-dated.
- 111 first-response dates were future-dated.
- All 1,000 response-delay values conflict with the gap between the recorded dates.

Because the source provides dates rather than full timestamps, the response-delay values cannot be reconstructed reliably.

### 5.5 Invoices

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 541

Cleaning performed:

- Standardized issue and due dates.
- Standardized amounts to two decimal places.
- Converted invoice types and statuses to snake case.
- Normalized descriptions and identifiers.
- Validated positive amounts, invoice types, and statuses.

Review findings:

- 508 invoices have a due date before the issue date.
- 45 issue dates were future-dated.
- 35 due dates were future-dated.

No amounts were missing, zero, negative, or malformed.

### 5.6 Matters

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 786

Cleaning performed:

- Corrected malformed and whitespace-padded column names.
- Standardized opening and closing dates.
- Standardized agreed fees to two decimal places.
- Converted Boolean fields to `true/false`.
- Converted matter types, stages, and outcomes to snake case.
- Validated channels, fees, dates, and Boolean fields.

Review findings:

- 485 closing dates occur before opening dates.
- 266 opening dates were future-dated.
- 285 closing dates were future-dated.
- 198 records have an active outcome (`ongoing` or `in_progress`) despite containing a closing date.

These conflicts require confirmation from the business owner.

### 5.7 Payments

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 808

Cleaning performed:

- Standardized payment dates.
- Standardized amounts to two decimal places.
- Normalized payment methods, references, names, and identifiers.
- Validated positive amounts and reference formats.
- Checked every `invoice_id` against the invoice table.
- Compared payment dates with invoice issue dates.
- Compared total payments per invoice with invoice amounts.

Review findings:

- 473 payments occur before their invoices were issued.
- 271 payment dates were future-dated.
- 212 payment rows relate to 105 invoices whose combined payments exceed the invoice amount.
- Every payment referenced an existing invoice.

Financial values were never automatically altered.

### 5.8 Users

**Input records:** 1,000
**Clean records:** 1,000
**Records requiring review:** 627

Cleaning performed:

- Removed trailing spaces from the `name` and `role` headers.
- Normalized whitespace in names.
- Standardized roles to lowercase.
- Validated user ID formats and approved roles.

Review findings:

- All user IDs were complete, unique, and structurally valid.
- All roles were recognized.
- 627 rows share a name with another user record.
- The 1,000 records contain 628 unique names.

Repeated names were preserved because different people can legitimately share a name.

## 6. Summary of review results

| Dataset | Input rows | Clean rows | Review rows | Main review reason |
|---|---:|---:|---:|---|
| Clients | 1,000 | 1,000 | 26 | Future creation dates |
| Consultations | 1,000 | 1,000 | 823 | Held before scheduled and future dates |
| Documents | 1,000 | 1,000 | 871 | Duplicate IDs and contradictory missing status |
| Inquiries | 1,000 | 1,000 | 1,000 | Response dates and delays conflict |
| Invoices | 1,000 | 1,000 | 541 | Due date before issue date |
| Matters | 1,000 | 1,000 | 786 | Closing date and active-status conflicts |
| Payments | 1,000 | 1,000 | 808 | Payment chronology and potential overpayment |
| Users | 1,000 | 1,000 | 627 | Repeated names |

The number of review rows should not be interpreted as the number of errors. One row may have multiple issue flags, and some flags indicate a value requiring confirmation rather than a definite error.

## 7. Cross-table findings

### 7.1 Payments and invoices

All payment invoice IDs matched an invoice. However:

- Some payment dates precede invoice issue dates.
- The combined payments for 105 invoices exceed their invoice amount.

These records require financial reconciliation.

### 7.2 Users and operational staff IDs

The users table uses identifiers formatted like:

```text
98-452-9682
```

The inquiries, consultations, and matters tables use sequential numeric values for `assistant_id`, `lawyer_id`, and `responsible_lawyer_id`. None of these operational staff references currently matches a `user_id` in the users table.

The project therefore needs one of the following:

- A common staff identifier across all tables
- A mapping table connecting numeric operational IDs to user IDs
- Regenerated mock data with consistent foreign keys

Until this is resolved, staff-level joins and lawyer/assistant performance analysis are unreliable.

### 7.3 Other relationships

Additional relationship tests should confirm that:

- Every client reference exists in the clients table.
- Every consultation references a valid client and inquiry.
- Every matter references a valid client and consultation.
- Every document references a valid matter.
- Every invoice references a valid client and matter.

Relationship failures should be recorded in review tables rather than corrected through guessed IDs.

## 8. Data-quality interpretation

The datasets are structurally complete but contain substantial logical inconsistency. Most tables have:

- Complete required fields
- Valid basic formats
- Unique primary identifiers
- Recognized categories

The most significant problems are chronological and relational rather than syntactic. Examples include events occurring before their prerequisite events, future dates, active cases with closing dates, response delays inconsistent with recorded dates, potential invoice overpayment, and incompatible staff identifiers.

This distinction is important: formatting can be repaired automatically, while chronology and relationship problems usually require a business decision or regenerated source data.

## 9. Recommended project workflow

```text
data/raw/           Original immutable source files
        |
        v
src/clean_data.py   Safe normalization and type conversion
        |
        v
processed/          Cleaned analysis-ready tables
        |
        +----------------------+
        v                      v
src/validate_data.py     docs/data_review/
Quality rules            Flagged records
        |
        v
src/transform_data.py
Validated joins and transformations
        |
        v
final/              Final reporting and dashboard tables
```

Only validated records or explicitly approved exceptions should be promoted to the `final/` directory.

## 10. Recommended automated tests

The project should include tests for:

- Required columns
- Primary-key uniqueness
- Missing required values
- Allowed category values
- Date parsing
- Start/end date order
- Positive monetary amounts
- Boolean formats
- Foreign-key relationships
- Payment totals not exceeding invoice totals without an approved exception
- Staff identifiers matching the users table or a mapping table

Examples of suitable test names:

```text
test_required_columns_exist
test_primary_keys_are_unique
test_dates_are_valid
test_end_dates_follow_start_dates
test_foreign_keys_exist
test_payment_totals_do_not_exceed_invoice_amounts
test_staff_ids_map_to_users
```

## 11. Limitations

- Email validation checks structure, not mailbox deliverability.
- Phone and document validation checks formatting, not authenticity.
- Future dates may represent valid planned activity and therefore were not deleted.
- Date-only fields cannot validate minute-level response delays precisely.
- Repeated names do not necessarily indicate duplicate people.
- Duplicate document IDs may require business context before consolidation.
- Overpayment detection compares recorded payment totals with invoice amounts but does not account for credits, refunds, fees, or intentional advances unless separately represented.
- Staff relationships cannot be completed until the identifier mismatch is resolved.
- Cleaning cannot determine the correct replacement for logically inconsistent source values.

## 12. Conclusion

All eight datasets were normalized without modifying their raw sources. The cleaned outputs provide consistent column names, text categories, Boolean values, date formats, and monetary formats. Separate review tables preserve a transparent audit trail for chronological, relational, and business-rule conflicts.

The next priority should be resolving cross-table staff identifiers and reviewing event chronology. Once those decisions are made, approved corrections can be applied and the validated datasets can be merged for final reporting and dashboard use.
