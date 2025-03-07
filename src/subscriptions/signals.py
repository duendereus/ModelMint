from django.db.models.signals import post_save
from django.dispatch import receiver
from subscriptions.models import OrganizationSubscription

ALLOW_CUSTOM_GROUPS = True


@receiver(post_save, sender=OrganizationSubscription)
def update_organization_members_permissions(sender, instance, **kwargs):
    """
    Ensure all members of the organization inherit subscription permissions along with groups.
    """
    if instance.subscription:
        groups = instance.subscription.groups.all()
        permissions = (
            instance.subscription.permissions.all()
        )  # Fetch related permissions

        for membership in instance.organization.members.all():
            user = membership.user

            # Assign groups
            user.groups.set(groups)

            # Assign permissions explicitly
            for perm in permissions:
                user.user_permissions.add(perm)

            user.save()
