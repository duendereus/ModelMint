from django.urls import path
from . import views

app_name = "subscriptions"

urlpatterns = [
    path("pricing/", views.subscription_price_view, name="pricing"),
    path(
        "dashboard/organization/<int:org_id>/",
        views.organization_subscription_view,
        name="organization_subscription",
    ),
    path(
        "dashboard/organization/<int:org_id>/cancel/",
        views.organization_subscription_cancel_view,
        name="organization_subscription_cancel",
    ),
]
