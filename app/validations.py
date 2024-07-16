from typing import cast

from .config import CONFIG, Config


def check_index_id_is_defined(index_id: str | None, config: Config) -> None:
    """Check that the index ID is defined in the configuration.

    Raise an HTTPException if it's not the case.

    :param index_id: index ID to check
    :param config: configuration to check against
    """
    if index_id is None:
        if len(config.indices) > 1:
            raise ValueError(
                f"Index ID must be provided when there is more than one index, available indices: {list(config.indices.keys())}",
            )
    elif index_id not in config.indices:
        raise ValueError(
            f"Index ID '{index_id}' not found, available indices: {list(config.indices.keys())}",
        )


def check_all_values_are_fields_agg(
    index_id: str | None, values: list[str] | None
) -> list[str]:
    """Check that all values are fields with aggregate: true
    property, that is, correspond to a field with aggregation.
    Used to check that charts are facets are valid."""
    errors: list[str] = []
    if values is None:
        return errors
    global_config = cast(Config, CONFIG)
    index_id, index_config = global_config.get_index_config(index_id)
    if index_config is None:
        raise ValueError(f"Cannot get index config for index_id {index_id}")
    for field_name in values:
        if field_name not in index_config.fields:
            errors.append(f"Unknown field name in facets/charts: {field_name}")
        elif not index_config.fields[field_name].bucket_agg:
            errors.append(f"Non aggregation field name in facets/charts: {field_name}")
    return errors


def check_fields_are_numeric(
    index_id: str | None, values: list[str] | None
) -> list[str]:
    """
    * If field exists in global_config, check that it's numeric.
    * If field looks like x.y and x.y does not exist in global config,
      check that x is an object field
    """
    errors: list[str] = []
    if values is None:
        return errors

    global_config = cast(Config, CONFIG)
    index_id, index_config = global_config.get_index_config(index_id)
    if index_config is None:
        raise ValueError(f"Cannot get index config for index_id {index_id}")
    for field_path in values:
        field_path_list = field_path.split(".")
        field_name = field_path_list[0]
        if field_name not in index_config.fields:
            errors.append(f"Unknown field name: {field_name}")
        elif len(field_path_list) == 1 and index_config.fields[field_name].type not in (
            "integer",
            "float",
            "long",
            "bool",
        ):
            errors.append(f"Non numeric field name: {field_name}")
        elif (
            len(field_path_list) >= 2
            and index_config.fields[field_name].type != "object"
        ):
            errors.append(f"Non object field name: {field_name}")
    return errors
