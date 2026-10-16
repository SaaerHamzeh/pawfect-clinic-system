from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Appointment
from apps.reminders.models import Reminder


@receiver(post_save, sender=Appointment)
def reset_reminders_on_appointment_cancel_or_soft_delete(sender, instance, **kwargs):
    """
    When an appointment transitions to CANCELLED or is soft-deleted,
    any linked Reminder in CONVERTED status must revert to PENDING and clear its converted_appointment.
    """
    if instance.status == Appointment.Status.CANCELLED or instance.is_deleted:
        instance.source_reminders.filter(status=Reminder.Status.CONVERTED).update(
            status=Reminder.Status.PENDING,
            converted_appointment=None,
            updated_at=timezone.now(),
        )


@receiver(pre_delete, sender=Appointment)
def reset_reminders_on_appointment_hard_delete(sender, instance, **kwargs):
    """
    When an appointment is permanently hard-deleted from database,
    revert any linked Reminder in CONVERTED status to PENDING before the ForeignKey is set to NULL.
    """
    instance.source_reminders.filter(status=Reminder.Status.CONVERTED).update(
        status=Reminder.Status.PENDING,
        converted_appointment=None,
        updated_at=timezone.now(),
    )
