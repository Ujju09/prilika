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


@register.filter
def inr(value):
    """
    Format a number in Indian numbering style with ₹ prefix.
    Usage: {{ amount|inr }}  →  ₹1,23,450.00
    Handles negative values (prefix with −) and None / zero gracefully.
    """
    try:
        from decimal import Decimal
        num = Decimal(str(value))
    except Exception:
        return '₹0.00'

    negative = num < 0
    num = abs(num)

    # Split integer and decimal parts
    integer_part, _, decimal_part = str(num.quantize(Decimal('0.01'))).partition('.')

    # Indian grouping: last 3 digits, then groups of 2
    if len(integer_part) > 3:
        last_three = integer_part[-3:]
        rest = integer_part[:-3]
        # Group the rest in pairs from the right
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        integer_part = ','.join(groups) + ',' + last_three

    sign = '−' if negative else ''
    return f'{sign}₹{integer_part}.{decimal_part}'
