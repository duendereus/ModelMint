import random
import uuid
from datetime import timedelta
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from labs.models import NotebookAccessRequest


def generate_otp_code(length=6):
    """Genera un código numérico OTP de longitud fija (default = 6)."""
    return "".join(random.choices("0123456789", k=length))


def is_otp_expired(access_request):
    """Evalúa si el OTP ha expirado."""
    return timezone.now() > access_request.expires_at


def send_lab_otp_email(email, otp_code, notebook):
    """Envía el código OTP a un correo invitado para acceder al notebook."""
    subject = f"🔐 Código de acceso a notebook: {notebook.title}"
    from_email = settings.DEFAULT_FROM_EMAIL
    context = {
        "otp_code": otp_code,
        "notebook": notebook,
    }
    html_message = render_to_string("labs/dashboard/emails/otp_access.html", context)

    email_msg = EmailMessage(subject, html_message, from_email, to=[email])
    email_msg.content_subtype = "html"
    email_msg.send()


def generate_and_send_lab_otp(email, notebook, expires_after_hours=24):
    """Crea un OTP para acceso a un notebook y lo envía por correo."""
    otp_code = generate_otp_code()
    expires_at = timezone.now() + timedelta(hours=expires_after_hours)

    # Elimina solicitudes anteriores no verificadas
    NotebookAccessRequest.objects.filter(
        notebook=notebook, email=email, is_verified=False
    ).delete()

    access_request = NotebookAccessRequest.objects.create(
        notebook=notebook,
        email=email,
        otp_code=otp_code,
        expires_at=expires_at,
    )

    send_lab_otp_email(email=email, otp_code=otp_code, notebook=notebook)
    return access_request
