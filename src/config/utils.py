from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings


def send_notification(mail_subject, mail_template, context, to_email=None):
    """
    Sends an email notification.

    Args:
        mail_subject (str): Subject of the email.
        mail_template (str): Path to the email template.
        context (dict): Context for rendering the template.
        to_email (list or str, optional): Email(s) to
        send the notification to. Defaults to context["email"].

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    try:
        from_email = settings.DEFAULT_FROM_EMAIL
        message = render_to_string(mail_template, context)

        if to_email is None:
            to_email = (
                [context["email"]]
                if isinstance(context["email"], str)
                else context["email"]
            )
        elif isinstance(to_email, str):
            to_email = [to_email]

        mail = EmailMessage(mail_subject, message, from_email, to=to_email)
        mail.content_subtype = "html"
        mail.send()
    except Exception as e:
        return False

    return True
