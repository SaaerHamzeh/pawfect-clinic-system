import logging
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import FileAttachment

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=FileAttachment)
def auto_delete_file_on_attachment_delete(sender, instance, **kwargs):
    """Deletes physical attachment file from filesystem only after the DB transaction commits."""
    if instance.file:
        storage = instance.file.storage
        file_name = instance.file.name

        def cleanup():
            try:
                if storage.exists(file_name):
                    storage.delete(file_name)
            except Exception:
                logger.warning(
                    f"Failed to physically delete attachment file '{file_name}' for FileAttachment ID {instance.pk}",
                    exc_info=True,
                )

        transaction.on_commit(cleanup)
