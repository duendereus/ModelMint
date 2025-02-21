from django.dispatch import Signal
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from customers.models import Customer

User = get_user_model()

user_signed_up = Signal()
email_confirmed = Signal()


@receiver(user_signed_up)
def handle_user_signed_up(sender, request, user, **kwargs):
    """
    This function is triggered when a user signs up.
    It creates a Customer instance linked to the new user.
    """
    email = user.email
    Customer.objects.create(
        user=user,
        init_email=email,
        init_email_confirmed=False,  # Email is not confirmed yet
    )
    print(f"Customer created for {user.email}")


@receiver(email_confirmed)
def handle_email_confirmed(sender, request, user, **kwargs):
    """
    This function is triggered when a user's email is confirmed.
    It updates the Customer model to mark the email as confirmed.
    """
    try:
        customer = Customer.objects.get(user=user, init_email=user.email)
        customer.init_email_confirmed = True
        customer.save()  # This will trigger the `save` method
        print(f"Email confirmed for {user.email}")
    except Customer.DoesNotExist:
        print(f"No customer record found for {user.email}")
