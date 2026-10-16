import logging
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Animal

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=Animal)
def auto_delete_photo_on_animal_delete(sender, instance, **kwargs):
    """Deletes physical photo file from filesystem only after the DB transaction commits."""
    if instance.photo:
        storage = instance.photo.storage
        photo_name = instance.photo.name

        def cleanup():
            try:
                if storage.exists(photo_name):
                    storage.delete(photo_name)
            except Exception:
                logger.warning(
                    f"Failed to physically delete photo file '{photo_name}' for animal ID {instance.pk}",
                    exc_info=True,
                )

        transaction.on_commit(cleanup)
