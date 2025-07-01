from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.files.storage import default_storage
from labs.models import LabNotebook
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import OrganizationMembership
from accounts.decorators import labs_only
from analytics.utils.utils import get_user_organization
from labs.models import LabNotebook
from labs.forms import LabNotebookUploadForm
from labs.tasks import process_lab_notebook_task
from subscriptions.utils import get_plan_limits
import os, uuid


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
        membership = (
            OrganizationMembership.objects.filter(
                user=request.user, organization__type="lab"
            )
            .select_related("organization")
            .first()
        )
        if membership:
            organization = membership.organization
            is_member = True

    if organization:
        notebooks = (
            LabNotebook.objects.filter(organization=organization, active=True)
            .prefetch_related("versions")
            .order_by("-created_at")
        )

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
@labs_only
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
            (
                "Your organization doesn't have an active Labs plan. "
                "Please upgrade to enable notebook uploads."
            ),
        )
        return redirect("dashboard:dashboard_home")

    max_reports = limits.get("max_reports", 1)
    current_active_notebooks = organization.lab_notebooks.filter(active=True).count()

    if request.method == "POST":
        form = LabNotebookUploadForm(
            request.POST, request.FILES, organization=organization, created_by=user
        )
        files = request.FILES.getlist("complementary_files")

        if not files:
            messages.info(request, "No complementary files uploaded.")

        if form.is_valid():
            if current_active_notebooks >= max_reports:
                messages.error(
                    request,
                    f"You've reached the limit of {max_reports} active notebook(s) for your plan.",
                )
                return redirect("dashboard:labs:notebook_upload")

            notebook = form.save(commit=True)

            VALID_EXTS = {".csv", ".xls", ".xlsx"}
            file_entries = []

            for f in files:
                ext = os.path.splitext(f.name)[1].lower()
                if ext not in VALID_EXTS:
                    messages.warning(request, f"Skipped unsupported file: {f.name}")
                    continue

                stored_path = default_storage.save(f"labs_temp/{f.name}", f)
                file_entries.append(
                    {
                        "stored_path": stored_path,
                        "original_name": f.name,
                    }
                )

            messages.success(request, "✅ Notebook uploaded successfully.")
            process_lab_notebook_task.delay(notebook.id, file_entries=file_entries)
            return redirect("labs:labs_dashboard_home")
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


@login_required
@labs_only
@require_http_methods(["GET", "POST"])
def upload_new_version_view(request, notebook_id):
    user = request.user
    organization = get_user_organization(user)

    if not organization or organization.type != "lab":
        messages.warning(
            request, "Your organization is not allowed to upload notebooks."
        )
        return redirect("dashboard:dashboard_home")

    # Asegura que el notebook pertenezca a la organización del usuario
    notebook = get_object_or_404(
        LabNotebook.objects.filter(active=True, organization=organization),
        id=notebook_id,
    )

    if request.method == "POST":
        html_file = request.FILES.get("html_file")
        files = request.FILES.getlist("complementary_files")

        if not html_file:
            messages.error(request, "Please upload a valid HTML file.")
            return redirect(request.path)

        # Guardar el HTML en storage temporal (ej. S3 o local)
        html_name = f"labs_temp/v{uuid.uuid4().hex}_{html_file.name}"
        stored_html_path = default_storage.save(html_name, html_file)

        file_entries = []
        VALID_EXTS = {".csv", ".xls", ".xlsx"}

        for f in files:
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in VALID_EXTS:
                messages.warning(request, f"⚠️ Skipped unsupported file: {f.name}")
                continue

            safe_name = f"{uuid.uuid4().hex}_{f.name.replace(' ', '_')}"
            stored_path = default_storage.save(f"labs_temp/{safe_name}", f)

            file_entries.append(
                {
                    "stored_path": stored_path,
                    "original_name": f.name,
                }
            )

        # ✅ Actualiza temporalmente el archivo del notebook para procesarlo
        notebook.file.name = stored_html_path
        process_lab_notebook_task.delay(notebook.id, file_entries=file_entries)

        messages.success(request, "✅ New version uploaded. Processing in background.")
        return redirect("labs:labs_dashboard_home")

    return render(
        request,
        "labs/dashboard/upload_new_version.html",
        {
            "notebook": notebook,
        },
    )
