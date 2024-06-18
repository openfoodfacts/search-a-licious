from typing import Literal, Tuple

BoolOperator = Literal["+"] | Literal["-"]


def split_sort_by_sign(sort_by: str) -> Tuple[BoolOperator, str]:
    """Not really a validator, but a helper to split a sort_by string
    into it's negative sign and the actual field name.
    """
    if negative_operator := sort_by.startswith("-"):
        sort_by = sort_by[1:]
    return "-" if negative_operator else "+", sort_by
