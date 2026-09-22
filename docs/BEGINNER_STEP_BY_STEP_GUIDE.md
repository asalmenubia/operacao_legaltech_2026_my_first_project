# Operacao LegalTech: step-by-step guide

Author: **Nubia Aparecida Silva Almeida**
Special thanks to **Adwiteey Mauriya** for his support during the project.

## 1. Open the finished reports

- [Português europeu](../site/reports/operacao_legaltech_dissertation_pt-PT.pdf)
- [English](../site/reports/operacao_legaltech_dissertation_en.pdf)

The reports use the same synthetic snapshot and explain the implemented features
and remaining deployment requirements. You do not need PostgreSQL to read them.

## 2. Understand the two data paths

The analytics path is:

```text
Eight synthetic CSVs -> cleaning -> staging -> core -> analytics views
                     -> static Plotly dashboard -> bilingual PDF reports
```

The private communications path is:

```text
WhatsApp / email -> private request record -> office deadline + outbox
                -> worker -> provider acceptance or review -> staff queue
```

The public site never reads private message records. The office works
Monday-Friday, 09:00-18:00; contacts received while closed are due a human reply
by 10:00 on the next working day. An 08:30 weekday contact is due at 10:00 that
same day. The default time zone is Europe/Lisbon and no holiday calendar is
configured. An automatic reply is not a human response.

## 3. Prepare the local environment

Install UV and ensure PostgreSQL is running. From the repository root:

```sh
uv sync
```

Copy `.env.example` to `.env` and enter your own database settings locally. Never
commit `.env`. The synthetic CSV files are already in `data/cleaned/` and their
originals are in `data/raw/`; no replacement with real client data is needed.

## 4. Update the database without resetting it

```sh
uv run python -m alembic upgrade head
uv run python -m alembic current
```

Revision `0004` adds the private communications schema. The existing core,
staging and analytics data remain intact. If PostgreSQL is stopped, start your
existing service first. If a migration fails, resolve the error before loading.
`src.reset_database` is only for a deliberate destructive development rebuild.

## 5. Load and validate the synthetic records

```sh
uv run python -m src.load_csvs
uv run python -m src.validate_database
```

The loader skips unchanged files by content hash. Critical findings must be
resolved before building a dashboard. Historical staff-mapping warnings are
recorded; do not invent identities to eliminate them. Review
`output/validation/database_validation.json` locally.

## 6. Build and preview the dashboard

```sh
uv run python -m src.build_dashboard
uv run python -m http.server 8765 --directory site
```

Open `http://localhost:8765`. The site shows the snapshot timestamp and has filters
for month, channel, matter type, stage, outcome and responsible-person label.
Check totals and filters. Response delays in historical date-only data do not
prove compliance with the new office-hours target.

## 7. Run the tests

```sh
uv run python -m unittest discover -s tests -v
```

These tests do not contact providers. The GitHub validation workflow also creates
an isolated PostgreSQL service to test migration, rollback, outbox behavior and
CSV validation. Do not point integration tests at operational data.

## 8. Rebuild both dissertations

```sh
uv run python -m src.build_dissertation_report
```

The sources are `docs/dissertation/en.json` and `pt-PT.json`. Keep both editions
consistent when changing a definition. Output goes to `output/pdf/`, with copies
in `site/reports/` and the project root. The original report filename is an
English alias so existing links still work. Inspect the rendered pages after any
content change. Times New Roman or Liberation Serif is required.

## 9. Configure messaging separately

Follow [COMMUNICATION_AUTOMATION.md](COMMUNICATION_AUTOMATION.md). You need a Meta
business account and number, a supported API version, a filtered email folder,
TLS mailbox credentials, a private HTTPS service and supervised workers.
`COMMUNICATIONS_LIVE_SEND=false` prevents sending until setup is complete.

Staff can inspect the queue using:

```sh
uv run python -m src.communications queue
```

Attachments remain in the mailbox for human review. The service does not
approve legal documents or open matters automatically.

## 10. Publish reviewed files

The GitHub repository contains the synthetic project and both reports. Keep
`.env`, temporary files, virtual environments and real messages out of Git.
GitHub Pages publishes the static `site/` folder when the repository's Pages
source is set to GitHub Actions. It does not host the private communication
service. See [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md) for current evidence.
