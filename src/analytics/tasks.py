from celery import shared_task
from django.core.files.base import ContentFile
from .models import DataUpload
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def save_uploaded_file(
    title, file_name, content_type, job_instructions, user_id, file_data
):
    """
    Celery task to create a DataUpload record in the background.
    """

    try:
        user = User.objects.get(id=user_id)

        # ✅ Determine the organization for the user
        organization = None
        if hasattr(user, "owned_organization") and user.owned_organization:
            organization = user.owned_organization
        else:
            membership = user.organization_memberships.first()
            if membership:
                organization = membership.organization

        if not organization:
            return f"Error: User {user.email} does not belong to an organization."

        # ✅ Create a new DataUpload instance (this will use upload_to)
        upload = DataUpload(
            title=title,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
        )

        # ✅ Assign the file and save it (this triggers upload_to!)
        upload.file.save(file_name, ContentFile(file_data, name=file_name))

        upload.save()  # ✅ Save the model after file is stored

        return f"File '{file_name}' uploaded successfully for user {user.email}."

    except User.DoesNotExist:
        return f"Error: User with ID {user_id} not found."
    except Exception as e:
        return f"Error processing upload: {str(e)}"
