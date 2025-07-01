from django.urls import path
from . import views
from labs.views.accounts_views import (
    labs_register_view,
    labs_activate_account_view,
    labs_password_reset_request,
    labs_password_reset_confirm,
    labs_login_view,
    labs_logout_view,
)
from labs.views.landing_views import labs_landing_view
from labs.views.subscription_views import labs_pricing_view
from labs.views.dashboard_views import (
    dashboard_home_labs_view,
    lab_notebook_upload_view,
    upload_new_version_view,
)

app_name = "labs"

urlpatterns = [
    path("", labs_landing_view, name="labs_landing"),
    path("pricing/", labs_pricing_view, name="labs_pricing"),
    path("register/", labs_register_view, name="labs_register"),
    path("login/", labs_login_view, name="labs_login"),
    path("logout/", labs_logout_view, name="labs_logout"),
    path(
        "activate/<uidb64>/<token>/", labs_activate_account_view, name="labs_activate"
    ),
    path(
        "password-reset/",
        labs_password_reset_request,
        name="labs_password_reset_request",
    ),
    path(
        "reset/<uidb64>/<token>/",
        labs_password_reset_confirm,
        name="labs_password_reset_confirm",
    ),
    path("home/", dashboard_home_labs_view, name="labs_dashboard_home"),
    path("upload/", lab_notebook_upload_view, name="lab_notebook_upload"),
    path(
        "notebooks/<int:notebook_id>/upload-version/",
        upload_new_version_view,
        name="lab_notebook_upload_version",
    ),
]
