from django.urls import path
from . import views
from config.views import labs_landing_view

app_name = "labs"

urlpatterns = [
    path("", labs_landing_view, name="labs_landing"),
    # path("labs/enroll/", views.labs_enroll_view, name="labs_enroll"),
]
