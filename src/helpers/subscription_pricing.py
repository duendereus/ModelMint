from subscriptions.models import SubscriptionPrice


def get_subscription_prices(interval="month", for_labs=False):
    """
    Retrieve subscription prices based on the selected interval.
    """
    qs = SubscriptionPrice.objects.filter(
        featured=True, subscription__is_for_labs=for_labs
    ).select_related("subscription")

    inv_mo = SubscriptionPrice.IntervalChoices.MONTHLY
    object_list = qs.filter(interval=inv_mo)
    active = inv_mo

    return object_list, active
