from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.urls import reverse
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import (
    JsonResponse,
    HttpResponse,
    HttpResponseRedirect,
    HttpResponseForbidden,
)
from django.template.loader import render_to_string
from django.utils import timezone
from accounts.models import OrganizationMembership
from accounts.decorators import labs_only
from analytics.utils.utils import get_user_organization
from labs.models import (
    LabNotebook,
    NotebookMetric,
    NotebookVersion,
    NotebookAccessRequest,
)
from labs.forms import LabNotebookUploadForm, NotebookAccessForm
from labs.tasks import process_lab_notebook_task
from labs.utils.otp import (
    generate_and_send_lab_otp,
    generate_otp_code,
    send_lab_otp_email,
)
from subscriptions.utils import get_plan_limits
import os, uuid, logging, json, base64, requests
from weasyprint import HTML
from datetime import timedelta

logger = logging.getLogger(__name__)


@login_required(login_url="labs:labs_login")
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


@login_required(login_url="labs:labs_login")
@labs_only
def dashboard_my_notebooks_view(request):
    """
    Labs Dashboard - My Notebooks View:
    Muestra únicamente los LabNotebooks subidos por el usuario autenticado.
    """
    notebooks = (
        LabNotebook.objects.filter(created_by=request.user, active=True)
        .prefetch_related("versions")
        .order_by("-created_at")
    )

    return render(
        request,
        "labs/dashboard/my_notebooks.html",
        {
            "notebooks": notebooks,
        },
    )


@login_required(login_url="labs:labs_login")
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


@login_required(login_url="labs:labs_login")
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

    # ✅ Asegura que el notebook pertenezca a la organización del usuario
    notebook = get_object_or_404(
        LabNotebook.objects.filter(active=True, organization=organization),
        id=notebook_id,
    )

    # ✅ Límite de versiones por notebook según plan
    plan_limits = get_plan_limits(organization)
    max_versions = plan_limits.get("max_versions_per_notebook", 1)
    current_versions = notebook.versions.count()
    can_upload_new_version = current_versions < max_versions

    if request.method == "POST":
        if not can_upload_new_version:
            messages.error(
                request,
                (
                    f"You've reached the version limit ({max_versions})"
                    " for this notebook under your current plan."
                ),
            )
            return redirect("labs:labs_dashboard_home")

        html_file = request.FILES.get("html_file")
        files = request.FILES.getlist("complementary_files")

        if not html_file:
            messages.error(request, "Please upload a valid HTML file.")
            return redirect(request.path)

        # Guardar el HTML temporalmente
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

        # ✅ Actualiza el archivo del notebook para procesarlo
        notebook.file.name = stored_html_path
        process_lab_notebook_task.delay(notebook.id, file_entries=file_entries)

        messages.success(request, "✅ New version uploaded. Processing in background.")
        return redirect("labs:labs_dashboard_home")

    # Mostrar formulario (GET)
    plan_name = (
        getattr(organization.subscription.subscription, "name", "Free")
        if hasattr(organization, "subscription") and organization.subscription
        else "Free"
    )

    return render(
        request,
        "labs/dashboard/upload_new_version.html",
        {
            "notebook": notebook,
            "plan_name": plan_name,
            "current_versions": current_versions,
            "max_versions": max_versions,
            "can_upload_new_version": can_upload_new_version,
        },
    )


@login_required(login_url="labs:labs_login")
@labs_only
@require_http_methods(["GET", "POST"])
def lab_preview_notebook_view(request, notebook_slug):
    notebook = get_object_or_404(
        LabNotebook.objects.select_related("organization", "created_by").filter(
            active=True
        ),
        slug=notebook_slug,
        organization=get_user_organization(request.user),
    )

    user = request.user
    is_creator = notebook.created_by == user
    is_org_owner = notebook.organization.owner == user

    # 🔒 Redirige si el usuario no tiene permisos para editar (ni creador ni dueño de la org)
    if not (is_creator or is_org_owner):
        return redirect("labs:labs_dashboard_home")

    all_versions = notebook.versions.order_by("-created_at")
    selected_version_id = request.GET.get("version_id")

    if selected_version_id:
        selected_version = get_object_or_404(
            NotebookVersion, id=selected_version_id, notebook=notebook
        )
    else:
        latest_metric = (
            NotebookMetric.objects.filter(notebook=notebook, is_preview=True)
            .exclude(version_obj__isnull=True)
            .order_by("-version_obj__created_at")
            .first()
        )
        selected_version = (
            latest_metric.version_obj if latest_metric else notebook.versions.first()
        )

    # POST: aplicar edición, orden y publicación
    if request.method == "POST":
        try:
            with transaction.atomic():
                data = json.loads(request.body)
                ordered_ids = data.get("ordered_ids", [])
                removed_ids = data.get("removed_ids", [])
                edited_titles = data.get("edited_titles", {})
                edited_values = data.get("edited_values", {})

                if (
                    not ordered_ids
                    and not removed_ids
                    and not edited_titles
                    and not edited_values
                ):
                    return JsonResponse(
                        {"success": False, "error": "Nothing to update."}, status=400
                    )

                if removed_ids:
                    NotebookMetric.objects.filter(
                        id__in=removed_ids, notebook=notebook
                    ).delete()

                for metric_id in set(edited_titles.keys()) | set(edited_values.keys()):
                    try:
                        metric = NotebookMetric.objects.get(
                            id=metric_id, notebook=notebook
                        )
                        if metric_id in edited_titles:
                            metric.name = edited_titles[metric_id].strip()
                        if metric_id in edited_values and metric.type in [
                            "text",
                            "single_value",
                        ]:
                            metric.value = edited_values[metric_id].strip()
                        metric.save()
                    except NotebookMetric.DoesNotExist:
                        continue

                TEMP_OFFSET = 10000
                for i, metric_id in enumerate(ordered_ids):
                    try:
                        metric = NotebookMetric.objects.select_for_update().get(
                            id=metric_id, notebook=notebook
                        )
                        metric.position = TEMP_OFFSET + i
                        metric.save()
                    except NotebookMetric.DoesNotExist:
                        continue

                for i, metric_id in enumerate(ordered_ids):
                    try:
                        metric = NotebookMetric.objects.select_for_update().get(
                            id=metric_id, notebook=notebook
                        )
                        metric.position = i
                        metric.save()
                    except NotebookMetric.DoesNotExist:
                        continue

                # Marcar métricas como publicadas
                NotebookMetric.objects.filter(notebook=notebook).update(
                    is_preview=False
                )

                return JsonResponse(
                    {
                        "success": True,
                        "redirect_url": reverse("labs:labs_dashboard_home"),
                    }
                )

        except Exception as e:
            logger.exception("Error publishing notebook preview")
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    # GET
    metrics = (
        NotebookMetric.objects.filter(notebook=notebook, version_obj=selected_version)
        .order_by("position")
        .select_related("table_data")
    )

    for m in metrics:
        m.presigned_url = m.get_presigned_url() if m.file else None
        m.is_published = not m.is_preview

    return render(
        request,
        "labs/dashboard/lab_preview_notebook.html",
        {
            "notebook": notebook,
            "selected_version": selected_version,
            "all_versions": all_versions,
            "metrics": metrics,
        },
    )


def lab_notebook_detail_view(request, notebook_slug):
    """
    Vista de detalle para un notebook publicado (Labs).
    - Si es público, cualquier persona con el link puede verlo.
    - Si no es público, se requiere:
        - Ser miembro/dueño/creador, o
        - Tener sesión OTP activa.
    """
    notebook = get_object_or_404(
        LabNotebook.objects.select_related("organization", "created_by").filter(
            active=True
        ),
        slug=notebook_slug,
    )

    organization = notebook.organization
    plan_limits = get_plan_limits(organization)

    # --- CONTROL DE ACCESO ---
    user = request.user
    is_authenticated = user.is_authenticated
    is_owner = is_authenticated and organization.owner == user
    is_member = is_authenticated and organization.members.filter(user=user).exists()
    is_creator = is_authenticated and notebook.created_by == user

    if not notebook.is_public:
        if not (is_owner or is_member or is_creator):
            session_tokens = request.session.get("verified_notebook_tokens", [])
            valid_token_exists = NotebookAccessRequest.objects.filter(
                notebook=notebook,
                session_token__in=session_tokens,
                is_verified=True,
                expires_at__gt=timezone.now(),
            ).exists()

            if not valid_token_exists:
                return redirect(
                    "labs:lab_notebook_enter_email", notebook_slug=notebook.slug
                )

    # --- Obtener versiones ---
    all_versions = notebook.versions.order_by("-created_at")

    selected_version_id = request.GET.get("version_id")
    selected_version = None

    if selected_version_id:
        selected_version = get_object_or_404(notebook.versions, id=selected_version_id)
    else:
        latest_metric = (
            NotebookMetric.objects.filter(notebook=notebook, is_preview=False)
            .exclude(version_obj__isnull=True)
            .order_by("-version_obj__created_at")
            .first()
        )
        selected_version = (
            latest_metric.version_obj if latest_metric else all_versions.first()
        )

    if not selected_version:
        messages.warning(request, "No versions found for this notebook.")
        return redirect("labs:labs_dashboard_home")

    metrics = (
        NotebookMetric.objects.filter(
            notebook=notebook, version_obj=selected_version, is_preview=False
        )
        .order_by("position")
        .select_related("table_data")
    )

    for metric in metrics:
        metric.presigned_url = metric.get_presigned_url() if metric.file else None
        metric.is_published = True

    is_guest = not request.user.is_authenticated

    return render(
        request,
        "labs/dashboard/lab_notebook_detail.html",
        {
            "notebook": notebook,
            "selected_version": selected_version,
            "all_versions": all_versions,
            "metrics": metrics,
            "plan_limits": plan_limits,
            "is_guest": is_guest,
        },
    )


def download_pdf_notebook(request, notebook_slug):
    """
    Exporta una versión publicada de un notebook en formato PDF (solo Labs).
    Soporta acceso vía OTP o membresía si el plan lo permite.
    """
    try:
        notebook = get_object_or_404(
            LabNotebook.objects.select_related("organization", "created_by").filter(
                active=True
            ),
            slug=notebook_slug,
        )

        organization = notebook.organization
        plan_limits = get_plan_limits(organization)

        if not plan_limits.get("allow_pdf_download", False):
            messages.warning(
                request,
                "La descarga en PDF solo está disponible en planes Team y Org Pro.",
            )
            return redirect("labs:lab_notebook_detail", notebook_slug=notebook_slug)

        # --- Control de acceso ---
        user = request.user
        is_authenticated = user.is_authenticated
        is_owner = is_authenticated and organization.owner == user
        is_member = is_authenticated and organization.members.filter(user=user).exists()
        is_creator = is_authenticated and notebook.created_by == user

        if not notebook.is_public:
            if not (is_owner or is_member or is_creator):
                session_tokens = request.session.get("verified_notebook_tokens", [])
                valid_token_exists = NotebookAccessRequest.objects.filter(
                    notebook=notebook,
                    session_token__in=session_tokens,
                    is_verified=True,
                    expires_at__gt=timezone.now(),
                ).exists()

                if not valid_token_exists:
                    messages.error(
                        request, "🔒 No tienes permiso para descargar este notebook."
                    )
                    return redirect(
                        "labs:labs:lab_notebook_verify_otp", notebook_slug=notebook.slug
                    )

        # --- Obtener versión ---
        version_id = request.GET.get("version_id")
        if version_id:
            version = get_object_or_404(notebook.versions, id=version_id)
        else:
            latest_metric = (
                NotebookMetric.objects.filter(notebook=notebook, is_preview=False)
                .exclude(version_obj__isnull=True)
                .order_by("-version_obj__created_at")
                .first()
            )
            version = latest_metric.version_obj if latest_metric else None

        if not version:
            messages.warning(request, "No se encontró una versión válida.")
            return redirect("labs:lab_notebook_detail", notebook_slug=notebook.slug)

        # --- Obtener métricas ---
        metrics = (
            NotebookMetric.objects.filter(
                notebook=notebook, version_obj=version, is_preview=False
            )
            .select_related("table_data")
            .order_by("position")
        )

        for metric in metrics:
            metric.presigned_url = None
            metric.base64_image = None
            if metric.type == "plot" and metric.file:
                try:
                    presigned_url = metric.get_presigned_url(expires_in=60)
                    response = requests.get(presigned_url)
                    response.raise_for_status()
                    ext = metric.file.name.split(".")[-1].lower()
                    ext = "png" if ext not in ["jpg", "jpeg", "svg"] else ext
                    encoded = base64.b64encode(response.content).decode()
                    metric.base64_image = f"data:image/{ext};base64,{encoded}"
                except Exception:
                    metric.base64_image = None

        # --- Logo ---
        logo_base64 = None
        logo_path = os.path.join(settings.BASE_DIR, "static", "img", "logo-green.png")
        try:
            with open(logo_path, "rb") as logo_file:
                encoded_logo = base64.b64encode(logo_file.read()).decode()
                logo_base64 = f"data:image/png;base64,{encoded_logo}"
        except Exception as logo_exc:
            logger.warning(f"[PDF Download] Could not encode logo: {logo_exc}")

        html = render_to_string(
            "labs/dashboard/pdf/pdf_notebook.html",
            {
                "notebook": notebook,
                "organization": organization,
                "version": version,
                "metrics": metrics,
                "logo_base64": logo_base64,
            },
            request=request,
        )

        pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = (
            f"inline; filename=Notebook_{notebook.slug}_v{version.version}.pdf"
        )
        return response

    except Exception as e:
        return HttpResponse(
            "Ocurrió un error al generar el PDF. Intenta más tarde.",
            status=500,
        )


@login_required(login_url="labs:labs_login")
@labs_only
def delete_lab_notebook(request, notebook_slug):
    """
    Permite eliminar un notebook si el usuario es el
    creador o el owner de la organización (Labs).
    """
    if request.method != "POST":
        raise PermissionDenied("Invalid request method.")

    notebook = get_object_or_404(
        LabNotebook.objects.select_related("organization", "created_by"),
        slug=notebook_slug,
        organization=get_user_organization(request.user),
    )

    user = request.user
    organization = notebook.organization

    is_creator = notebook.created_by == user
    is_owner = organization.owner == user

    if not (is_creator or is_owner):
        raise PermissionDenied("You do not have permission to delete this notebook.")

    notebook_title = notebook.title

    # DELETE PERMANENTLY
    # notebook.delete()

    # SOFT DELETE
    notebook.active = False
    notebook.save()

    messages.success(request, f"The notebook '{notebook_title}' has been deleted.")
    return redirect("labs:labs_dashboard_home")


def lab_notebook_enter_email_view(request, notebook_slug):
    """
    Vista unificada para ingresar email y generar OTP automáticamente si el email está autorizado.
    """
    notebook = get_object_or_404(LabNotebook, slug=notebook_slug, active=True)

    if notebook.is_public:
        return redirect("labs:lab_notebook_detail", notebook_slug=notebook.slug)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        if not email:
            messages.warning(request, "Email is required.")
            return redirect(
                "labs:lab_notebook_enter_email", notebook_slug=notebook.slug
            )

        if email not in (notebook.allowed_emails or []):
            messages.error(
                request, "This email is not authorized to access this notebook."
            )
            return redirect(
                "labs:lab_notebook_enter_email", notebook_slug=notebook.slug
            )

        # Validar plan
        plan_limits = get_plan_limits(notebook.organization)
        if not plan_limits.get("otp_access", False):
            messages.warning(request, "This notebook doesn't allow shared access.")
            return redirect("labs:labs_dashboard_home")

        now = timezone.now()

        # Buscar OTP vigente, si no existe generarlo
        access_request = (
            NotebookAccessRequest.objects.filter(
                notebook=notebook, email=email, expires_at__gt=now
            )
            .order_by("-requested_at")
            .first()
        )

        if not access_request:
            generate_and_send_lab_otp(
                email=email,
                notebook=notebook,
                expires_after_hours=notebook.expires_after_hours,
            )
            messages.success(request, "🔐 An OTP has been sent to your email.")

        else:
            messages.info(request, "You already have a valid OTP in your email.")

        # Redirigir directamente a verify_otp
        verify_url = reverse("labs:lab_notebook_verify_otp", args=[notebook.slug])
        return HttpResponseRedirect(f"{verify_url}?email={email}")

    return render(request, "labs/public/enter_email.html", {"notebook": notebook})


def lab_notebook_verify_otp_view(request, notebook_slug):
    notebook = get_object_or_404(LabNotebook, slug=notebook_slug, active=True)

    # 🔒 Bloquear verificación si el plan no permite OTP
    plan_limits = get_plan_limits(notebook.organization)
    if not plan_limits.get("otp_access", False):
        return HttpResponseForbidden("Shared access is not enabled for this notebook.")

    email = request.GET.get("email", "").strip().lower()
    error = None

    if request.method == "POST":
        submitted_otp = request.POST.get("otp", "").strip()
        now = timezone.now()

        access_request = (
            NotebookAccessRequest.objects.filter(
                notebook=notebook,
                email=email,
                otp_code=submitted_otp,
                expires_at__gt=now,
            )
            .order_by("-requested_at")
            .first()
        )

        if access_request:
            access_request.is_verified = True
            access_request.save()

            # Guardar token en la sesión
            if "verified_notebook_tokens" not in request.session:
                request.session["verified_notebook_tokens"] = []

            request.session["verified_notebook_tokens"].append(
                str(access_request.session_token)
            )
            request.session.modified = True

            messages.success(request, "✅ OTP verified. Access granted.")
            return redirect("labs:lab_notebook_detail", notebook_slug=notebook.slug)
        else:
            error = "Invalid or expired OTP."

    return render(
        request,
        "labs/public/verify_otp.html",
        {
            "notebook": notebook,
            "email": email,
            "error": error,
        },
    )


@require_POST
def lab_notebook_resend_otp(request, notebook_slug):
    notebook = get_object_or_404(LabNotebook, slug=notebook_slug, active=True)
    email = request.POST.get("email", "").strip().lower()

    if not email:
        return JsonResponse({"success": False, "error": "Missing email"}, status=400)

    # 🚫 Validar plan: sin acceso si la organización no tiene otp_access
    plan_limits = get_plan_limits(notebook.organization)
    if not plan_limits.get("otp_access", False):
        return JsonResponse(
            {
                "success": False,
                "error": "This notebook doesn't allow shared access.",
            },
            status=403,
        )

    now = timezone.now()
    one_min_ago = now - timedelta(seconds=60)
    recent_requests = NotebookAccessRequest.objects.filter(
        notebook=notebook,
        email=email,
        requested_at__gte=one_min_ago,
    )

    if recent_requests.exists():
        return JsonResponse(
            {
                "success": False,
                "error": "Too many requests. Please wait before requesting another OTP.",
            },
            status=429,
        )

    active_unverified = (
        NotebookAccessRequest.objects.filter(
            notebook=notebook,
            email=email,
            is_verified=False,
            expires_at__gt=now,
        )
        .order_by("-requested_at")
        .first()
    )

    if active_unverified:
        send_lab_otp_email(
            email=email, otp_code=active_unverified.otp_code, notebook=notebook
        )
        return JsonResponse({"success": True, "reused": True})

    otp_code = generate_otp_code()
    expires_at = now + timedelta(hours=24)

    NotebookAccessRequest.objects.filter(
        notebook=notebook, email=email, is_verified=False
    ).delete()

    access_request = NotebookAccessRequest.objects.create(
        notebook=notebook,
        email=email,
        otp_code=otp_code,
        expires_at=expires_at,
    )

    send_lab_otp_email(email=email, otp_code=otp_code, notebook=notebook)

    return JsonResponse({"success": True, "reused": False})


@login_required(login_url="labs:labs_login")
@labs_only
def edit_notebook_access_view(request, notebook_slug):
    notebook = get_object_or_404(
        LabNotebook.objects.select_related("organization", "created_by"),
        slug=notebook_slug,
    )

    user = request.user
    is_owner = notebook.organization.owner == user
    is_creator = notebook.created_by == user
    if not (is_owner or is_creator):
        raise PermissionDenied("You do not have permission to edit this notebook.")

    if request.method == "POST":
        form = NotebookAccessForm(request.POST, instance=notebook)
        if form.is_valid():
            plan_limits = get_plan_limits(notebook.organization)
            if not plan_limits.get("otp_access"):
                # Forzar limpieza de los emails si el plan no permite OTP
                form.instance.allowed_emails = []
            form.save()
            messages.success(request, "✅ Access settings updated.")
            return redirect("labs:lab_notebook_detail", notebook_slug=notebook.slug)
    else:
        form = NotebookAccessForm(instance=notebook)

    # Gather unique allowed emails from other notebooks in the org
    all_emails = (
        LabNotebook.objects.filter(organization=notebook.organization)
        .exclude(id=notebook.id)
        .values_list("allowed_emails", flat=True)
    )

    email_suggestions = sorted(
        set(email.lower() for sublist in all_emails if sublist for email in sublist)
    )
    email_suggestions_json = json.dumps(email_suggestions)

    return render(
        request,
        "labs/dashboard/edit_access.html",
        {
            "notebook": notebook,
            "form": form,
            "email_suggestions_json": email_suggestions_json,
            "otp_access_allowed": get_plan_limits(notebook.organization).get(
                "otp_access", False
            ),
        },
    )
