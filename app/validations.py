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
            errors.append(f"Unknown field name in facets: {field_name}")
        elif not index_config.fields[field_name].bucket_agg:
            errors.append(f"Non aggregation field name in facets: {field_name}")
    return errors
