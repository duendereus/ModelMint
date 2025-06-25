from django.contrib import admin
from subscriptions.models import (
    Subscription,
    OrganizationSubscription,
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
    list_display = ("name", "active", "featured", "is_for_labs")
    list_filter = ["is_for_labs", "active", "featured"]
    search_fields = ("name", "groups")
    list_filter = ("groups",)


@admin.register(OrganizationSubscription)
class OrganizationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("organization", "subscription", "active")
    search_fields = ("organization", "subscription")
    list_filter = ("subscription", "active")
