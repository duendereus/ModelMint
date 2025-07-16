from storages.backends.s3boto3 import S3Boto3Storage


class OrgLogoStorage(S3Boto3Storage):
    """Storage class for organization logos (public)."""

    location = "org_logos"
    file_overwrite = False
