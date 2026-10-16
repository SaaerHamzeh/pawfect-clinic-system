# Vet Clinic Management System

## 1. Project Purpose

The Vet Clinic Management System is an internal veterinary clinic management application designed to organize and manage the clinic's daily operations and records.

The system focuses on:

* Owners management
* Animals management
* Appointments
* Reminders
* Clinical records
* Vaccination records
* Reports and Excel exports
* User accounts and permissions
* Audit logs
* Local backups

The system is **not an accounting, billing, inventory, or customer-facing booking system**.

---

## 2. Deployment Environment

The application must work **completely offline** after deployment.

It must not depend on:

* Internet access
* Cloud services
* External APIs
* External notification services
* Cloud storage

The application is deployed inside a single veterinary clinic and accessed through a **Local Area Network (LAN)**.

Multiple computers/devices on the same LAN must be able to access the application through a web browser.

Example:

```text
Clinic LAN
    │
    ├── Computer 1
    ├── Computer 2
    ├── Computer 3
    └── Computer 4
            │
            ▼
     Local Application Server
            │
       ┌────┴────┐
       │         │
   PostgreSQL  Local Files
```

The system is intended for approximately **3–4 concurrent users**.

---

## 3. Application Architecture

The application is a **LAN-based web application**.

Users access the system through a browser.

The initial architecture is a **Django monolith**.

The project should prioritize:

1. Simplicity
2. Reliability
3. Maintainability
4. Offline operation
5. LAN accessibility
6. Data integrity
7. Clear separation of domains

The project should avoid unnecessary infrastructure and overengineering.

---

## 4. Main User Types

The system has three main user types:

### Admin / Manager

Has full administrative control and creates Staff and Vet accounts.

The Admin can define permissions individually for each user.

### Staff

Primarily handles:

* Appointments
* Owners
* Animals
* Reminders

The exact permissions granted to each Staff user are determined individually by the Admin.

### Vet / Doctor

Primarily handles:

* Clinical records
* Vaccinations

The exact permissions granted to each Vet user are determined individually by the Admin.

---

## 5. Main Domains

The system is divided into the following domains:

```text
Accounts
Owners
Animals
Appointments
Reminders
Clinical Records
Vaccinations
Reports
Audit Logs
Backups
```

Each domain should remain logically separated in the codebase.

---

## 6. Core Business Characteristics

### Owners

* One owner may have multiple animals.
* Each animal has exactly one primary owner.
* Owner names do not need to be unique.

### Animals

Animals contain information such as:

* Name
* Species
* Breed
* Gender
* Birth date/age
* Weight
* Color
* Optional image

Animal names are **not unique identifiers**.

There is no microchip number in the system.

### Appointments

Appointments:

* Are created by staff.
* Are associated with an animal.
* Are assigned to a Vet.
* Are associated with the Staff member who created them.
* Have a selectable duration.
* Must not overlap for the same Vet.

### Reminders

Reminders:

* Belong to an animal.
* Have a due date.
* Have a reason/note.
* Can be converted into appointments.
* Change state after conversion.

### Clinical Records

Clinical records contain medical information related to visits.

A clinical visit may:

* Be linked to an existing appointment.
* Be created as a walk-in without a previous appointment.

Clinical records may contain file attachments.

The maximum attachment size is **15 MB**.

Any file type is allowed, subject to the size limit and application security validation.

### Vaccinations

Vaccinations support:

* Fixed vaccination templates by species.
* Manual vaccinations.
* Automatic due-date calculation for template-based vaccinations.
* Manually entered due dates for manual vaccinations.
* Lists/reports of vaccinations that are due.

---

## 7. Data Management

The primary database is PostgreSQL.

Files uploaded to clinical records are stored locally.

No cloud file storage is required.

The system must maintain audit logs for important user actions.

Deletion uses a **soft-delete/restore mechanism** where applicable.

Restoring deleted records requires the appropriate permission.

---

## 8. Backup Policy

Database backups are performed locally.

The current backup policy is:

```text
Frequency: Daily
Time: 21:00
Retention: 30 latest backups
Storage: Local
```

Older backups beyond the retention limit should be removed according to the backup policy.

---

## 9. Explicitly Out of Scope

The following are not part of the current system:

* Billing
* Payments
* Financial accounting
* Inventory management
* Customer self-service booking
* SMS notifications
* Email notifications
* Cloud synchronization
* Multi-branch synchronization
* Microchip management
* Multi-language support
* Internet-dependent functionality

---

## 10. Development Principle

The project must use the simplest architecture that fully satisfies the requirements.

Do not introduce a technology, service, framework, or infrastructure component unless it provides a clear benefit required by the system.

The system must remain:

```text
Offline
LAN-based
Maintainable
Secure
Reliable
Simple
```

All future implementation decisions must remain consistent with the project's requirements, business rules, architecture, and technology decisions documented in the `docs/` directory.