from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path("upload/generate-url/", views.generate_presigned_put_url, name="generate_presigned_post"),
    path("upload/confirm/", views.confirm_upload, name="confirm_upload"),
    path("upload/submit/", views.submit_upload_metadata, name="submit_upload_metadata"),
    path("data-uploads/", views.data_upload_list, name="data_upload_list"),
    path(
        "data-uploads/<int:upload_id>/",
        views.data_upload_detail,
        name="data_upload_detail",
    ),
]
