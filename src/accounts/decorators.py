from django.shortcuts import redirect
from accounts.utils import get_user_organization_type
from functools import wraps


def daas_only(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        org_type = get_user_organization_type(request.user)
        if org_type == "lab":
            return redirect("labs:labs_landing")  # o una página de error si prefieres
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def labs_only(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        org_type = get_user_organization_type(request.user)
        if org_type != "lab":
            return redirect(
                "dashboard:dashboard_home"
            )  # o una página de error si prefieres
        return view_func(request, *args, **kwargs)

    return _wrapped_view
