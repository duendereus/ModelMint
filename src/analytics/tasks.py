from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from .models import DataUpload
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task
def test_task():
    return "Celery is working!"


@shared_task
def save_uploaded_file(title, file_data, file_name, job_instructions, user_id):
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

        # ✅ Save the file in storage asynchronously
        file_path = f"uploads/{organization.id}/{file_name}"
        default_storage.save(file_path, ContentFile(file_data))

        # ✅ Create the DataUpload object
        upload = DataUpload.objects.create(
            title=title,
            file=file_path,
            job_instructions=job_instructions,
            uploaded_by=user,
            organization=organization,
        )

        return f"File '{file_name}' uploaded successfully for user {user.email}."

    except User.DoesNotExist:
        return f"Error: User with ID {user_id} not found."
    except Exception as e:
        return f"Error processing upload: {str(e)}"
