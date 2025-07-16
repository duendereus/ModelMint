from django.dispatch import Signal
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from accounts.models import User, UserProfile, Organization, OrganizationProfile
from customers.models import OrganizationCustomer

User = get_user_model()

user_signed_up = Signal()
email_confirmed = Signal()


@receiver(user_signed_up)
def handle_user_signed_up(sender, request, user, **kwargs):
    """
    This function is triggered when a user signs up.
    It creates an OrganizationCustomer instance linked to the user's organization.
    """
    if hasattr(user, "owned_organization"):  # Ensure user is an org owner
        org = user.owned_organization
        OrganizationCustomer.objects.create(
            organization=org,
            init_email=org.owner.email,
            init_email_confirmed=False,  # Email is not confirmed yet
        )
        print(f"OrganizationCustomer created for {org.name} ({user.email})")


@receiver(email_confirmed)
def handle_email_confirmed(sender, request, user, **kwargs):
    """
    This function is triggered when a user's email is confirmed.
    It updates the OrganizationCustomer model to mark the email as confirmed.
    """
    try:
        organization = user.owned_organization
        org_customer = OrganizationCustomer.objects.get(
            organization=organization, init_email=user.email
        )
        org_customer.init_email_confirmed = True
        org_customer.save()  # This will trigger the `save` method
        print(f"Email confirmed for {organization.name} ({user.email})")
    except OrganizationCustomer.DoesNotExist:
        print(f"No organization customer record found for {user.email}")


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Creates a UserProfile instance automatically when a new user is created.
    """
    if created:
        UserProfile.objects.create(
            user=instance, name=instance.username
        )  # Set a default name


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Saves the UserProfile whenever the User instance is saved.
    """
    instance.profile.save()


@receiver(post_save, sender=Organization)
def create_organization_profile(sender, instance, created, **kwargs):
    """
    Automatically creates an OrganizationProfile
    when a new Organization is created.
    """
    if created and not hasattr(instance, "profile"):
        OrganizationProfile.objects.create(organization=instance)
        print(f"✅ OrganizationProfile created for {instance.name}")
