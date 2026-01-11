"""
Custom template tags for accounting templates.
"""
from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up a value in a dictionary.
    Usage: {{ my_dict|lookup:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key, None)
