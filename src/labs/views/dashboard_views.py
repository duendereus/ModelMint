from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from labs.models import LabNotebook
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import OrganizationMembership
from accounts.decorators import labs_only
from analytics.utils.utils import get_user_organization
from labs.models import LabNotebook, NotebookTableMetric
from labs.forms import LabNotebookUploadForm
from subscriptions.utils import get_plan_limits
import os


@login_required
@labs_only
def dashboard_home_labs_view(request):
    """
    Labs Dashboard Home View:
    Muestra los LabNotebooks subidos por los miembros del equipo.
    Solo accesible si el usuario pertenece a una organización tipo 'lab'.
    """
    organization = None
    is_owner = False
    is_member = False
    notebooks = []

    # Detecta si es owner o miembro
    if (
        hasattr(request.user, "owned_organization")
        and request.user.owned_organization.type == "lab"
    ):
        organization = request.user.owned_organization
        is_owner = True
    else:
        membership = OrganizationMembership.objects.filter(
            user=request.user, organization__type="lab"
        ).first()
        if membership:
            organization = membership.organization
            is_member = True

    if organization:
        notebooks = LabNotebook.objects.filter(
            organization=organization, active=True
        ).order_by("-created_at")

    return render(
        request,
        "labs/dashboard/home.html",
        {
            "organization": organization,
            "is_owner": is_owner,
            "is_member": is_member,
            "notebooks": notebooks,
        },
    )


@login_required
def lab_notebook_upload_view(request):
    user = request.user
    organization = get_user_organization(user)

    if not organization or organization.type != "lab":
        messages.warning(
            request, "Your organization is not allowed to upload notebooks."
        )
        return redirect("dashboard:dashboard_home")

    limits = get_plan_limits(organization)
    if not limits:
        messages.error(
            request,
            "Your organization doesn't have an active Labs plan. Please upgrade to enable notebook uploads.",
        )
        return redirect("dashboard:dashboard_home")

    max_reports = limits.get("max_reports", 1)
    current_active_notebooks = LabNotebook.objects.filter(
        organization=organization, active=True
    ).count()

    if request.method == "POST":
        form = LabNotebookUploadForm(request.POST, request.FILES)
        files = request.FILES.getlist("files")  # Aquí accedemos a los .csv/.xlsx

        if form.is_valid():
            if current_active_notebooks >= max_reports:
                messages.error(
                    request,
                    f"You've reached the limit of {max_reports} active notebook(s) for your plan.",
                )
                return redirect("dashboard:labs:notebook_upload")

            notebook = form.save(commit=False)
            notebook.organization = organization
            notebook.created_by = user
            notebook.save()

            # 💡 Guardar archivos complementarios
            VALID_EXTS = {".csv", ".xls", ".xlsx"}
            for f in files:
                ext = os.path.splitext(f.name)[1].lower()
                if ext not in VALID_EXTS:
                    messages.warning(request, f"Skipped unsupported file: {f.name}")
                    continue

                NotebookTableMetric.objects.create(
                    notebook=notebook,
                    file=f,
                    original_filename=f.name,
                    uploaded_by=user,
                )

            messages.success(request, "✅ Notebook uploaded successfully.")
            return redirect("dashboard:labs:notebook_detail", slug=notebook.slug)
    else:
        form = LabNotebookUploadForm()

    can_upload = current_active_notebooks < max_reports

    return render(
        request,
        "labs/dashboard/notebook_upload.html",
        {
            "form": form,
            "max_allowed": max_reports,
            "current_count": current_active_notebooks,
            "plan_name": (
                getattr(organization.subscription.subscription, "name", "Free")
                if hasattr(organization, "subscription") and organization.subscription
                else "Free"
            ),
            "can_upload": can_upload,
        },
    )
