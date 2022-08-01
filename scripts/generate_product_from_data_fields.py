"""
This script takes the data-fields.txt and generates the updated product fields.
Note, if field names are changed, etc, this will have considerable implications for the index.
"""
from utils import constants


def get_type_for_field(field):
    """
    The docs state:
    - fields that end with _t are dates in the UNIX timestamp format (number of seconds since Jan 1st 1970)
    - fields that end with _datetime are dates in the iso8601 format: yyyy-mm-ddThh:mn:ssZ
    - fields that end with _tags are comma separated list of tags (e.g. categories_tags is the set of normalized tags computer from the categories field)
    - fields that end with a language 2 letter code (e.g. fr for French) is the set of tags in that language
    - fields that end with _100g correspond to the amount of a nutriment (in g, or kJ for energy) for 100 g or 100 ml of product
    - fields that end with _serving correspond to the amount of a nutriment (in g, or kJ for energy) for 1 serving of the product
    """

    suffix_to_type = {
        't': 'Integer()',
        'datetime': 'Date()',
        'tags': 'Text(multi=True)',
        '100g': 'Double()',
        'serving': 'Double()',
    }

    suffix = field.split('_')[-1]

    type = suffix_to_type.get(suffix)
    if type:
        return type

    # Otherwise, just do as keyword
    return 'Keyword()'


def generate_product_from_data_fields():
    with open('data-fields.txt', 'r') as f:
        lines = f.readlines()

    # Add undocumented fields
    lines += constants.UNDOCUMENTED_FIELDS

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
        else:
            field_type = get_type_for_field(field_name)
            print("{} = {}".format(field_name, field_type))


if __name__ == "__main__":
    generate_product_from_data_fields()
