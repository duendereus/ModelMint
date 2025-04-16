from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path("upload/generate-url/", views.generate_presigned_post, name="generate_presigned_post"),
    path("upload/confirm/", views.confirm_upload, name="confirm_upload"),
    path(
        "upload/initiate-multipart-upload/", 
        views.initiate_multipart_upload, 
        name="initiate_multipart_upload"),
    path(
        "upload/generate-part-url/", 
        views.generate_part_presigned_url, 
        name="generate_part_presigned_url"),
    path(
        "upload/complete-multipart-upload/", 
        views.complete_multipart_upload, 
        name="complete_multipart_upload"),
    path("data-uploads/", views.data_upload_list, name="data_upload_list"),
    path(
        "data-uploads/<int:upload_id>/",
        views.data_upload_detail,
        name="data_upload_detail",
    ),
    path(
        "data-uploads/download-pdf/<int:upload_id>/", 
        views.download_pdf_report,
        name="download_pdf_report"),
]
