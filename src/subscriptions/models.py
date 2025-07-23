import datetime
import helpers.billing
from django.db import models
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from accounts.models import Organization

User = get_user_model()

SUBSCRIPTION_PERMISSIONS = [
    ("starter", "Starter Plan Access"),  # subscriptions.starter
    ("business", "Business Plan Access"),  # subscriptions.business
    ("enterprise", "Enterprise Plan Access"),  # subscriptions.enterprise
]


class Subscription(models.Model):
    """
    Subscription Plan = Stripe Product
    """

    name = models.CharField(max_length=120)
    subtitle = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    groups = models.ManyToManyField(Group, blank=True)
    permissions = models.ManyToManyField(
        Permission,
        limit_choices_to={
            "content_type__app_label": "subscriptions",
            "codename__in": [x[0] for x in SUBSCRIPTION_PERMISSIONS],
        },
        blank=True,
    )
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    order = models.IntegerField(default=-1, help_text="Ordering on Django pricing page")
    featured = models.BooleanField(
        default=True, help_text="Featured on Django pricing page"
    )
    is_for_labs = models.BooleanField(
        default=False, help_text="Show on Labs landing page"
    )
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = SUBSCRIPTION_PERMISSIONS
        ordering = ["order", "featured", "-updated"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.stripe_id:
            stripe_id = helpers.billing.create_product(
                name=self.name, metadata={"subscription_plan_id": self.id}, raw=False
            )
            self.stripe_id = stripe_id
        super().save(*args, **kwargs)


class SubscriptionFeature(models.Model):
    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="features"
    )
    description = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.subscription.name} - {self.description}"


class SubscriptionPrice(models.Model):
    """
    Subscription Price = Stripe Price
    """

    class IntervalChoices(models.TextChoices):
        MONTHLY = "month", "Monthly"
        # YEARLY = "year", "Yearly"

    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True)
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    interval = models.CharField(
        max_length=120, default=IntervalChoices.MONTHLY, choices=IntervalChoices.choices
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, default=99.99)
    order = models.IntegerField(default=-1, help_text="Ordering on Django pricing page")
    featured = models.BooleanField(
        default=True, help_text="Featured on Django pricing page"
    )
    updated = models.DateTimeField(auto_now=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["subscription__order", "order", "featured", "-updated"]

    @property
    def get_checkout_url(self):
        if self.subscription and self.subscription.is_for_labs:
            return reverse("labs:labs_checkout_redirect", kwargs={"price_id": self.id})
        return reverse("checkouts:sub-price-checkout", kwargs={"price_id": self.id})

    @property
    def display_sub_name(self):
        if not self.subscription:
            return "Plan"
        return self.subscription.name

    @property
    def display_sub_subtitle(self):
        if not self.subscription:
            return "Plan"
        return self.subscription.subtitle

    @property
    def stripe_currency(self):
        return "usd"

    @property
    def stripe_price(self):
        """
        remove decimal places
        """
        return int(self.price * 100)

    @property
    def product_stripe_id(self):
        if not self.subscription:
            return None
        return self.subscription.stripe_id

    @property
    def features_list(self):
        if self.subscription:
            return [f.description for f in self.subscription.features.all()]
        return []

    def save(self, *args, **kwargs):
        if not self.stripe_id and self.product_stripe_id is not None:
            stripe_id = helpers.billing.create_price(
                currency=self.stripe_currency,
                unit_amount=self.stripe_price,
                interval=self.interval,
                product=self.product_stripe_id,
                metadata={"subscription_plan_price_id": self.id},
                raw=False,
            )
            self.stripe_id = stripe_id
        super().save(*args, **kwargs)
        if self.featured and self.subscription:
            qs = SubscriptionPrice.objects.filter(
                subscription=self.subscription, interval=self.interval
            ).exclude(id=self.id)
            qs.update(featured=False)

    def __str__(self):
        return f"{self.subscription} - {self.price}"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    TRIALING = "trialing", "Trialing"
    INCOMPLETE = "incomplete", "Incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete Expired"
    PAST_DUE = "past_due", "Past Due"
    CANCELED = "canceled", "Canceled"
    UNPAID = "unpaid", "Unpaid"
    PAUSED = "paused", "Paused"


class OrganizationSubscriptionQuerySet(models.QuerySet):
    def by_active_trialing(self):
        return self.filter(
            status__in=[SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
        )

    def by_days_left(self, days_left=7):
        now = timezone.now()
        in_n_days = now + datetime.timedelta(days=days_left)
        day_start = in_n_days.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = in_n_days.replace(hour=23, minute=59, second=59, microsecond=59)
        return self.filter(
            current_period_end__gte=day_start, current_period_end__lte=day_end
        )

    def by_days_ago(self, days_ago=3):
        now = timezone.now()
        in_n_days = now - datetime.timedelta(days=days_ago)
        day_start = in_n_days.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = in_n_days.replace(hour=23, minute=59, second=59, microsecond=59)
        return self.filter(
            current_period_end__gte=day_start, current_period_end__lte=day_end
        )

    def by_range(self, days_start=7, days_end=120, verbose=True):
        now = timezone.now()
        start = now + datetime.timedelta(days=days_start)
        end = now + datetime.timedelta(days=days_end)
        range_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        range_end = end.replace(hour=23, minute=59, second=59, microsecond=59)
        if verbose:
            print(f"[Range] {range_start} to {range_end}")
        return self.filter(
            current_period_end__gte=range_start, current_period_end__lte=range_end
        )


class OrganizationSubscriptionManager(models.Manager):
    def get_queryset(self):
        return OrganizationSubscriptionQuerySet(self.model, using=self._db)

    def by_active_trialing(self):
        return self.get_queryset().by_active_trialing()


class OrganizationSubscription(models.Model):
    """
    Organization-based subscription, replacing user-level subscriptions.
    """

    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name="subscription"
    )
    subscription = models.ForeignKey(
        "subscriptions.Subscription", on_delete=models.SET_NULL, null=True, blank=True
    )
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    active = models.BooleanField(default=True)
    user_cancelled = models.BooleanField(default=False)
    original_period_start = models.DateTimeField(
        auto_now=False, auto_now_add=False, blank=True, null=True
    )
    current_period_start = models.DateTimeField(
        auto_now=False, auto_now_add=False, blank=True, null=True
    )
    current_period_end = models.DateTimeField(
        auto_now=False, auto_now_add=False, blank=True, null=True
    )
    cancel_at_period_end = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    objects = OrganizationSubscriptionManager()

    def get_absolute_url(self):
        if self.organization.type == "lab":
            return reverse("labs:labs_organization_subscription")
        return reverse(
            "subscriptions:organization_subscription",
            kwargs={"org_id": self.organization.id},
        )

    def get_cancel_url(self):
        if self.organization.type == "lab":
            return reverse("labs:labs_organization_subscription_cancel")
        return reverse(
            "subscriptions:organization_subscription_cancel",
            kwargs={"org_id": self.organization.id},
        )

    @property
    def is_active_status(self):
        """
        Considera la suscripción activa si está en estado 'active' o 'trialing',
        o si está programada para cancelarse pero aún no ha llegado su periodo final.
        """
        if self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]:
            return True
        if (
            self.cancel_at_period_end
            and self.current_period_end
            and self.current_period_end > timezone.now()
        ):
            return True
        return False

    @property
    def is_set_to_cancel(self):
        """
        Retorna True si la suscripción está programada
        para cancelarse al final del periodo actual.
        """
        return bool(self.cancel_at_period_end)

    @property
    def plan_name(self):
        if not self.subscription:
            return None
        return self.subscription.name

    def serialize(self):
        return {
            "plan_name": self.plan_name,
            "status": self.status,
            "current_period_start": self.current_period_start,
            "current_period_end": self.current_period_end,
        }

    @property
    def billing_cycle_anchor(self):
        """
        Stripe checkout - delay for new subscriptions
        """
        if not self.current_period_end:
            return None
        return int(self.current_period_end.timestamp())

    def save(self, *args, **kwargs):
        if self.original_period_start is None and self.current_period_start is not None:
            self.original_period_start = self.current_period_start
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization.name} - {self.subscription}"
