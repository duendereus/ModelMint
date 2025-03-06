from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Retrieves an item from a dictionary safely in Django templates.
    Example usage in template: {{ my_dict|get_item:"my_key" }}
    """
    return dictionary.get(key, "")
