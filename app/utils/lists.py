import itertools


def batch(iterable, size=100):
    """Batching utility"""
    data = []
    for item in iterable:
        data.append(item)
        if len(data) >= size:
            yield data
            data = []
    if data:
        yield data


def first(iterable, default=None):
    return (list(itertools.islice(iterable, 1)) + [default])[0]
