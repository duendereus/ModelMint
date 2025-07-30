from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


@shared_task
def notify_team_new_subscription(organization_name, plan_name, user_email):
    subject = f"🛒 New Subscription - {organization_name}"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient = settings.ADMIN_USER_EMAIL

    if not recipient:
        return

    context = {
        "organization_name": organization_name,
        "plan_name": plan_name,
        "user_email": user_email,
    }

    html_message = render_to_string(
        "subscriptions/emails/notify_team_new_subscription.html", context
    )

    plain_message = (
        f"A new subscription has been completed.\n\n"
        f"Organization: {organization_name}\n"
        f"Plan: {plan_name}\n"
        f"User: {user_email}"
    )

    send_mail(
        subject, plain_message, from_email, [recipient], html_message=html_message
    )
