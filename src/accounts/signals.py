from django.dispatch import Signal
from django.dispatch import receiver
from django.contrib.auth import get_user_model
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
