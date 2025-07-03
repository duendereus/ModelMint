from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path("upload/", views.upload_data, name="upload_data"),
    path("reports/request/", views.request_report_view, name="request_report"),
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
        "reports/view/<int:report_id>/",
        views.report_detail_view,
        name="report_detail_view",
    ),
    path(
        "reports/download-pdf/<int:report_id>/",
        views.download_pdf_report,
        name="download_pdf_report",
    ),
    path("get-datasets/", views.get_available_datasets, name="get_datasets"),
    path("staff/datasets/", views.staff_dataset_list_view, name="staff_dataset_list"),
    path(
        "staff/datasets/<int:dataset_id>/mark-processed/",
        views.mark_dataset_as_processed,
        name="mark_dataset_as_processed",
    ),
    path(
        "staff/reports/<int:report_id>/process/",
        views.staff_process_report_view,
        name="staff_process_report",
    ),
    path(
        "staff/reports/<int:report_id>/preview/",
        views.staff_preview_report_view,
        name="staff_preview_report_by_report",
    ),
    path(
        "staff/reports/dynamic/<int:report_id>/process/",
        views.staff_process_dynamic_dashboard_view,
        name="staff_process_dynamic_dashboard",
    ),
    path(
        "staff/reports/<int:report_id>/dashboard-config/",
        views.get_dashboard_config,
        name="get_dashboard_config",
    ),
    path(
        "staff/preview/dynamic/<int:report_id>/",
        views.staff_preview_dynamic_dashboard_view,
        name="staff_preview_dynamic_dashboard",
    ),
    path(
        "staff/confirm/dynamic/<int:report_id>/",
        views.confirm_dynamic_dashboard_metric,
        name="confirm_dynamic_dashboard_metric",
    ),
    path(
        "reports/dynamic/<int:report_id>/",
        views.dynamic_report_detail_view,
        name="dynamic_report_detail_view",
    ),
    path(
        "reports/dynamic/chart-data/<int:report_id>/",
        views.get_chart_data,
        name="get_chart_data",
    ),
]
