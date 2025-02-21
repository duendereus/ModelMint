import helpers.billing
from django.db import models
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model

User = get_user_model()

SUBSCRIPTION_PERMISSIONS = [
    ("pro", "Pro Perm"),  # subscriptions.pro
    ("basic", "Basic Perm"),  # subscriptions.basic
]


class Subscription(models.Model):
    """
    Subscription Plan = Stripe Product
    """

    name = models.CharField(max_length=120)
    subtitle = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)
    groups = models.ManyToManyField(Group)
    permissions = models.ManyToManyField(
        Permission,
        limit_choices_to={
            "content_type__app_label": "subscriptions",
            "codename__in": [x[0] for x in SUBSCRIPTION_PERMISSIONS],
        },
    )
    stripe_id = models.CharField(max_length=120, null=True, blank=True)
    order = models.IntegerField(default=-1, help_text="Ordering on Django pricing page")
    featured = models.BooleanField(
        default=True, help_text="Featured on Django pricing page"
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


class UserSubscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True
    )
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user} - {self.subscription}"
