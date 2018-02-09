# -*- coding: utf-8 -*-
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from user_management.models import GlobalGroup, KamajiUser


@receiver(post_save, sender=User)
def add_superuser_role(instance, created, **kwargs):
    """
    Listens to the post_save signal of the User model and adds newly
    created superusers to the global superuser group.

    :param instance: The user that was created
    :type instance: User
    :param created: Was the user created
    :type created: bool
    """
    user = instance

    if created:
        KamajiUser.objects.create(user=user)

        spectator_group = GlobalGroup.objects.get(
            name=GlobalGroup.DEFAULT_SPECTATORS
        )

        spectator_group.users.add(user)

        if user.is_superuser:
            superuser_group = GlobalGroup.objects.get(
                name=GlobalGroup.ADMINISTRATORS
            )
            superuser_group.users.add(user)
