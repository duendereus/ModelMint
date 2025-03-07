import helpers.billing
from django.db import models
from accounts.models import Organization


class OrganizationCustomer(models.Model):
    """
    Organization-level Stripe Customer.
    """

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE)
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    init_email = models.EmailField(blank=True, null=True)
    init_email_confirmed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.organization.name}"

    def save(self, *args, **kwargs):
        """
        Creates a Stripe customer when the organization's email is confirmed.
        """
        if not self.stripe_id and self.init_email_confirmed and self.init_email:
            email = self.init_email
            if email.strip():
                self.stripe_id = helpers.billing.create_customer(
                    organization_name=self.organization.name,
                    email=email,
                    metadata={"organization_id": self.organization.id},
                    raw=False,
                )
        super().save(*args, **kwargs)
