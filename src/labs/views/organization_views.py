from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from accounts.models import User, OrganizationMembership
from accounts.tasks import send_verification_email_task
from accounts.decorators import labs_only
from accounts.utils import generate_random_password
from analytics.utils.utils import get_user_organization
from subscriptions.utils import get_plan_limits, can_add_member
from dashboard.forms import InviteMemberForm
from helpers.organizations import can_manage_membership


@login_required(login_url="labs:labs_login")
@labs_only
def invite_lab_member(request):
    """Allows Lab owners to invite members or admins to their Labs organization."""
    organization = None

    if (
        hasattr(request.user, "owned_organization")
        and request.user.owned_organization.type == "lab"
    ):
        organization = request.user.owned_organization
    else:
        membership = (
            OrganizationMembership.objects.filter(
                user=request.user, organization__type="lab", role="admin"
            )
            .select_related("organization")
            .first()
        )
        if membership:
            organization = membership.organization

    if not organization:
        messages.warning(request, "You don’t have permission to invite members.")
        return redirect("labs:labs_dashboard_home")

    # ✅ Check member limit
    if not can_add_member(organization):
        messages.warning(
            request,
            "You’ve reached the maximum number of members allowed by your Labs plan. "
            "Please remove members or upgrade your plan to add more.",
        )
        return redirect("labs:labs_organization_users")

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
                user=user,
                organization=organization,
                defaults={"role": role},
            )

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            send_verification_email_task.delay(
                user_id=user.id,
                mail_subject="You’ve been invited to join a Labs organization",
                email_template="labs/accounts/emails/invitation_email.html",
                domain=request.get_host(),
                scheme=request.scheme,
                uidb64=uid,
                token=token,
                invited_by_name=request.user.profile.name or request.user.username,
                reset_url_name="labs:labs_password_reset_confirm",
            )

            messages.success(request, f"{email} has been invited successfully!")
            return redirect("labs:labs_dashboard_home")
    else:
        form = InviteMemberForm()

    return render(request, "labs/accounts/invite_member.html", {"form": form})


@login_required(login_url="labs:labs_login")
@labs_only
def labs_organization_users(request):
    """
    Lists all users of a Labs organization: owner + members/admins.
    """
    organization = None

    if (
        hasattr(request.user, "owned_organization")
        and request.user.owned_organization.type == "lab"
    ):
        organization = request.user.owned_organization
    else:
        membership = OrganizationMembership.objects.filter(
            user=request.user, organization__type="lab"
        ).first()
        if membership:
            organization = membership.organization

    if not organization:
        messages.error(request, "You are not part of any Labs organization.")
        return redirect("labs:labs_dashboard_home")

    owner = organization.owner
    memberships = organization.members.all()
    limits = get_plan_limits(organization)
    max_members = limits.get("max_members", 1) if limits else 1

    return render(
        request,
        "labs/accounts/organization_users.html",
        {
            "organization": organization,
            "owner": owner,
            "memberships": memberships,
            "max_members": max_members,
        },
    )


@login_required(login_url="labs:labs_login")
@labs_only
@require_http_methods(["POST"])
def delete_lab_member_view(request, member_id):
    organization = get_user_organization(request.user)
    membership = get_object_or_404(
        OrganizationMembership, id=member_id, organization=organization
    )

    if not can_manage_membership(request.user, membership, organization):
        messages.error(request, "You don’t have permission to remove this member.")
        return redirect("labs:labs_organization_users")

    membership.delete()
    messages.success(request, f"✅ {membership.user.email} has been removed.")
    return redirect("labs:labs_organization_users")


@login_required(login_url="labs:labs_login")
@labs_only
@require_http_methods(["POST"])
def edit_lab_member_view(request, member_id):
    new_role = request.POST.get("role")
    if new_role not in dict(OrganizationMembership.ROLE_CHOICES):
        messages.error(request, "Invalid role.")
        return redirect("labs:labs_organization_users")

    organization = get_user_organization(request.user)
    membership = get_object_or_404(
        OrganizationMembership, id=member_id, organization=organization
    )

    if not can_manage_membership(request.user, membership, organization):
        messages.error(request, "You don’t have permission to modify this member.")
        return redirect("labs:labs_organization_users")

    membership.role = new_role
    membership.save()
    messages.success(request, f"{membership.user.email} has been updated.")
    return redirect("labs:labs_organization_users")
