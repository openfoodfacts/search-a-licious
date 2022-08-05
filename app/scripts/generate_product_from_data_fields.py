"""
This script takes the data-fields.txt and generates the updated product fields.
Note, if field names are changed, etc, this will have considerable implications for the index.
"""
import json

from app.utils import constants


def get_types_for_field(field):
    """
    The docs state:
    - fields that end with _t are dates in the UNIX timestamp format (number of seconds since Jan 1st 1970)
    - fields that end with _datetime are dates in the iso8601 format: yyyy-mm-ddThh:mn:ssZ
    - fields that end with _tags are comma separated list of tags (e.g. categories_tags is the set of normalized tags computer from the categories field)
    - fields that end with a language 2 letter code (e.g. fr for French) is the set of tags in that language
    - fields that end with _100g correspond to the amount of a nutriment (in g, or kJ for energy) for 100 g or 100 ml of product
    - fields that end with _serving correspond to the amount of a nutriment (in g, or kJ for energy) for 1 serving of the product
    """

    suffix_to_es_type = {
        't': 'Integer()',
        'datetime': 'Date()',
        'tags': 'Text(multi=True)',
        '100g': 'Double()',
        'serving': 'Double()',
    }

    suffix_to_json_type = {
        't': 'integer',
        'datetime': 'string',
        'tags': 'array',
        '100g': 'number',
        'serving': 'number',
    }
    suffix = field.split('_')[-1]

    es_type = suffix_to_es_type.get(suffix)
    json_type = suffix_to_json_type.get(suffix)
    if es_type:
        return es_type, json_type

    # Otherwise, just do as keyword
    return 'Keyword()', 'string'


def generate_product_from_data_fields():
    with open('data-fields.txt', 'r') as f:
        lines = f.readlines()

    # Prepare for generating the JSON schema too
    schema = {
        '$schema': 'http://json-schema.org/schema#',
        'type': 'object',
        'properties': {},
    }
    schema_properties = schema['properties']

    for line in lines:
        words = line.split()
        # Lines with fields should follow the pattern of <field> or <field> : <description>
        if len(words) != 1 and ':' not in words:
            continue

        # Remove any lines with a : but only one word (as these are headings)
        if len(words) == 1 and ':' in words[0]:
            continue

        field_name = words[0]
        description = ''
        if len(words) > 2:
            description = ' '.join(words[2:])

        if description:
            print("# {}".format(description))

        # Some fields have dashes, let's replace them
        field_name = field_name.replace('-', '_')

        # Autocomplete cases
        if field_name in constants.AUTOCOMPLETE_FIELDS:
            # Do text with snowball (for direct searches), and autocomplete too
            print(field_name + "= Text(analyzer='snowball', fields={'autocomplete': Text(analyzer=autocomplete), "
                               "'raw': Keyword()})")
            schema_properties[field_name] = {
              "type": "string",
            }
        else:
            es_field_type, json_field_type = get_types_for_field(field_name)
            print("{} = {}".format(field_name, es_field_type))
            schema_properties[field_name] = {
              "type": json_field_type,
            }

        if description:
            schema_properties[field_name]['description'] = description

    # Serializing json
    json_str = json.dumps(schema, indent=4)

    # Writing to sample.json
    with open("../product.schema.json", "w") as outfile:
        outfile.write(json_str)

if __name__ == "__main__":
    generate_product_from_data_fields()
