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
    Supports passing uid/token manually, and optional reset_url_name for custom reverse.
    """
    from accounts.models import User
    from django.urls import reverse

    try:
        user = User.objects.get(pk=user_id)
        from_email = settings.DEFAULT_FROM_EMAIL

        # Get uid/token (or generate)
        uidb64 = kwargs.get("uidb64", urlsafe_base64_encode(force_bytes(user.pk)))
        token = kwargs.get("token", default_token_generator.make_token(user))

        # Optional: Generate reset URL if reset_url_name is provided
        reset_url = None
        reset_url_name = kwargs.get("reset_url_name")
        if reset_url_name:
            try:
                reset_url = reverse(
                    reset_url_name,
                    kwargs={"uidb64": uidb64, "token": token},
                )
            except Exception:
                reset_url = None  # Optional: log the error

        # ✅ Optional invited_by_name context
        invited_by_name = kwargs.get("invited_by_name", None)

        message = render_to_string(
            email_template,
            {
                "user": user,
                "domain": domain,
                "scheme": scheme,
                "uid": uidb64,
                "token": token,
                "reset_url": reset_url,
                "invited_by_name": invited_by_name,
            },
        )

        to_email = user.email
        mail = EmailMessage(mail_subject, message, from_email, to=[to_email])
        mail.content_subtype = "html"
        mail.send()
    except User.DoesNotExist:
        pass  # Optional: log error
