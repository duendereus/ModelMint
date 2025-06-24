from django.urls import path, include
from . import views
from accounts.views import profile_view

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("customize/", views.dashboard_customize, name="customize_dashboard"),
    path(
        "reorder-metrics/",
        views.reorder_dashboard_metrics,
        name="reorder_dashboard_metrics",
    ),
    path("invite-member/", views.invite_member, name="invite_member"),
    path("organization/users/", views.organization_users, name="organization_users"),
    path("profile/", profile_view, name="profile"),
    path("analytics/", include("analytics.urls", namespace="analytics")),
]
