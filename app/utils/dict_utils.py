def deep_get(d, *keys, default=None):
    """
    Robustly get a value from a nested dictionary.
    """
    value = d
    try:
        for key in keys:
            value = value[key]
        return value
    # we only catch KeyError, the rest may hide bugs
    except KeyError:
        return default
