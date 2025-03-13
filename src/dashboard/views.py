from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from accounts.models import OrganizationMembership, Organization
from accounts.utils import generate_random_password
from accounts.tasks import send_verification_email_task
from .forms import InviteMemberForm
from django.contrib.auth import get_user_model
from django.contrib import messages

User = get_user_model()


@login_required
def dashboard_home(request):
    """
    View for the dashboard home page.
    Ensures only authenticated users can access it.
    """

    context = {}

    return render(request, "dashboard/home.html", context)


@login_required
def invite_member(request):
    """Allows organization owners to invite new members or admins."""
    organization = get_object_or_404(Organization, owner=request.user)

    if request.method == "POST":
        form = InviteMemberForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            role = form.cleaned_data["role"]

            # Generate a random password
            random_password = generate_random_password()

            # Create the new user with a random password (inactive)
            user = User.objects.create_user(
                email=email, username=email, password=random_password
            )
            user.is_active = False  # User will activate via password reset
            user.save()

            # Add the user to the organization
            OrganizationMembership.objects.create(
                user=user, organization=organization, role=role
            )

            # Generate password reset token and send the direct reset link
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject="You've been invited to join an organization",
                email_template="dashboard/accounts/emails/invitation_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
                uidb64=uid,  # Pass UID for direct reset link
                token=token,  # Pass generated token
            )

            messages.success(request, f"{email} has been invited successfully!")
            return redirect("dashboard:dashboard_home")

    else:
        form = InviteMemberForm()

    return render(request, "dashboard/accounts/invite_member.html", {"form": form})
