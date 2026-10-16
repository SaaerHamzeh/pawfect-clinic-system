# AGENTS.md — Vet Clinic Management System

## 1. Before Working

Before implementing or modifying anything:

1. Read `docs/00-project-overview.md`.
2. Read `docs/01-requirements.md`.
3. Check the existing project structure before creating new files.
4. Follow the documented requirements and architecture.

These documents are the project's source of truth.

---

## 2. Core Rules

### Offline First

The application must work completely without Internet access.

Do not introduce:

* Cloud services
* External APIs
* Online authentication
* Cloud databases
* Cloud file storage
* External notification services

The application must be accessible from devices connected to the same LAN.

---

### Keep the Architecture Simple

This is a small internal clinic system.

Do not introduce unnecessary:

* Frameworks
* Services
* Infrastructure
* Abstractions
* Dependencies

Do not add React, Next.js, Redis, Celery, Nginx, or cloud services unless the requirements are explicitly changed and the technology is justified.

---

## 3. Requirements Are the Source of Truth

Do not invent business rules.

If a requirement is ambiguous:

1. Identify the ambiguity.
2. Do not silently choose a business rule.
3. Ask for clarification before implementing behavior that depends on it.

Do not add features that are outside the documented scope.

---

## 4. Code Organization

Keep domains logically separated.

Prefer clear Django applications based on business domains, such as:

```text
accounts
owners
animals
appointments
reminders
clinical
vaccinations
reports
audit
backups
```

Do not put unrelated domain logic into a single application.

Keep business logic out of templates.

Avoid putting complex business logic directly inside views.

Use appropriate service/query layers when they provide real value.

Do not create abstractions merely for the sake of abstraction.

---

## 5. Database Rules

PostgreSQL is the project's database.

Database integrity must be enforced as close to the database/domain layer as reasonably possible.

Important business constraints must not rely only on frontend validation.

For example:

* A Vet must not have overlapping appointments.
* Animal names are not unique.
* An animal has one primary owner.
* Deleted records that support restoration must remain recoverable.

---

## 6. Permissions

Permissions are assigned individually by the Admin.

Do not assume that a user's role alone determines access.

When implementing protected functionality:

* Check the appropriate permission.
* Do not rely only on hiding a button in the UI.
* Backend authorization is mandatory.

Delete and Restore are separate permissions.

---

## 7. Files

Uploaded attachments are stored locally.

Maximum attachment size:

```text
15 MB
```

Any file type may be accepted according to the requirements, but uploaded files must still be handled securely.

Do not store uploaded files in the database unless there is an explicit requirement to do so.

---

## 8. Audit Logs

Important user actions must be auditable.

When implementing a feature that changes important persistent data, consider whether the action must produce an audit record.

Audit logs must identify at minimum:

* User
* Action
* Affected resource
* Resource identifier
* Timestamp

Do not rely on frontend-only logging.

---

## 9. Deletion

Use soft deletion where the requirements specify recoverable deletion.

Do not permanently destroy recoverable records when the user performs a normal delete operation.

Restoration must require the appropriate permission.

---

## 10. UI Development

The UI is a server-rendered Django application.

Preferred frontend technologies:

* Django Templates
* HTMX
* Alpine.js
* Tailwind CSS
* FullCalendar where calendar functionality is required

Do not turn the project into a SPA without an explicit architectural decision.

UI behavior must respect backend permissions.

---

## 11. Changes

Before making a significant change:

1. Understand the existing implementation.
2. Identify affected domains.
3. Make the smallest appropriate change.
4. Avoid unrelated refactoring.
5. Run relevant tests.
6. Verify that existing behavior has not been broken.

Do not rewrite working code without a clear reason.

---

## 12. Testing

New business behavior should have appropriate tests.

Prioritize tests for:

* Business rules
* Permissions
* Appointment conflicts
* Soft deletion and restoration
* Vaccination due-date calculation
* Reminder-to-appointment conversion
* File-size validation
* Backup behavior
* Important audit logging

Do not consider a feature complete merely because the UI works manually.

---

## 13. Communication

Before implementing a large task, briefly explain:

* What will change
* Which files/domains are affected
* Any assumptions
* Any unresolved requirement

For small, obvious tasks, implementation can proceed directly.

Never hide an important assumption from the developer.

---

## 14. Definition of Done

A feature is considered complete only when:

* The requirements are satisfied.
* Backend authorization is implemented.
* Relevant business rules are enforced.
* Appropriate tests exist.
* The UI behaves correctly.
* No unrelated functionality is broken.
* The implementation does not introduce unnecessary dependencies or infrastructure.
