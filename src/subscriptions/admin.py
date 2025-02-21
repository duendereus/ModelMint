from django.contrib import admin
from subscriptions.models import (
    Subscription,
    UserSubscription,
    SubscriptionPrice,
    SubscriptionFeature,
)


class SubscriptionFeatureInline(admin.TabularInline):
    """
    Inline admin for managing Subscription Features within the Subscription admin page.
    """

    model = SubscriptionFeature
    extra = 1


class SubscriptionPriceInline(admin.StackedInline):
    model = SubscriptionPrice
    readonly_fields = ["stripe_id"]
    can_delete = False
    extra = 0


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    inlines = [SubscriptionPriceInline, SubscriptionFeatureInline]
    list_display = ("name",)
    search_fields = ("name", "groups")
    list_filter = ("groups",)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "subscription", "active")
    search_fields = ("user", "subscription")
    list_filter = ("subscription", "active")
