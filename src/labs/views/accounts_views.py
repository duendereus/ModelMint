from accounts.utils import anonymous_required
from accounts.forms import UserRegistrationForm
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from accounts.signals import user_signed_up, email_confirmed
from accounts.tasks import send_verification_email_task
from accounts.models import User
from accounts.utils import get_user_organization_type


@anonymous_required
def labs_register_view(request):
    if request.user.is_authenticated:
        return redirect("labs:labs_dashboard")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(org_type="lab")

            user_signed_up.send(sender=user.__class__, request=request, user=user)

            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject="Activate your Labs account",
                email_template="labs/accounts/emails/activation_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
            )

            messages.success(
                request,
                (
                    "Registration successful! Please check "
                    "your email to activate your Labs account."
                ),
            )
            return redirect("labs:labs_login")
    else:
        form = UserRegistrationForm()

    return render(request, "labs/accounts/register.html", {"form": form})


def labs_activate_account_view(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()

        email_confirmed.send(sender=user.__class__, request=request, user=user)

        login(request, user)
        messages.success(request, "Your Labs account has been activated successfully!")
        return redirect("labs:labs_landing")
    else:
        messages.error(request, "Activation link is invalid or expired.")
        return redirect("#")


@anonymous_required
def labs_login_view(request):
    """Handles login for Labs (data scientists uploading notebooks)."""
    if request.user.is_authenticated:
        return redirect("labs:labs_landing")  # Usuario ya autenticado

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        if email and password:
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(
                        request,
                        "Your account is inactive. Please check your email for activation.",
                    )
                    return redirect("labs:login")

                login(request, user)

                org_type = get_user_organization_type(user)

                if org_type == "lab":
                    return redirect("labs:labs_landing")  # Labs user
                else:
                    return redirect("dashboard:dashboard_home")

            else:
                messages.error(request, "Invalid credentials, please try again!")

    return render(request, "labs/accounts/login.html")
