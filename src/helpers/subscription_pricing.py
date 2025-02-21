from subscriptions.models import SubscriptionPrice


def get_subscription_prices(interval="month"):
    """
    Retrieve subscription prices based on the selected interval.
    """
    qs = SubscriptionPrice.objects.filter(featured=True).select_related("subscription")
    inv_mo = SubscriptionPrice.IntervalChoices.MONTHLY
    object_list = qs.filter(interval=inv_mo)
    active = inv_mo

    return object_list, active
