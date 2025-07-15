from accounts.utils import anonymous_required
from accounts.decorators import labs_only
from accounts.forms import (
    UserRegistrationForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
)
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.shortcuts import render, redirect
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_str, force_bytes
from django.contrib.auth.tokens import default_token_generator
from accounts.signals import user_signed_up, email_confirmed
from accounts.tasks import send_verification_email_task
from accounts.models import User, UserProfile
from accounts.forms import UserForm, UserProfileForm
from accounts.utils import get_user_organization_type


@anonymous_required
def labs_login_view(request):
    """Handles login for Labs (data scientists uploading notebooks)."""
    if request.user.is_authenticated:
        return redirect("labs:labs_dashboard_home")

    # ✅ Guarda el parámetro ?next=... en la sesión si existe
    next_url = request.GET.get("next")
    if next_url:
        request.session["labs_post_login_redirect"] = next_url

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
                    return redirect("labs:labs_login")

                login(request, user)
                request.session.save()

                # ✅ Redirige al valor guardado si existe
                redirect_url = request.session.pop(
                    "labs_post_login_redirect", reverse("labs:labs_dashboard_home")
                )
                return redirect(redirect_url)

            else:
                messages.error(request, "Invalid credentials, please try again!")

    return render(request, "labs/accounts/login.html")


@anonymous_required
def labs_register_view(request):
    print("REGISTER VIEW")
    if request.user.is_authenticated:
        print(
            "🧪",
            request.user,
            request.user.is_authenticated,
            request.session.session_key,
        )
        return redirect("labs:labs_dashboard_home")

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
        return redirect("labs:labs_login")
    else:
        messages.error(request, "Activation link is invalid or expired.")
        return redirect("labs:labs_login")


def labs_password_reset_request(request):
    """
    Handles Labs password reset request and sends a password reset email.
    """
    if request.method == "POST":
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.get(email=email)
            mail_subject = "Reset Your Password - ModelMint Labs"

            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            # Send password reset email asynchronously with Labs-specific URL name
            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject=mail_subject,
                email_template="labs/accounts/emails/password_reset_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
                uidb64=uidb64,
                token=token,
                reset_url_name="labs:labs_password_reset_confirm",
            )

            messages.success(
                request,
                "A password reset email has been sent to your email.",
            )
            return redirect("labs:labs_login")
    else:
        form = CustomPasswordResetForm()

    return render(request, "labs/accounts/password_reset.html", {"form": form})


def labs_password_reset_confirm(request, uidb64, token):
    """
    Handles Labs password reset confirmation and form submission.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        if request.method == "POST":
            form = CustomSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()

                if not user.is_active:
                    user.is_active = True
                    user.save()

                messages.success(
                    request,
                    "Your password has been set! You can now log in.",
                )
                return redirect("labs:labs_login")
        else:
            form = CustomSetPasswordForm(user)

        return render(
            request, "labs/accounts/password_reset_confirm.html", {"form": form}
        )
    else:
        messages.error(request, "The reset link is invalid or expired.")
        return redirect("labs:labs_password_reset_request")


@login_required(login_url="labs:labs_login")
@labs_only
def labs_logout_view(request):
    auth.logout(request)
    messages.info(request, "You have sucesfully logged out!")
    return redirect("labs:labs_login")


@login_required(login_url="labs:labs_login")
@labs_only
def labs_profile_view(request):
    """
    Displays and allows editing of the Labs user's profile.
    """
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect("labs:labs_profile")

    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    return render(
        request,
        "labs/accounts/profile.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,
        },
    )
