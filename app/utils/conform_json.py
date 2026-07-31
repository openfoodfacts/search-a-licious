"""Utilities to conform a schemaless JSON document (as produced by Product
Opener, written in Perl) to the types expected by an ``IndexConfig``.
This is necessary because Elasticsearch is strict about types,
and will reject documents otherwise.

Product Opener emits JSON without strict typing: booleans may arrive as
``1``/``0`` or the strings ``"true"``/``"false"``, floats may arrive as
integers (or vice-versa), and epoch dates may arrive as strings.

:func:`conform_json_to_config` walks the document using the field
configuration and coerces values in place to the expected Python types,
so that what reaches Elasticsearch matches the index mapping.
"""

from app._types import JSONType
from app.config import FieldConfig, FieldType, IndexConfig
from app.utils.log import get_logger

logger = get_logger(__name__)

# Values that should be interpreted as boolean ``False`` under Perl-style
# truthiness. Anything not in this set (and not None) is considered ``True``.
_PERL_FALSEY_STRINGS = frozenset({"", "0", "false", "no", "off", "null", "none"})

# Field types that are integer-flavored.
_INTEGER_TYPES = frozenset(
    {
        FieldType.integer,
        FieldType.short,
        FieldType.long,
        FieldType.unsigned_long,
    }
)

# Field types that are float-flavored.
_FLOAT_TYPES = frozenset(
    {
        FieldType.float,
        FieldType.double,
        FieldType.half_float,
        FieldType.scaled_float,
    }
)


def _to_bool(value) -> bool | None:
    """Coerce a value to a boolean using Perl-style truthiness.

    :return: the coerced boolean, or ``None`` if the value is ``None``
        (in which case the caller will drop the field).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        # bool is a subclass of int, but is handled above.
        return value != 0
    if isinstance(value, str):
        return value.lower() not in _PERL_FALSEY_STRINGS
    # lists, dicts and other objects: presence means truthy.
    return bool(value)


def _to_number(value, *, to_int: bool) -> int | float | None:
    """Coerce a value to an int or float.

    :param to_int: if ``True`` the target type is integer-flavored and the
        result is truncated to an ``int``; otherwise a ``float`` is returned.
    :return: the coerced number, or ``None`` if the value cannot be coerced
        (the caller will drop the field and log a warning).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        # bool is a subclass of int; treat True/False as 1/0.
        value = int(value)
    if isinstance(value, (int, float)):
        return int(value) if to_int else float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        if to_int:
            return int(parsed)
        return parsed
    # not a number-like value
    return None


def _to_date(value) -> int | float | str | None:
    """Coerce a date field value.

    Only stringified epoch values are fixed (e.g. ``"1700000000"`` →
    ``1700000000``). Already-numeric values and ISO date strings are left
    untouched (returned as-is) because Elasticsearch accepts both natively.

    :return: the conformed value (an ``int`` for epochs, the original value
        otherwise), or ``None`` if a numeric-looking string failed to parse.
    """
    if isinstance(value, bool):
        # an unexpected bool; treat as a parse failure.
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            try:
                return float(stripped)
            except ValueError:
                # An ISO date string or anything else: leave it to ES.
                return value
    return value


def _coerce_value(field: FieldConfig, value):
    """Coerce a single value according to the field's type.

    :return: the coerced value, or the sentinel ``_DROP`` if the value
        cannot be conformed and the field should be removed.
    """
    field_type = field.type

    if field_type is FieldType.bool:
        coerced: bool | int | float | str | None = _to_bool(value)
        return _DROP if coerced is None else coerced

    if field_type in _INTEGER_TYPES:
        coerced = _to_number(value, to_int=True)
        return _DROP if coerced is None else coerced

    if field_type in _FLOAT_TYPES:
        coerced = _to_number(value, to_int=False)
        return _DROP if coerced is None else coerced

    if field_type is FieldType.date:
        coerced = _to_date(value)
        return _DROP if coerced is None else coerced

    # keyword, text, text_lang, taxonomy, disabled, object, nested:
    # no scalar coercion to perform.
    return value


class _DropSentinel:
    """Sentinel returned when a value cannot be conformed."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover
        return "<DROP>"


_DROP = _DropSentinel()


def _conform_subdocument(
    field: FieldConfig, document: JSONType, parents: list[str]
) -> None:
    """Recursively conform an object/nested field's subfields.

    The document value for an object or nested field may be a single dict
    or a list of dicts (this is handled defensively, since the document may
    not yet have been fully reshaped).
    """
    subfields = field.fields
    if not subfields:
        return

    def _conform_dict(item: JSONType, parents: list[str]) -> None:
        if not isinstance(item, dict):
            return
        for sub_name, sub_field in subfields.items():
            if sub_name not in item:
                continue
            _conform_field(sub_field, item, sub_name, parents)

    value = document.get(field.name)
    if isinstance(value, list):
        for i, entry in enumerate(value):
            _conform_dict(entry, parents + [str(i)])
    elif isinstance(value, dict):
        _conform_dict(value, parents)


def _conform_field(
    field: FieldConfig, document: JSONType, key: str, parents: list[str] | None = None
) -> None:
    """Conform a single top-level or nested field in the document."""
    if key not in document:
        return

    if parents is None:
        parents = []
    field_type = field.type

    if field_type in (FieldType.object, FieldType.nested):
        _conform_subdocument(field, document, parents=parents + [key])
        return

    value = document[key]

    # A list value for a scalar field: conform each element in place.
    if isinstance(value, list):
        conformed: list = []
        for element in value:
            coerced = _coerce_value(field, element)
            if coerced is not _DROP:
                conformed.append(coerced)
        if conformed:
            document[key] = conformed
        else:
            del document[key]
            logger.warning(
                "conform_json_to_config: dropped empty field %r after "
                "coercion of all its list elements to type %s",
                key,
                field.type,
            )
        return

    coerced = _coerce_value(field, value)
    if coerced is _DROP:
        del document[key]
        logger.warning(
            "conform_json_to_config: dropped field %r whose value %r "
            "could not be conformed to type %s",
            ".".join(parents + [key]),
            value,
            field.type,
        )
    else:
        document[key] = coerced


def conform_json_to_config(document: JSONType, config: IndexConfig) -> None:
    """Conform the types of fields in ``document`` in place so that they
    match the expected ``IndexConfig`` field types.

    This handles the schema discrepancies of Product Opener's Perl/JSON
    output:

    * ``bool`` fields: ``1``/``0``, ``"true"``/``"false"`` and other
      Perl-style truthy/falsy values are coerced to real booleans.
    * numeric fields (``float``, ``double``, ``half_float``,
      ``scaled_float``, ``integer``, ``short``, ``long``,
      ``unsigned_long``): cross-coerce between int and float flavors and
      parse numeric strings.
    * ``date`` fields: only stringified epoch values are cast to numbers;
      ISO date strings and already-numeric values are left untouched.

    Fields whose value cannot be conformed are dropped from the document
    and a warning is logged.

    The function only touches fields declared in ``config.fields`` (and
    their object/nested subfields); unknown keys are left as-is. Field
    lookup uses ``field.name`` (no ``input_field`` aliasing).

    :param document: the document to conform, mutated in place.
    :param config: the index configuration describing expected field types.
    """
    for field_name, field in config.fields.items():
        _conform_field(field, document, field_name)
