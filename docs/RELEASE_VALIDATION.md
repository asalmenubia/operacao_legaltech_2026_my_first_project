# Release validation

## Scope

This release adds communication adapters, a private queue, the corrected office
policy, bilingual APA-style reports and updated project documentation. It does
not activate provider accounts or send client messages.

## Local checks completed

- 19 unit tests passed: opening/closing boundaries, weekday pre-opening, weekend
  deadlines, both daylight-saving transitions, aware timestamps, automatic reply
  wording, webhook signatures/phone filtering, email loop prevention, provider
  receipt dates, expired free-text windows, approved template payloads, unknown attachment counts and the live-send lock.
- Python source compilation passed.
- The complete Alembic migration chain generated SQL successfully in offline mode.
- Both PDF editions built from the same retained validated synthetic snapshot.
- PDF layout, full author name, mentor acknowledgment, schedule and download copies
  are reviewed before publication.

## Database and provider limits

The existing local PostgreSQL container was initially stopped and was restarted.
Permission to apply the new local migration was declined; revision 0004 has not
been applied by this update to that database. The new migration is included in the
repository. GitHub Actions is configured to test it in a disposable PostgreSQL 18
service, including rollback/reapplication and 14 transactional assertions.

Provider tests use synthetic fixtures and do not contact WhatsApp, IMAP or SMTP.
Live operation requires accounts, credentials, approved templates, a filtered
mailbox, a private host and staff coverage. No production response-target
compliance is claimed. The historical synthetic validation recorded zero critical
findings and 3,000 identity-mapping warnings; historical date-only inquiry data
cannot validate the new response policy.

## GitHub validation and publication

The project was pushed to `main` in commit
`685f41ecc00f44c2a0d587da7af74c4628e4fc88`.
[GitHub validation passed](https://github.com/asalmenubia/operacao_legaltech_2026_my_first_project/actions/runs/35572687542).
The job ran the 19 unit tests, applied all migrations to PostgreSQL 18, passed the
14 transactional assertions, downgraded to revision 0003 and reapplied 0004,
repeated the integration checks, then loaded and validated the synthetic CSVs.
These database tests used the disposable GitHub service, not the user's local
database. The local migration remains unapplied by this update.

The separate [Pages job](https://github.com/asalmenubia/operacao_legaltech_2026_my_first_project/actions/runs/35572687624)
failed at `actions/configure-pages`: GitHub Pages is not enabled/configured for
this repository (HTTP 404). The repository files and both PDFs are uploaded and
downloadable directly from GitHub. No claim is made that the dashboard website is
live. Enable Pages with GitHub Actions as the source, then rerun that job to host
the static site. This setting was not changed as part of the requested Git push.
Repository publication, static hosting and live messaging activation are
separate operations.
