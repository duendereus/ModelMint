from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from accounts.models import OrganizationMembership, Organization
from accounts.utils import generate_random_password
from accounts.tasks import send_verification_email_task
from analytics.models import Metric
from subscriptions.utils import can_add_member, get_plan_limits
from .forms import InviteMemberForm
from .models import DashboardSelection
from django.contrib.auth import get_user_model
from django.contrib import messages

User = get_user_model()


@login_required
def dashboard_home(request):
    """
    View for the main dashboard, displaying only selected metrics.
    - Owners can manage metric selection.
    - Members can only view the selected metrics.
    """
    organization = None
    dashboard_selection = None
    selected_metrics = []
    is_owner = False
    is_member = False

    # Check if the user is the owner of an organization
    if hasattr(request.user, "owned_organization"):
        organization = request.user.owned_organization
        is_owner = True

    # If the user is not an owner, check if they are a member of any organization
    elif OrganizationMembership.objects.filter(user=request.user).exists():
        organization = OrganizationMembership.objects.get(
            user=request.user
        ).organization
        is_member = True

    # If the user is part of an organization, fetch the dashboard selection
    if organization:
        dashboard_selection = DashboardSelection.objects.filter(
            organization=organization
        ).first()

        if dashboard_selection:
            # ✅ Prefetch table data to avoid missing relations
            selected_metrics = dashboard_selection.metrics.all().select_related("table_data")

            # ✅ Generate pre-signed URLs using the existing model method
            for metric in selected_metrics:
                metric.presigned_url = metric.get_presigned_url() if metric.file else None

    return render(
        request,
        "dashboard/home.html",
        {
            "selected_metrics": selected_metrics,
            "is_owner": is_owner,
            "is_member": is_member,
            "organization": organization,
        },
    )

@login_required
def invite_member(request):
    """Allows organization owners to invite new members or admins."""
    organization = get_object_or_404(Organization, owner=request.user)

    # ✅ Check member limit
    if not can_add_member(organization):
        # messages.warning(
        #     request,
        #     "You’ve reached the maximum number of members allowed by your subscription plan. "
        #     "Please remove members or upgrade your plan to add more."
        # )
        return redirect("dashboard:organization_users")

    if request.method == "POST":
        form = InviteMemberForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            role = form.cleaned_data["role"]
            name = form.cleaned_data["name"]

            random_password = generate_random_password()

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email,
                    "password": random_password,
                    "is_active": False,
                },
            )

            if created:
                user.set_password(random_password)
                user.save()

                user.profile.name = name
                user.profile.save()

            OrganizationMembership.objects.get_or_create(
                user=user, organization=organization, defaults={"role": role}
            )

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject="You've been invited to join an organization",
                email_template="dashboard/accounts/emails/invitation_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
                uidb64=uid,
                token=token,
            )

            messages.success(request, f"{email} has been invited successfully!")
            return redirect("dashboard:dashboard_home")
    else:
        form = InviteMemberForm()

    return render(request, "dashboard/accounts/invite_member.html", {"form": form})

@login_required
def organization_users(request):
    """
    Lists all users (owner and members/admins) of an organization.
    The organization is determined by either:
      - request.user.owned_organization (if the user is the owner)
      - Otherwise, the organization from one of the user's memberships.
    """
    organization = None

    # Determine the organization associated with the user
    if hasattr(request.user, "owned_organization"):
        organization = request.user.owned_organization
    else:
        membership = OrganizationMembership.objects.filter(user=request.user).first()
        if membership:
            organization = membership.organization

    if not organization:
        messages.error(request, "You are not associated with any organization.")
        return redirect("dashboard:dashboard_home")

    # Get the organization owner (a User instance)
    owner = organization.owner

    # Get all memberships for this organization.
    # These are OrganizationMembership objects containing user and role information.
    memberships = organization.members.all()

    limits = get_plan_limits(organization)
    max_members = limits.get("max_members", 1) if limits else 1

    context = {
        "organization": organization,
        "owner": owner,
        "memberships": memberships,
        "max_members": max_members,
    }
    return render(request, "dashboard/accounts/organization_users.html", context)


@login_required
def dashboard_customize(request):
    """
    Allows organization owners to select which metrics appear on the main dashboard.
    """
    organization = get_object_or_404(Organization, owner=request.user)

    # Get or create the selection model for this organization
    dashboard_selection, created = DashboardSelection.objects.get_or_create(
        organization=organization
    )

    # Get all available metrics from the organization's DataUpload reports
    available_metrics = Metric.objects.filter(datasource__organization=organization)

    if request.method == "POST":
        selected_metric_ids = request.POST.getlist(
            "metrics"
        )  # List of selected metric IDs

        # Update selection
        dashboard_selection.metrics.set(selected_metric_ids)

        messages.success(request, "Dashboard selection updated successfully!")
        return redirect("dashboard:dashboard_home")

    return render(
        request,
        "dashboard/customize_dashboard.html",
        {
            "available_metrics": available_metrics,
            "dashboard_selection": dashboard_selection,
        },
    )
