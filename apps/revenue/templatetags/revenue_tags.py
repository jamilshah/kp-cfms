from django import template

register = template.Library()

@register.filter
def sum_field(value, arg):
    """
    Sums the values of a specific field (arg) in a list of dictionaries or objects (value).
    Usage: {{ list|sum_field:"field_name" }}
    """
    if not value:
        return 0
    
    total = 0
    for item in value:
        # Check if item is a dictionary
        if isinstance(item, dict):
            try:
                val = item.get(arg, 0)
                if val is None:
                    val = 0
                total += float(val)
            except (ValueError, TypeError):
                pass
        else:
            # Assume item is an object
            try:
                val = getattr(item, arg, 0)
                if val is None:
                    val = 0
                total += float(val)
            except (ValueError, TypeError, AttributeError):
                pass
    return total
