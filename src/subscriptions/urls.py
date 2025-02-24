from django.urls import path
from . import views

app_name = "subscriptions"

urlpatterns = [
    path("pricing/", views.subscription_price_view, name="pricing"),
    path("accounts/billing/", views.user_subscription_view, name="user_subscription"),
    path(
        "accounts/billing/cancel",
        views.user_subscription_cancel_view,
        name="user_subscription_cancel",
    ),
]
