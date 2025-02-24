from django.urls import path
from . import views

app_name = "checkouts"

urlpatterns = [
    path(
        "checkout/sub-price/<int:price_id>/",
        views.product_price_redirect_view,
        name="sub-price-checkout",
    ),
    path("checkout/start/", views.checkout_redirect_view, name="stripe-checkout-start"),
    path("checkout/success/", views.checkout_finalize_view, name="stripe-checkout-end"),
]
