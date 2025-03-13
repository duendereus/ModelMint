from django.urls import path, include
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path("invite-member/", views.invite_member, name="invite_member"),
    path("analytics/", include("analytics.urls", namespace="analytics")),
]
