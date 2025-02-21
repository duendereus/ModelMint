import helpers.billing
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# Create your models here.
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    init_email = models.EmailField(blank=True, null=True)
    init_email_confirmed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}"

    def save(self, *args, **kwargs):
        """
        Creates a Stripe customer when the email is confirmed.
        """
        if not self.stripe_id and self.init_email_confirmed and self.init_email:
            email = self.init_email
            if email and email.strip():
                self.stripe_id = helpers.billing.create_customer(
                    email=email,
                    metadata={"user_id": self.user.id, "username": self.user.username},
                    raw=False,
                )
        super().save(*args, **kwargs)
