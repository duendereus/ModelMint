from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .forms import ContactForm
from config.utils import send_notification


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save()

            # Email context
            email_context = {
                "name": contact.name,
                "email": contact.email,
                "subject": contact.subject,
                "content": contact.content,
            }

            # Send email to admin
            admin_email = settings.EMAIL_HOST_USER
            send_notification(
                mail_subject="New Contact Form Submission",
                mail_template="contact/emails/contact_email.html",
                context=email_context,
                to_email=admin_email,
            )

            messages.success(request, "Your message has been sent successfully!")
            return redirect("home")
    else:
        form = ContactForm()

    return render(request, "contact/contact.html", {"form": form})
