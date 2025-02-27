from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from accounts.utils import validate_phone_number


class UserManager(BaseUserManager):
    """
    Custom manager for User model with methods to create users and superusers.
    """

    def create_user(
        self, email, username, phone_number=None, password=None, **extra_fields
    ):
        if not email:
            raise ValueError("All users must have an email address.")
        if not username:
            raise ValueError("All users must have a username.")

        email = self.normalize_email(email)
        user = self.model(
            email=email, username=username, phone_number=phone_number, **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        user = self.create_user(
            email=email, username=username, password=password, **extra_fields
        )
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model replacing the default Django user model.
    """

    email = models.EmailField(unique=True)
    phone_number = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        validators=[validate_phone_number],
    )
    username = models.CharField(max_length=50, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)

    # Default Many-to-Many for Permissions and Groups
    groups = models.ManyToManyField(
        "auth.Group",
        verbose_name=_("groups"),
        blank=True,
        related_name="user_groups",
        help_text=_("The groups this user belongs to."),
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        verbose_name=_("user permissions"),
        blank=True,
        related_name="user_permissions",
        help_text=_("Specific permissions for this user."),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.email


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    owner = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="owned_organization"
    )
    users = models.ManyToManyField(User, related_name="organization", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def clean(self):
        """
        Enforce validation rules:
        1. Owner cannot be in `users` list.
        2. A user can only belong to one organization.
        3. A user cannot be both an owner and a member in any organization.
        """
        if self.pk:  # Only enforce rules for existing instances
            for user in self.users.all():
                if user == self.owner:
                    raise ValidationError(
                        f"Owner {user.username} cannot be in the members list."
                    )

                if Organization.objects.exclude(id=self.id).filter(users=user).exists():
                    raise ValidationError(
                        f"User {user.username} is already a member of another organization."
                    )

                if Organization.objects.filter(owner=user).exists():
                    raise ValidationError(
                        f"User {user.username} is already an owner of another organization."
                    )

        if Organization.objects.exclude(id=self.id).filter(owner=self.owner).exists():
            raise ValidationError(
                f"User {self.owner.username} already owns another organization."
            )

    def save(self, *args, **kwargs):
        """
        Save the Organization instance before adding users.
        """
        is_new = not self.pk
        super().save(*args, **kwargs)  # Save first to generate an ID

        if not is_new:
            self.clean()  # Validate constraints
