from django.urls import path
from . import views

app_name = "landing"

urlpatterns = [
    path("contact/", views.contact, name="contact"),
]
