"""
Custom template filters for CFMS.
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='currency')
def currency(value):
    """
    Format number with thousand separators and 2 decimal places.
    
    Usage: {{ amount|currency }}
    Result: 1,234,567.89
    """
    try:
        if value is None:
            return '0.00'
        
        # Convert to Decimal for precise formatting
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        
        # Format with commas and 2 decimal places
        return '{:,.2f}'.format(value)
    except (ValueError, TypeError, Decimal.InvalidOperation):
        return value


@register.filter(name='intcomma')
def intcomma(value):
    """
    Format integer with thousand separators.
    
    Usage: {{ count|intcomma }}
    Result: 1,234,567
    """
    try:
        if value is None:
            return '0'
        return '{:,}'.format(int(value))
    except (ValueError, TypeError):
        return value


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Access dictionary item by key in templates.
    
    Usage: {{ my_dict|get_item:key_var }}
    Result: value from dictionary
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
