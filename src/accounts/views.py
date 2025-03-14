from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from .forms import (
    UserRegistrationForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
)
from .models import UserProfile
from .utils import anonymous_required
from .tasks import send_verification_email_task
from .signals import user_signed_up, email_confirmed
from .forms import UserForm, UserProfileForm
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator


User = get_user_model()


@anonymous_required
def login_view(request):
    """Handles user authentication."""
    if request.user.is_authenticated:
        return redirect("home")  # Redirect logged-in users

    if request.method == "POST":
        email = request.POST.get("email") or None
        password = request.POST.get("password") or None

        if all([email, password]):
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if not user.is_active:
                    messages.error(
                        request,
                        "Your account is inactive. Please check your email for activation.",
                    )
                    return redirect("accounts:login")

                login(request, user)
                return redirect("home")  # Redirect authenticated user to home page
            else:
                messages.error(request, "Invalid credentials, please try again!")

    return render(request, "accounts/login.html")


@login_required(login_url="accounts:login")
def logout(request):
    auth.logout(request)
    messages.info(request, "You have sucesfully logged out!")
    return redirect("accounts:login")


@anonymous_required
def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Dispatch the user_signed_up signal
            user_signed_up.send(sender=user.__class__, request=request, user=user)

            # Send verification email asynchronously
            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject="Activate Your Account",
                email_template="accounts/emails/activation_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
            )

            messages.success(
                request, "Registration successful! Please check your email."
            )
            return redirect("accounts:login")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def activate_account(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()

        # Dispatch the email_confirmed signal
        email_confirmed.send(sender=user.__class__, request=request, user=user)

        login(request, user)
        messages.success(request, "Your account has been activated successfully!")
        return redirect("accounts:login")
    else:
        messages.error(request, "Activation link is invalid or expired.")
        return redirect("accounts:login")


def password_reset_request(request):
    """
    Handles password reset request and sends a password reset email.
    """
    if request.method == "POST":
        form = CustomPasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.get(email=email)
            mail_subject = "Reset Your Password - ModelMint"

            # Send password reset email asynchronously
            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject=mail_subject,
                email_template="accounts/emails/password_reset_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
            )

            messages.success(
                request, "A password reset email has been sent to your email."
            )
            return redirect("accounts:login")

    else:
        form = CustomPasswordResetForm()

    return render(request, "accounts/password_reset.html", {"form": form})


def password_reset_confirm(request, uidb64, token):
    """
    Handles password reset confirmation and form submission.
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

                # Check if user was invited (i.e., previously inactive)
                if not user.is_active:
                    user.is_active = True
                    user.save()

                messages.success(
                    request, "Your password has been set! You can now log in."
                )
                return redirect("accounts:login")
        else:
            form = CustomSetPasswordForm(user)

        return render(request, "accounts/password_reset_confirm.html", {"form": form})

    else:
        messages.error(request, "The reset link is invalid or expired.")
        return redirect("accounts:password_reset_request")


@login_required
def profile_view(request):
    """
    Displays and allows editing of the user's profile.
    """
    user = request.user
    profile, created = UserProfile.objects.get_or_create(
        user=user
    )  # Ensure profile exists

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect("dashboard:profile")

    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
    }
    return render(request, "dashboard/accounts/profile.html", context)
