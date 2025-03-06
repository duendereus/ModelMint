from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path("data-uploads/", views.data_upload_list, name="data_upload_list"),
    path(
        "data-uploads/<int:upload_id>/",
        views.data_upload_detail,
        name="data_upload_detail",
    ),
]
