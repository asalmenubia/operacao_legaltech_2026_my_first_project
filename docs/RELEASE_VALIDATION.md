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

## Publication

The project is prepared for the repository's main branch. The static Pages job
requires GitHub Pages to be enabled with GitHub Actions as its source. Repository
publication and live messaging activation are separate operations. CI and push
results will be recorded after publication.
