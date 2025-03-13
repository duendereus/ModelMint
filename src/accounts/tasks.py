from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings


@shared_task
def send_verification_email_task(
    user_id, mail_subject, email_template, domain, scheme, **kwargs
):
    """
    Asynchronous task to send an email with an account activation or password reset link.
    """
    from accounts.models import (
        User,
    )  # Import inside the function to avoid circular imports

    try:
        user = User.objects.get(pk=user_id)
        from_email = settings.DEFAULT_FROM_EMAIL

        # Retrieve uidb64 and token from kwargs, or generate if not provided
        uidb64 = kwargs.get("uidb64", urlsafe_base64_encode(force_bytes(user.pk)))
        token = kwargs.get("token", default_token_generator.make_token(user))

        message = render_to_string(
            email_template,
            {
                "user": user,
                "domain": domain,
                "scheme": scheme,
                "uid": uidb64,
                "token": token,
            },
        )

        to_email = user.email
        mail = EmailMessage(mail_subject, message, from_email, to=[to_email])
        mail.content_subtype = "html"
        mail.send()
    except User.DoesNotExist:
        # Handle the case where the user doesn't exist (perhaps log it)
        pass
