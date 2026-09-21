# Data Governance Guide

## Operacao LegalTech

**Document status:** Educational example
**Project status:** In development
**Data classification:** Synthetic data only
**Review frequency:** At each major project milestone

## 1. Purpose

This guide defines example rules for creating, maintaining, accessing, validating, and protecting data in the Operacao LegalTech project.

The project simulates the data operations of a small law firm. Its purpose is to demonstrate good data-management practices and support reliable analysis in Power BI.

This document is designed for an educational project and is not legal advice. Before the project is used with real client or case information, its policies must be reviewed and approved by the law firm, its data-protection adviser, and other qualified professionals as required.

## 2. Scope

This guide applies to the following project tables:

- `Clients`
- `Inquiries`
- `Consultations`
- `Matters`
- `Matter_updates`
- `Documents`
- `Invoices`
- `Payments`
- `Users`

It also applies to the files, SQL scripts, Python code, notebooks, data model, and Power BI dashboard used to process or present the data.

## 3. Governance Principles

The project follows these principles:

1. **Purpose limitation:** Collect and use only the information required for a defined operational or analytical purpose.
2. **Data minimization:** Avoid unnecessary personal, financial, or legal details.
3. **Accuracy:** Validate data before it is used for reporting or decision-making.
4. **Consistency:** Use standard names, formats, controlled values, and identifiers.
5. **Traceability:** Keep enough information to understand where data came from and how it was transformed.
6. **Confidentiality:** Restrict sensitive information to authorized users.
7. **Accountability:** Assign responsibility for data creation, review, correction, and approval.
8. **Security by design:** Protect data throughout collection, storage, analysis, sharing, backup, and deletion.

## 4. Current Educational-Project Rules

- Only synthetic data generated for testing and learning may be stored in the repository.
- Synthetic records must not reproduce identifiable real clients, employees, cases, documents, or transactions.
- Real names, identification numbers, phone numbers, email addresses, legal documents, case details, payment references, passwords, tokens, and credentials must not be committed to Git.
- Public examples, screenshots, dashboard exports, and demonstrations must contain synthetic or properly anonymized information.
- The repository may be public only while all included data is demonstrably synthetic and no secrets are present.
- Files received from external sources must be reviewed before they are added to the repository.

## 5. Roles and Responsibilities

The following roles are examples for a small law firm. In this educational project, the project owner may perform all roles.

| Role | Example responsibilities |
|---|---|
| **Project owner / Data owner** | Approves definitions, access rules, KPIs, major corrections, and publication of project outputs. |
| **Data steward** | Maintains the data dictionary, controlled values, validation rules, and data-quality issue log. |
| **Administrator** | Manages users, permissions, backups, configuration, and recovery procedures. |
| **Assistant / Receptionist** | Records inquiries, client contact information, consultation bookings, and received documents. |
| **Lawyer** | Reviews consultation outcomes, matter stages, legal assignments, and matter updates. |
| **Finance user** | Creates invoices, records payments, reconciles balances, and investigates financial discrepancies. |
| **Analyst** | Cleans and models approved data, builds KPIs, documents transformations, and validates dashboard results. |

No user should approve their own access or have more permissions than required for their responsibilities.

## 6. Example Access-Control Matrix

Access should follow the principle of least privilege.

| Data area | Assistant | Lawyer | Finance | Administrator | Analyst |
|---|---:|---:|---:|---:|---:|
| Clients and inquiries | Create/update | View | Limited view | Manage | Approved analytical view |
| Consultations | Create/update schedule | Review/update outcome | View fee status | Manage | Approved analytical view |
| Matters and updates | Limited update | Create/update assigned matters | Limited view | Manage | Approved analytical view |
| Documents | Record receipt status | View assigned matters | No access unless required | Manage | Metadata only |
| Invoices and payments | Limited view | Limited view | Create/update | Manage | Approved analytical view |
| Users and permissions | No access | No access | No access | Manage | No access |
| Power BI dashboard | Operational pages | Assigned-matter pages | Financial pages | Full authorized view | Develop and validate |

For a real system, row-level security should restrict lawyers and assistants to the clients or matters they are authorized to handle.

## 7. Data Classification

| Classification | Examples | Example handling |
|---|---|---|
| **Public** | Approved project description and fully synthetic screenshots | May be published after review. |
| **Internal** | Data model, validation results, internal procedures | Share only with project participants. |
| **Confidential** | Client contact details, staff information, invoices, payment details | Restrict access; do not place in a public repository. |
| **Highly confidential** | Legal advice, evidence, case documents, identity documents, credentials | Store only in an approved secure system with strict access controls. |

All current project records are synthetic, but their fields should still be handled as if they represented confidential data. This encourages safe habits and makes future migration easier.

## 8. Data Entry and Ownership Rules

### Clients

- Create one client record per person or organization.
- Search for an existing client before creating a new record.
- Require `client_id`, `full_name`, `created_at`, and `status`.
- Store contact information only when needed.
- Convert email addresses to lowercase and use a consistent international telephone format.

### Inquiries

- Record the origin channel and received time when an inquiry arrives.
- Link the inquiry to a known client when possible.
- Calculate `response_delay_minutes` from `received_at` and `first_response_at`; do not enter it manually.
- Record the assistant responsible for the first response.

### Consultations

- Link every consultation to an existing client.
- Assign only a user whose role is `lawyer` as the consultation lawyer.
- Do not enter `held_at` before the consultation occurs.
- Leave `case_accepted` blank until the lawyer makes a decision.
- Keep notes brief and avoid unnecessary confidential information.

### Matters and matter updates

- Link every matter to one existing client.
- Use an approved matter type and stage.
- Assign a responsible lawyer before substantive legal work begins.
- Record stage changes in `Matter_updates` rather than overwriting history without a trace.
- Require a closure date and final outcome when a matter is closed.

### Documents

- Store document metadata in the analytical model, not document contents.
- Link each document record to an existing matter.
- Mark `is_missing` as true only when a required document has not been received.
- Prefer calculating missing-document status automatically.
- Real files would require a secure document-management system outside a public Git repository.

### Invoices and payments

- Link every invoice to an existing client and, where applicable, a matter or consultation.
- Require positive invoice and payment amounts.
- Link every payment to an existing invoice.
- Reconcile total payments against the invoice amount.
- Require a transaction reference for non-cash methods when applicable.
- Record which authorized user entered or approved the payment.

### Users

- Create one account per staff member; shared accounts are not permitted.
- Assign only approved roles.
- Disable access promptly when a user leaves the organization or changes responsibilities.
- Never store passwords or authentication secrets in project tables or Git.

## 9. Naming and Formatting Standards

- Use English `snake_case` for table fields, for example `client_id` and `received_at`.
- Use stable singular identifiers ending in `_id`.
- Use ISO date formats when exporting text data: `YYYY-MM-DD` for dates and ISO 8601 for date-time values.
- Store Boolean values consistently as `true` or `false`.
- Store monetary values as numeric decimals with two decimal places and document the currency separately.
- Use approved controlled values for roles, channels, statuses, matter types, stages, document types, and payment methods.
- Correct spelling and naming inconsistencies before loading data into the analytical model.
- Do not change field definitions without updating the data dictionary and affected tests, SQL, Python, and Power BI logic.

## 10. Primary and Foreign Keys

- Every table must have a documented primary key.
- Primary keys must be unique, non-empty, stable, and generated consistently.
- Foreign keys must reference an existing parent record unless the data dictionary explicitly permits a temporary null value.
- Deleting a parent record must not leave orphan inquiries, consultations, matters, invoices, payments, documents, or updates.
- Records referenced by transactions or legal work should normally be deactivated or archived instead of physically deleted.

## 11. Data-Quality Controls

Quality checks should run after each import or transformation and before dashboard refresh or publication.

### Required checks

- Primary keys contain no nulls or duplicates.
- Foreign keys match existing parent records.
- Required fields are populated.
- Dates are valid and follow logical order.
- Monetary amounts are numeric and meet the documented rules.
- Statuses and categories use permitted values.
- Emails, phone numbers, and identifiers follow the agreed format.
- Closed matters have a closure date and final outcome.
- Held consultations are not dated before their scheduled time.
- Payments reference valid invoices.
- Required but unreceived documents are identified consistently.
- Power BI totals reconcile with the processed source tables.

### Quality thresholds

For this educational project:

- Primary-key uniqueness: **100%**
- Required primary and foreign keys: **100% valid**, except documented optional relationships
- Permitted-value compliance: **100%**
- Dashboard reconciliation for key totals: **100%**
- Missing optional values: measured and documented, not silently replaced

Any failed critical check must block publication of the affected dataset or dashboard refresh until it is corrected or formally accepted as a known issue.

## 12. Data-Quality Issue Process

1. Detect the issue through a test, reconciliation, or user report.
2. Record the affected table, field, record count, date, and impact.
3. Preserve the original raw data.
4. Identify whether the cause is source entry, transformation logic, relationship design, or reporting logic.
5. Correct the issue in the appropriate source or transformation step.
6. Rerun all relevant validation tests.
7. Document the resolution and any preventive rule added.
8. Refresh Power BI only after the corrected outputs pass validation.

Corrections must not be hidden through manual dashboard adjustments.

## 13. Data Lineage and Change Management

The expected lineage is:

```text
Synthetic source data
        ↓
Raw files (preserved without manual alteration)
        ↓
Python/SQL cleaning and validation
        ↓
Processed tables
        ↓
Power BI data model and measures
        ↓
Dashboard and final project outputs
```

For each important transformation:

- keep source and processed data separate;
- document the input, output, purpose, and responsible code file;
- use version control for SQL, Python, documentation, and model definitions where possible;
- use meaningful Git commit messages;
- review changes to keys, relationships, business rules, or KPI definitions before merging;
- update the README, data dictionary, tests, and dashboard guide when the model changes.

## 14. Repository and Secret Management

The `.gitignore` file should exclude at least:

- environment files such as `.env`;
- credentials, tokens, and private keys;
- local virtual environments;
- temporary files and caches;
- operating-system files such as `.DS_Store`;
- real or confidential source datasets;
- local Power BI temporary files;
- exports containing sensitive information.

Before every public push:

1. Review `git status` and the staged changes.
2. Confirm all datasets are synthetic or approved for publication.
3. Scan for secrets and personal information.
4. Confirm screenshots and dashboard exports contain no real data.
5. Verify that ignored files have not already been tracked.

Removing a secret from the latest version does not remove it from Git history. If a real credential is committed, it must be revoked immediately and the incident handled appropriately.

## 15. Backup and Recovery

For the educational project:

- Use Git for versioned code and documentation.
- Keep a separate backup of source datasets, Power BI files, and other binary deliverables.
- Do not rely on a local computer as the only copy.
- Test that important files can be restored before final submission.

For a real law firm, backup frequency, encryption, recovery-time objectives, storage location, and access must be defined and tested by the organization.

## 16. Retention and Deletion

This educational project does not define legal retention periods because it uses synthetic data.

For real operations:

- retention periods must be approved for client, matter, document, billing, payment, audit, and backup records;
- legal, contractual, regulatory, and professional obligations must be considered;
- deletion must be authorized and logged;
- records subject to a legal hold must not be deleted;
- deletion should cover active storage, exports, and backups according to the approved procedure.

No real-data retention period should be guessed or adopted from this example without qualified review.

## 17. Power BI Governance

- Use only validated processed tables as dashboard sources.
- Document every KPI name, purpose, formula, source table, filters, and owner.
- Reconcile important measures with source totals before publication.
- Apply role-level or row-level access if real data is introduced.
- Limit export permissions for confidential data.
- Display the last refresh date on the dashboard.
- Record refresh failures and investigate them before relying on the results.
- Obtain approval before changing definitions used in management reporting.

During development, refreshes may be manual. A real deployment should define an approved refresh frequency based on operational need and source-system availability.

## 18. Incident Response

If information is accidentally exposed, altered, lost, or accessed without authorization:

1. Stop further sharing or processing where safe to do so.
2. Preserve evidence and do not conceal the event.
3. Notify the project owner or designated responsible person.
4. Revoke exposed credentials and restrict affected access.
5. Identify the data, users, systems, and time period involved.
6. Restore trusted data where required.
7. Document the cause, impact, response, and preventive actions.
8. For real data, follow the organization's approved legal and regulatory notification process.

## 19. Review and Approval

This guide should be reviewed when:

- a new table, field, data source, or dashboard page is introduced;
- a key, relationship, permitted value, or KPI definition changes;
- data access or user responsibilities change;
- the repository changes from private to public;
- the project moves from synthetic to real data;
- a data-quality or security incident occurs;
- the project reaches a major milestone or release.

## 20. Pre-Release Checklist

- [ ] All committed datasets are synthetic or approved for publication.
- [ ] No secrets, credentials, or real personal information are present.
- [ ] Primary-key and foreign-key tests pass.
- [ ] Required fields and permitted values pass validation.
- [ ] Processed data can be traced to its source and transformation.
- [ ] Power BI totals reconcile with processed tables.
- [ ] KPI definitions are documented.
- [ ] The data dictionary matches the implemented model.
- [ ] README and workflow documentation are current.
- [ ] Dashboard screenshots contain no sensitive information.
- [ ] Final files are backed up and can be restored.

## 21. Policies Required Before Using Real Data

The following items remain **to be confirmed by the organization** before any real client information is introduced:

- applicable privacy and professional rules;
- named data owner, system owner, and security contact;
- detailed user permissions and approval workflow;
- approved systems for client and legal-document storage;
- encryption and authentication requirements;
- retention schedules and secure-deletion procedures;
- backup frequency and recovery objectives;
- incident-notification and breach-response procedures;
- Power BI sharing, export, and row-level security rules;
- third-party vendor and cloud-service approval.


## Communication automation update (September 2026)

The corrected office policy is Monday-Friday, 09:00-18:00. After-hours contacts
are due a human reply by 10:00 on the next working day, with Europe/Lisbon as a
configurable default. A weekday pre-opening contact is due at 10:00 that day.
No holiday calendar or numerical in-hours response target is assumed.

Private requests and queued replies are stored in the `communications` schema,
not exported to the static dashboard. Automated acknowledgments and approved
re-engagement templates do not populate the human-response timestamp. The
implemented timestamp measures provider acceptance, not delivery or reading.
The office's staff own queue coverage; the technical operator owns availability,
provider credentials and failed-send reconciliation. Retention and mailbox access
must be configured before production activation.

Email intake reads headers only and leaves attachments for reviewed handling in
the protected mailbox. The channel integration does not automatically approve
client identity, document completeness or matter opening. See
[communication automation](COMMUNICATION_AUTOMATION.md) and
[release validation](RELEASE_VALIDATION.md) for implementation and test boundaries.
