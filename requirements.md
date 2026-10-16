

# Vet Clinic Management System — Requirements

## 1. Scope

The system is an internal management system for a single veterinary clinic.

It must operate completely offline after deployment and must be accessible from multiple devices connected to the same local network (LAN).

Expected concurrent users: 3–4.

The system is for records and organization, not accounting.

---

## 2. Users

The system has three user types:

### Admin / Manager

* Has full system access.
* Creates Staff and Vet accounts.
* Determines permissions for each individual user.
* Can customize permissions beyond the user's default role.

### Staff

Responsible primarily for:

* Appointments
* Owners
* Animals
* Reminders

Actual permissions are determined individually by the Admin.

### Vet / Doctor

Responsible primarily for:

* Clinical records
* Vaccinations

Actual permissions are determined individually by the Admin.

---

## 3. Owners and Animals

### Owner

The system stores:

* Full name
* Phone
* Address
* Notes

One owner may have multiple animals.

### Animal

Each animal has exactly one primary owner.

The system stores:

* Name
* Species
* Breed — optional
* Gender
* Birth date / age
* Weight
* Color
* Optional image

Animal names do not need to be unique.

There is no microchip field.

The person bringing the animal to the clinic is recorded at the appointment/visit level and is not treated as the permanent owner.

---

## 4. Appointments

Appointments:

* Are created by Staff.
* Are associated with an Animal.
* Are assigned to a Vet.
* Store the Staff member who created them.
* Have a duration selected from a predefined list.
* Have a status:

  * Scheduled
  * Completed
  * Cancelled
  * No-show

The system must provide a visual calendar with month/week views.

### Appointment conflict rule

A Vet cannot have two overlapping appointments.

Different Vets may have appointments at the same time.

---

## 5. Reminders

Reminders are a separate section from appointments.

Each reminder is associated with:

* Animal
* Reason/note
* Due date

Statuses:

* Pending
* Converted to appointment
* Cancelled

A pending reminder can be converted directly into an appointment.

After conversion, its status becomes `Converted to appointment`.

Reminders are created and managed individually.

---

## 6. Clinical Records

Clinical records contain:

* Symptoms
* Diagnosis
* Prescribed treatment
* Weight at visit
* Additional notes

A clinical record may:

* Be linked to an existing appointment.
* Be created as a walk-in without an appointment.

Each clinical record may contain attachments.

### Attachments

* Any file type is allowed.
* Maximum file size: **15 MB**.
* Files are stored locally.
* No cloud storage is used.

---

## 7. Medical Timeline

Each animal must have a complete chronological medical timeline showing previous clinical visits.

The timeline should provide the veterinarian with a single place to review the animal's medical history.

---

## 8. Vaccinations

The system supports predefined vaccination schedules based on animal species.

A vaccination template defines the interval used to calculate the next due date.

The system also supports manually added vaccinations outside the predefined templates.

For template-based vaccinations:

```text
Last vaccination date
        +
Configured interval
        =
Next due date
```

For manually entered vaccinations, the due date is entered manually.

The system must provide a list/report of vaccinations that are due.

---

## 9. Reports

The system must support on-demand Excel export.

An exported client/animal report contains multiple worksheets:

### Sheet 1 — Basic Information

Owner and animal information.

### Sheet 2 — Clinical History

Complete clinical visit history.

### Sheet 3 — Vaccination History

Vaccination history.

There are no financial reports.

---

## 10. Permissions

Permissions are assigned individually by the Admin.

Permissions must not be determined exclusively by the user's role.

The system must support permissions for relevant actions such as:

* View
* Create
* Edit
* Delete
* Restore

This applies to relevant system resources.

### Clinical records

The Admin determines whether a Staff user can view, create, edit, or delete clinical records.

### Vet visibility

The Admin determines whether each Vet can see all patients or only patients assigned to that Vet.

### Restore

Restoring a soft-deleted record requires the appropriate `restore` permission.

---

## 11. Audit Logs

The system must maintain logs for user actions.

Audit records should allow the system to identify:

* Who performed the action
* What action was performed
* Which object/resource was affected
* When the action occurred

Audit logging is part of the system and should not depend on an external service.

---

## 12. Deletion and Restore

Records that support deletion should use soft deletion rather than immediately removing the database record.

Deleted records should be recoverable through a restore operation.

The ability to restore a record requires the appropriate permission.

The exact list of resources supporting soft deletion will be determined during domain/database design.

---

## 13. Backup

The database must be backed up locally.

Backup policy:

```text
Frequency: Daily
Time: 21:00
Retention: Latest 30 backups
Storage: Local
```

No cloud backup is required.

Backups older than the retention limit should be removed.

---

## 14. Offline and LAN Requirements

After deployment, the system must not require Internet access.

The system must not depend on:

* Cloud services
* External APIs
* Cloud databases
* Cloud file storage
* SMS services
* Email services

The application server runs inside the clinic's local network.

Other devices on the same LAN access the system through a web browser using the local server address.

Example:

```text
http://192.168.1.100:8000
```

The system must remain usable when the Internet connection is completely unavailable.

---

## 15. Explicitly Out of Scope

The following are not part of the current version:

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

---

## 16. Technology Constraints

The project should use a simple LAN-based web architecture.

The current technology direction is:

* Python
* Django
* PostgreSQL
* Django Templates
* HTMX
* Alpine.js
* Tailwind CSS
* FullCalendar
* Local file storage
* openpyxl

The project should **not** introduce unnecessary infrastructure.

The following are not required for the current scope:

* React
* Next.js
* Redis
* Celery
* Nginx
* Cloud services

Any new major technology must have a clear requirement-based justification before being introduced.

---

## 17. Core Design Principle

The implementation must follow the requirements rather than adding features based on assumptions.

When a requirement is unclear:

1. Do not invent a business rule.
2. Identify the ambiguity.
3. Ask for clarification before implementing it.

The system should prioritize:

**Reliability → Data integrity → Simplicity → Maintainability → User experience.**