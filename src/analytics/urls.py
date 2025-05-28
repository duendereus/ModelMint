from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path(
        "upload/generate-url/",
        views.generate_presigned_post,
        name="generate_presigned_post",
    ),
    path("upload/confirm/", views.confirm_upload, name="confirm_upload"),
    path(
        "upload/initiate-multipart-upload/",
        views.initiate_multipart_upload,
        name="initiate_multipart_upload",
    ),
    path(
        "upload/generate-part-url/",
        views.generate_part_presigned_url,
        name="generate_part_presigned_url",
    ),
    path(
        "upload/complete-multipart-upload/",
        views.complete_multipart_upload,
        name="complete_multipart_upload",
    ),
    path("reports/", views.report_list_view, name="report_list_view"),
    path(
        "reports/<int:dataset_id>/",
        views.report_detail_view,
        name="report_detail_view",
    ),
    path(
        "reports/download-pdf/<int:upload_id>/",
        views.download_pdf_report,
        name="download_pdf_report",
    ),
    path("get-datasets/", views.get_available_datasets, name="get_datasets"),
    path("staff/datasets/", views.staff_dataset_list_view, name="staff_dataset_list"),
]
