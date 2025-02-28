from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
]
