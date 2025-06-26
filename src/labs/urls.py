from django.urls import path
from . import views
from labs.views.accounts_views import (
    labs_register_view,
    labs_activate_account_view,
    labs_login_view,
)
from labs.views.landing_views import labs_landing_view
from labs.views.subscription_views import labs_pricing_view

app_name = "labs"

urlpatterns = [
    path("", labs_landing_view, name="labs_landing"),
    path("pricing/", labs_pricing_view, name="labs_pricing"),
    path("register/", labs_register_view, name="labs_register"),
    path("login/", labs_login_view, name="labs_login"),
    path(
        "activate/<uidb64>/<token>/", labs_activate_account_view, name="labs_activate"
    ),
    # path("labs/enroll/", views.labs_enroll_view, name="labs_enroll"),
]
