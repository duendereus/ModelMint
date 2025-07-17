from django.urls import path
from . import views
from labs.views.accounts_views import (
    labs_register_view,
    labs_activate_account_view,
    labs_password_reset_request,
    labs_password_reset_confirm,
    labs_login_view,
    labs_logout_view,
    labs_profile_view,
    labs_organization_profile_view,
)
from labs.views.landing_views import labs_landing_view
from labs.views.subscription_views import (
    labs_organization_subscription_view,
    labs_organization_subscription_cancel_view,
    labs_pricing_view,
    labs_organization_subscription_restore_view,
)
from labs.views.dashboard_views import (
    dashboard_home_labs_view,
    dashboard_my_notebooks_view,
    lab_notebook_upload_view,
    upload_new_version_view,
    lab_preview_notebook_view,
    lab_notebook_detail_view,
    download_pdf_notebook,
    delete_lab_notebook,
    lab_notebook_enter_email_view,
    lab_notebook_verify_otp_view,
    lab_notebook_resend_otp,
    edit_notebook_access_view,
)
from labs.views.organization_views import (
    invite_lab_member,
    labs_organization_users,
    delete_lab_member_view,
    edit_lab_member_view,
)
from labs.views.checkout_views import (
    labs_checkout_redirect_view,
    labs_checkout_finalize,
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
    path("my-notebooks/", dashboard_my_notebooks_view, name="my_notebooks"),
    path("upload/", lab_notebook_upload_view, name="lab_notebook_upload"),
    # profile
    path("profile/", labs_profile_view, name="labs_profile"),
    path(
        "organization/profile/",
        labs_organization_profile_view,
        name="labs_organization_profile",
    ),
    # org views
    path("invite-member/", invite_lab_member, name="invite_lab_member"),
    path(
        "organization/users/", labs_organization_users, name="labs_organization_users"
    ),
    path(
        "members/<int:member_id>/delete/",
        delete_lab_member_view,
        name="labs_delete_member",
    ),
    path(
        "members/<int:member_id>/edit/", edit_lab_member_view, name="labs_edit_member"
    ),
    path(
        "notebooks/<int:notebook_id>/upload-version/",
        upload_new_version_view,
        name="lab_notebook_upload_version",
    ),
    path(
        "notebook-preview/<slug:notebook_slug>/",
        lab_preview_notebook_view,
        name="lab_preview_notebook",
    ),
    path(
        "notebooks/<slug:notebook_slug>/details/",
        lab_notebook_detail_view,
        name="lab_notebook_detail",
    ),
    path(
        "notebooks/<slug:notebook_slug>/pdf/",
        download_pdf_notebook,
        name="lab_notebook_pdf",
    ),
    path(
        "notebooks/<slug:notebook_slug>/delete/",
        delete_lab_notebook,
        name="delete_lab_notebook",
    ),
    path(
        "notebooks/<slug:notebook_slug>/enter-email/",
        lab_notebook_enter_email_view,
        name="lab_notebook_enter_email",
    ),
    path(
        "notebooks/verify-otp/<slug:notebook_slug>/",
        lab_notebook_verify_otp_view,
        name="lab_notebook_verify_otp",
    ),
    path(
        "notebooks/<slug:notebook_slug>/resend-otp/",
        lab_notebook_resend_otp,
        name="lab_notebook_resend_otp",
    ),
    path(
        "notebooks/<slug:notebook_slug>/access-settings/",
        edit_notebook_access_view,
        name="lab_notebook_access",
    ),
    # subscription action views
    path(
        "subscription/",
        labs_organization_subscription_view,
        name="labs_organization_subscription",
    ),
    path(
        "subscription/cancel/",
        labs_organization_subscription_cancel_view,
        name="labs_organization_subscription_cancel",
    ),
    path(
        "labs/subscription/restore/",
        labs_organization_subscription_restore_view,
        name="labs_organization_subscription_restore",
    ),
    # checkout views
    path(
        "subscription/checkout/<int:price_id>/",
        labs_checkout_redirect_view,
        name="labs_checkout_redirect",
    ),
    path(
        "subscription/checkout/complete/",
        labs_checkout_finalize,
        name="labs_checkout_finalize",
    ),
]
