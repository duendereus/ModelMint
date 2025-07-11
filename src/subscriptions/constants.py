PLAN_LIMITS = {
    "Starter Plan": {
        "max_uploads_per_month": 1,
        "max_members": 3,
        "max_reports": 3,  # ✅ Limit processed DataUploads
        "allow_pdf_download": False,
        "turnaround_days": 5,
    },
    "Business Plan": {
        "max_uploads_per_month": 4,
        "max_members": 10,
        "max_reports": 10,
        "allow_pdf_download": True,
        "turnaround_days": 3,
    },
    "Enterprise Plan": {
        "max_uploads_per_month": float("inf"),
        "max_members": float("inf"),
        "max_reports": float("inf"),
        "allow_pdf_download": True,
        "turnaround_days": 1,
    },
}

LAB_PLAN_LIMITS = {
    "Free": {
        "max_reports": 1,
        "max_members": 1,
        "otp_access": False,
        "allow_pdf_download": False,
        "branding": "none",
        "max_versions_per_notebook": 1,
    },
    "Solo": {
        "max_reports": 5,
        "max_members": 1,
        "otp_access": False,
        "allow_pdf_download": False,
        "branding": "none",
        "max_versions_per_notebook": 5,
    },
    "Team": {
        "max_reports": 10,
        "max_members": 3,
        "otp_access": True,
        "allow_pdf_download": True,
        "branding": "partial",
        "max_versions_per_notebook": 15,
    },
    "Org Pro": {
        "max_reports": float("inf"),
        "max_members": 10,
        "otp_access": True,
        "allow_pdf_download": True,
        "branding": "full",
        "max_versions_per_notebook": float("inf"),
    },
}
