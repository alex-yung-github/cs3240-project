from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User

# new user will be assigned patron
@receiver(post_save, sender=User)
def assign_default_role(sender, instance, created, **kwargs):
    if created and not instance.role:
        instance.role = 'patron'
        instance.save()
        print(f"Assigned default role to user: {instance.username} -> {instance.role}")