from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def staff_required(view_func):
    """
    Ensures the user is authenticated and is_staff.
    """

    @user_passes_test(lambda u: u.is_authenticated and u.is_staff)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped_view
