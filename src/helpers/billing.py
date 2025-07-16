import stripe
from decouple import config
from . import date_utils

DEBUG = config("DEBUG", default=False, cast=bool)
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="", cast=str)

if "sk_test" in STRIPE_SECRET_KEY and not DEBUG:
    raise ValueError("Invalid Stripe key for production.")

stripe.api_key = STRIPE_SECRET_KEY


def serialize_subscription_data(subscription_response):
    """
    Convert Stripe subscription response into a structured dictionary.
    """
    status = getattr(subscription_response, "status", None)
    current_period_start = getattr(subscription_response, "current_period_start", None)
    current_period_end = getattr(subscription_response, "current_period_end", None)
    cancel_at_period_end = getattr(subscription_response, "cancel_at_period_end", False)

    return {
        "current_period_start": (
            date_utils.timestamp_as_datetime(current_period_start)
            if current_period_start
            else None
        ),
        "current_period_end": (
            date_utils.timestamp_as_datetime(current_period_end)
            if current_period_end
            else None
        ),
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
    }


def create_customer(organization_name="", email="", metadata={}, raw=False):
    """
    Creates a Stripe customer for an organization.
    """
    response = stripe.Customer.create(
        name=organization_name,
        email=email,
        metadata=metadata,
    )
    return response if raw else response.id


def create_product(name="", metadata={}, raw=False):
    """
    Creates a new Stripe product.
    """
    response = stripe.Product.create(
        name=name,
        metadata=metadata,
    )
    return response if raw else response.id


def create_price(
    currency="usd",
    unit_amount="9999",
    interval="month",
    product=None,
    metadata={},
    raw=False,
):
    """
    Creates a new Stripe price for a product.
    """
    if product is None:
        return None
    response = stripe.Price.create(
        currency=currency,
        unit_amount=unit_amount,
        recurring={"interval": interval},
        product=product,
        metadata=metadata,
    )
    return response if raw else response.id


def start_checkout_session(
    customer_id, success_url="", cancel_url="", price_stripe_id="", raw=True
):
    """
    Starts a Stripe checkout session for an organization.
    """
    if not success_url.endswith("?session_id={CHECKOUT_SESSION_ID}"):
        success_url = f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}"

    response = stripe.checkout.Session.create(
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price_stripe_id, "quantity": 1}],
        mode="subscription",
    )
    return response if raw else response.url


def get_checkout_session(stripe_id, raw=True):
    """
    Retrieves a Stripe checkout session by ID.
    """
    response = stripe.checkout.Session.retrieve(stripe_id)
    return response if raw else response.url


def get_subscription(stripe_id, raw=True):
    """
    Retrieves a Stripe subscription by ID.
    """
    response = stripe.Subscription.retrieve(stripe_id)
    return response if raw else serialize_subscription_data(response)


def get_customer_active_subscriptions(customer_stripe_id):
    """
    Retrieves all active subscriptions for an organization.
    """
    response = stripe.Subscription.list(customer=customer_stripe_id, status="active")
    return response


def cancel_subscription(
    stripe_id, reason="", feedback="other", cancel_at_period_end=False, raw=True
):
    """
    Cancels an organization's subscription on Stripe.
    """
    if cancel_at_period_end:
        response = stripe.Subscription.modify(
            stripe_id,
            cancel_at_period_end=cancel_at_period_end,
            cancellation_details={"comment": reason, "feedback": feedback},
        )
    else:
        response = stripe.Subscription.cancel(
            stripe_id, cancellation_details={"comment": reason, "feedback": feedback}
        )
    return response if raw else serialize_subscription_data(response)


def get_checkout_customer_plan(session_id):
    """
    Retrieves the checkout session and links it to an organization instead of a user.
    """
    checkout_r = get_checkout_session(session_id, raw=True)
    customer_id = checkout_r.customer
    sub_stripe_id = checkout_r.subscription

    # ✅ Obtener el objeto real de Stripe (no como dict)
    sub_obj = stripe.Subscription.retrieve(sub_stripe_id)

    try:
        price_id = sub_obj["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Could not retrieve price ID from subscription items.")

    subscription_data = serialize_subscription_data(sub_obj)

    return {
        "customer_id": customer_id,
        "plan_id": price_id,
        "sub_stripe_id": sub_stripe_id,
        **subscription_data,
    }


def restore_subscription(stripe_id, raw=True):
    """
    Reverts a subscription cancellation (cancel_at_period_end = False).
    """
    response = stripe.Subscription.modify(
        stripe_id,
        cancel_at_period_end=False,
    )
    return response if raw else serialize_subscription_data(response)
