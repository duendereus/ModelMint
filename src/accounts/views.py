from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, CustomPasswordResetForm, CustomSetPasswordForm
from .utils import send_verification_email
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.contrib.auth.tokens import default_token_generator
from .utils import anonymous_required


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
    """Handles user registration and sends email verification."""
    if request.user.is_authenticated:
        return redirect("home")  # Redirect logged-in users

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  # User must activate account via email
            user.save()

            send_verification_email(
                request,
                user,
                "Activate Your Account",
                "accounts/emails/activation_email.html",
            )

            messages.success(
                request,
                "Registration successful! Please check your email to activate your account.",
            )
            return redirect("accounts:login")  # Redirect to login page
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def activate_account(request, uidb64, token):
    """Handles user account activation via email link"""
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, "Your account has been activated successfully!")
        return redirect("accounts:login")
    else:
        messages.error(request, "Activation link is invalid or expired.")
        return redirect("accounts:login")
        # return HttpResponse("Activation link is invalid or expired.", status=400)


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

            # Send email using the reusable function
            send_verification_email(
                request=request,
                user=user,
                mail_subject=mail_subject,
                email_template="accounts/emails/password_reset_email.html",
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
                messages.success(request, "Your password has been reset successfully!")
                return redirect("accounts:login")
        else:
            form = CustomSetPasswordForm(user)

        return render(request, "accounts/password_reset_confirm.html", {"form": form})

    else:
        messages.error(request, "The reset link is invalid or expired.")
        return redirect("accounts:password_reset_request")
