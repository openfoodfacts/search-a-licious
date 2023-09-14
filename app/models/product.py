from __future__ import annotations

import datetime

from elasticsearch_dsl import Date
from elasticsearch_dsl import Document
from elasticsearch_dsl import Double
from elasticsearch_dsl import Field
from elasticsearch_dsl import Keyword
from elasticsearch_dsl import Nested
from elasticsearch_dsl import Text

from app.utils import constants
from app.utils.analyzers import autocomplete
from app.utils.analyzers import text_like


class Flattened(Field):
    # Elasticsearch dsl doesn't support the Flattened field yet, so we need to add it here
    name = "flattened"


def create_product_from_dict(d):
    # Remove the ocr fields
    d = {k: v for k, v in d.items() if "_ocr_" not in k}

    # Make sure that the nutriments values are floats
    temp_nutriments = {}
    if "nutriments" in d:
        for k, v in d["nutriments"].items():
            for str_value in ["unit", "label", "modifier"]:
                if str_value in k:
                    temp_nutriments[k] = v
                    break
            else:
                temp_nutriments[k] = float(v)

        d["nutriments"] = temp_nutriments

    if "last_modified_t" in d:
        d["last_modified_datetime"] = datetime.datetime.utcfromtimestamp(
            d["last_modified_t"],
        )
    if "created_t" in d:
        d["created_datetime"] = datetime.datetime.utcfromtimestamp(
            d["created_t"],
        )

    product = Product(**d)
    product.fill_internal_fields()
    return product


class Product(Document):
    """
    This was initially created with the scripts/generate_schema.py script. However, note that there have been manual
    adjustments.

    Furthermore, additional fields are added at index time, so below is just a subset of the available fields.
    """

    class Index:
        name = constants.INDEX_ALIAS
        settings = {
            "number_of_shards": 4,
            "index.mapping.nested_fields.limit": 200,
            "index.mapping.total_fields.limit": 20000,
        }

    def fill_internal_fields(self):
        self.meta["id"] = self.code
        self.last_indexed_datetime = datetime.datetime.now()

    def save(
        self,
        **kwargs,
    ):
        self.fill_internal_fields()
        super().save(**kwargs)

    # barcode of the product (can be EAN-13 or internal codes for some food stores), for products without a barcode, Open Food Facts assigns a number starting with the 200 reserved prefix
    code = Keyword(required=True)
    # date of last index for the purposes of search
    last_indexed_datetime = Date(required=True)
    # name of the product
    product_name = Text(
        analyzer=text_like,
        fields={
            "autocomplete": Text(analyzer=autocomplete),
            "raw": Keyword(),
        },
    )
    brands = Text(
        analyzer=text_like,
        fields={
            "autocomplete": Text(analyzer=autocomplete),
            "raw": Keyword(),
        },
    )
    categories = Text(
        analyzer=text_like,
        fields={
            "autocomplete": Text(analyzer=autocomplete),
            "raw": Keyword(),
        },
    )

    last_check_dates_tags = Keyword(multi=True)
    traces = Keyword()
    last_modified_t = Double()
    last_modified_datetime = Date()
    nucleotides_prev_tags = Keyword(multi=True)
    ecoscore_tags = Keyword(multi=True)
    allergens_from_user = Keyword()
    informers_tags = Keyword(multi=True)
    ingredients_text_en = Keyword()
    removed_countries_tags = Keyword(multi=True)
    other_nutritional_substances_prev_tags = Keyword(multi=True)
    last_modified_by = Keyword()
    lc = Keyword()
    nutrition_score_debug = Keyword()
    created_t = Double()
    created_datetime = Date()
    states_hierarchy = Keyword(multi=True)
    data_quality_info_tags = Keyword(multi=True)
    rev = Double()
    traces_from_ingredients = Keyword()
    product_name_en = Keyword()
    lang = Keyword()
    additives_old_tags = Keyword(multi=True)
    nova_group_tags = Keyword(multi=True)
    nutrition_data_prepared_per = Keyword()
    nutrition_grades_tags = Keyword(multi=True)
    nutrition_data_per = Keyword()
    allergens = Keyword()
    packagings = Nested(
        properties={
            "shape": Keyword(),
            "quantity_value": Keyword(),
            "quantity": Keyword(),
            "quantity_unit": Keyword(),
        },
        multi=True,
    )
    data_quality_tags = Keyword(multi=True)
    main_countries_tags = Keyword(multi=True)
    vitamins_tags = Keyword(multi=True)
    category_properties = Nested(
        properties={},
    )
    data_quality_bugs_tags = Keyword(multi=True)
    last_editor = Keyword()
    photographers_tags = Keyword(multi=True)
    allergens_from_ingredients = Keyword()
    nutrient_levels_tags = Keyword(multi=True)
    serving_quantity = Keyword()
    languages_tags = Keyword(multi=True)
    interface_version_modified = Keyword()
    allergens_tags = Keyword(multi=True)
    pnns_groups_1_tags = Keyword(multi=True)
    pnns_groups_2_tags = Keyword(multi=True)
    ingredients_text = Keyword()
    popularity_key = Double()
    update_key = Keyword()
    pnns_groups_1 = Keyword()
    nutrition_data = Keyword()
    languages_hierarchy = Keyword(multi=True)
    complete = Double()
    creator = Keyword()
    brands_tags = Keyword(multi=True)
    states = Keyword()
    additives_tags = Keyword(multi=True)
    nutriments = Nested(
        properties={
            "energy_serving": Double(),
            "vitamin-a_unit": Keyword(),
            "trans-fat_value": Double(),
            "sodium": Double(),
            "vitamin-c": Double(),
            "sodium_serving": Double(),
            "salt_100g": Double(),
            "energy-kcal_100g": Double(),
            "energy-kj_value": Double(),
            "energy-kj": Double(),
            "energy-kj_100g": Double(),
            "carbohydrates_100g": Double(),
            "energy_100g": Double(),
            "energy": Double(),
            "proteins_serving": Double(),
            "proteins": Double(),
            "sugars": Double(),
            "fiber_value": Double(),
            "trans-fat": Double(),
            "nova-group_100g": Double(),
            "vitamin-a_100g": Double(),
            "fiber": Double(),
            "energy_unit": Keyword(),
            "fat": Double(),
            "fruits-vegetables-nuts-estimate-from-ingredients_serving": Double(),
            "fruits-vegetables-nuts-estimate": Double(),
            "fruits-vegetables-nuts-estimate_value": Double(),
            "fruits-vegetables-nuts-estimate_serving": Double(),
            "potassium_100g": Double(),
            "iron": Double(),
            "fiber_unit": Keyword(),
            "energy-kcal_value": Double(),
            "trans-fat_serving": Double(),
            "saturated-fat_serving": Double(),
            "vitamin-c_value": Double(),
            "salt_unit": Keyword(),
            "sugars_value": Double(),
            "proteins_value": Double(),
            "vitamin-c_unit": Keyword(),
            "iron_unit": Keyword(),
            "vitamin-c_100g": Double(),
            "cholesterol_value": Double(),
            "fiber_serving": Double(),
            "carbohydrates_value": Double(),
            "carbohydrates": Double(),
            "fat_serving": Double(),
            "iron_100g": Double(),
            "trans-fat_unit": Keyword(),
            "cholesterol": Double(),
            "salt_serving": Double(),
            "saturated-fat_value": Double(),
            "energy-kcal": Double(),
            "fat_value": Double(),
            "calcium_unit": Keyword(),
            "vitamin-c_serving": Double(),
            "sodium_unit": Keyword(),
            "sugars_unit": Keyword(),
            "iron_value": Double(),
            "fat_100g": Double(),
            "vitamin-a": Double(),
            "cholesterol_serving": Double(),
            "calcium": Double(),
            "nutrition-score-fr": Double(),
            "carbohydrates_serving": Double(),
            "calcium_serving": Double(),
            "saturated-fat_unit": Keyword(),
            "salt": Double(),
            "nutrition-score-fr_100g": Double(),
            "nova-group_serving": Double(),
            "vitamin-a_serving": Double(),
            "cholesterol_100g": Double(),
            "energy-kcal_unit": Keyword(),
            "fat_unit": Keyword(),
            "energy-kcal_serving": Double(),
            "proteins_100g": Double(),
            "trans-fat_100g": Double(),
            "saturated-fat_100g": Double(),
            "iron_serving": Double(),
            "cholesterol_unit": Keyword(),
            "calcium_100g": Double(),
            "sugars_serving": Double(),
            "fruits-vegetables-nuts-estimate-from-ingredients_100g": Double(),
            "sodium_value": Double(),
            "saturated-fat": Double(),
            "sugars_100g": Double(),
            "sodium_100g": Double(),
            "vitamin-a_value": Double(),
            "calcium_value": Double(),
            "proteins_unit": Keyword(),
            "nova-group": Double(),
            "energy_value": Double(),
            "carbohydrates_unit": Keyword(),
            "salt_value": Double(),
            "fiber_100g": Double(),
            "manganese": Double(),
            "omega-6-fat_100g": Double(),
            "omega-6-fat": Double(),
            "omega-6-fat_value": Double(),
            "carbon-footprint-from-known-ingredients_product": Double(),
            "phenylalanin_100g": Double(),
            "proteins-dry-substance_100g": Double(),
            "fruits-vegetables-nuts-estimate_100g": Double(),
            "monounsaturated-fat_value": Double(),
        },
    )
    languages = Nested(
        properties={
            "en:english": Double(),
        },
    )
    countries = Keyword()
    data_quality_warnings_tags = Keyword(multi=True)
    other_nutritional_substances_tags = Keyword(multi=True)
    serving_size = Keyword()
    nova_group_debug = Keyword()
    traces_tags = Keyword(multi=True)
    countries_hierarchy = Keyword(multi=True)
    allergens_hierarchy = Keyword(multi=True)
    pnns_groups_2 = Keyword()
    misc_tags = Keyword(multi=True)
    countries_lc = Keyword()
    _keywords = Keyword(multi=True)
    data_quality_errors_tags = Keyword(multi=True)
    vitamins_prev_tags = Keyword(multi=True)
    categories_properties = Nested(
        properties={},
    )
    id = Keyword()
    amino_acids_prev_tags = Keyword(multi=True)
    checkers_tags = Keyword(multi=True)
    ciqual_food_name_tags = Keyword(multi=True)
    last_edit_dates_tags = Keyword(multi=True)
    ingredients_from_palm_oil_tags = Keyword(multi=True)
    popularity_tags = Keyword(multi=True)
    states_tags = Keyword(multi=True)
    interface_version_created = Keyword()
    categories_properties_tags = Keyword(multi=True)
    ingredients_text_debug = Keyword()
    traces_from_user = Keyword()
    completeness = Double()
    minerals_tags = Keyword(multi=True)
    countries_tags = Keyword(multi=True)
    additives_original_tags = Keyword(multi=True)
    correctors_tags = Keyword(multi=True)
    additives_debug_tags = Keyword(multi=True)
    nutrition_score_beverage = Double()
    traces_hierarchy = Keyword(multi=True)
    ingredients_hierarchy = Keyword(multi=True)
    unique_scans_n = Double()
    ingredients_that_may_be_from_palm_oil_tags = Keyword(multi=True)
    unknown_nutrients_tags = Keyword(multi=True)
    entry_dates_tags = Keyword(multi=True)
    ecoscore_grade = Keyword()
    amino_acids_tags = Keyword(multi=True)
    food_groups_tags = Keyword(multi=True)
    additives_prev_original_tags = Keyword(multi=True)
    scans_n = Double()
    languages_codes = Nested(
        properties={
            "en": Double(),
        },
    )
    added_countries_tags = Keyword(multi=True)
    nutrient_levels = Nested(
        properties={
            "saturated-fat": Keyword(),
            "salt": Keyword(),
            "sugars": Keyword(),
            "fat": Keyword(),
        },
    )
    no_nutrition_data = Keyword()
    editors_tags = Keyword(multi=True)
    ecoscore_data = Flattened()
    nucleotides_tags = Keyword(multi=True)
    codes_tags = Keyword(multi=True)
    minerals_prev_tags = Keyword(multi=True)
    debug_param_sorted_langs = Keyword(multi=True)
    ingredients_text_en_debug_tags = Keyword(multi=True)
    product_name_en_debug_tags = Keyword(multi=True)
    ingredients_text_with_allergens_en = Keyword()
    generic_name_fr = Keyword()
    last_image_t = Double()
    labels_hierarchy = Keyword(multi=True)
    origins_lc = Keyword()
    ingredients_n = Double()
    ingredients_tags = Keyword(multi=True)
    unknown_ingredients_n = Double()
    ingredients_analysis = Flattened()
    additives_n = Double()
    ingredients_that_may_be_from_palm_oil_n = Double()
    images = Flattened()
    known_ingredients_n = Double()
    product_name_debug_tags = Keyword(multi=True)
    product_quantity = Keyword()
    emb_codes = Keyword()
    manufacturing_places = Keyword()
    origins_tags = Keyword(multi=True)
    ingredients_original_tags = Keyword(multi=True)
    food_groups = Keyword()
    ingredients = Nested(
        properties={
            "id": Keyword(),
            "percent_estimate": Double(),
            "ingredients": Nested(
                properties={
                    "ingredients": Nested(
                        properties={
                            "text": Keyword(),
                            "id": Keyword(),
                            "percent_estimate": Double(),
                        },
                        multi=True,
                    ),
                    "text": Keyword(),
                    "id": Keyword(),
                    "percent_estimate": Double(),
                    "vegan": Keyword(),
                    "vegetarian": Keyword(),
                    "percent": Double(),
                },
                multi=True,
            ),
            "text": Keyword(),
            "vegan": Keyword(),
            "vegetarian": Keyword(),
            "percent": Double(),
            "processing": Keyword(),
        },
        multi=True,
    )
    packaging_old = Keyword()
    manufacturing_places_tags = Keyword(multi=True)
    ingredients_with_unspecified_percent_sum = Double()
    last_image_dates_tags = Keyword(multi=True)
    nutrition_data_prepared_per_debug_tags = Keyword(multi=True)
    origins_hierarchy = Keyword(multi=True)
    purchase_places_debug_tags = Keyword(multi=True)
    labels_tags = Keyword(multi=True)
    expiration_date = Keyword()
    labels_lc = Keyword()
    cities_tags = Keyword(multi=True)
    fruits_vegetables_nuts_100g_estimate = Double()
    quantity_debug_tags = Keyword(multi=True)
    ingredients_text_debug_tags = Keyword(multi=True)
    emb_codes_tags = Keyword(multi=True)
    packaging = Keyword()
    generic_name_en = Keyword()
    ingredients_analysis_tags = Keyword(multi=True)
    ingredients_with_specified_percent_n = Double()
    generic_name = Keyword()
    ingredients_n_tags = Keyword(multi=True)
    product_name_fr = Keyword()
    ingredients_from_or_that_may_be_from_palm_oil_n = Double()
    data_sources_tags = Keyword(multi=True)
    traces_debug_tags = Keyword(multi=True)
    link_debug_tags = Keyword(multi=True)
    expiration_date_debug_tags = Keyword(multi=True)
    generic_name_fr_debug_tags = Keyword(multi=True)
    packaging_old_before_taxonomization = Keyword()
    max_imgid = Keyword()
    categories_hierarchy = Keyword(multi=True)
    ingredients_text_with_allergens_fr = Keyword()
    categories_old = Keyword()
    generic_name_en_debug_tags = Keyword(multi=True)
    ingredients_with_unspecified_percent_n = Double()
    stores_tags = Keyword(multi=True)
    nova_group_error = Keyword()
    purchase_places_tags = Keyword(multi=True)
    purchase_places = Keyword()
    data_sources = Keyword()
    ingredients_percent_analysis = Double()
    link = Keyword()
    packaging_hierarchy = Keyword(multi=True)
    labels = Keyword()
    packaging_tags = Keyword(multi=True)
    stores_debug_tags = Keyword(multi=True)
    manufacturing_places_debug_tags = Keyword(multi=True)
    sources = Nested(
        properties={
            "id": Keyword(),
            "url": Keyword(),
            "fields": Keyword(multi=True),
            "images": Keyword(multi=True),
            "import_t": Double(),
            "name": Keyword(),
            "manufacturer": Keyword(),
        },
        multi=True,
    )
    labels_old = Keyword()
    packaging_lc = Keyword()
    quantity = Keyword()
    emb_codes_orig = Keyword()
    countries_debug_tags = Keyword(multi=True)
    nova_groups_tags = Keyword(multi=True)
    lang_debug_tags = Keyword(multi=True)
    ingredients_text_fr_debug_tags = Keyword(multi=True)
    emb_codes_debug_tags = Keyword(multi=True)
    stores = Keyword()
    compared_to_category = Keyword()
    nutrition_data_prepared = Keyword()
    ingredients_with_specified_percent_sum = Double()
    ingredients_text_with_allergens = Keyword()
    nutrition_data_per_debug_tags = Keyword(multi=True)
    serving_size_debug_tags = Keyword(multi=True)
    origins_old = Keyword()
    ingredients_from_palm_oil_n = Double()
    additives_old_n = Double()
    categories_tags = Keyword(multi=True)
    categories_lc = Keyword()
    product_name_fr_debug_tags = Keyword(multi=True)
    brands_debug_tags = Keyword(multi=True)
    ingredients_text_fr = Keyword()
    origins = Keyword()
    nutrition_score_warning_fruits_vegetables_nuts_estimate_from_ingredients_value = (
        Double()
    )
    nutriscore_grade = Keyword()
    nutrition_grades = Keyword()
    nutrition_grade_fr = Keyword()
    nutriscore_data = Nested(
        properties={
            "proteins": Double(),
            "sugars": Double(),
            "fiber_value": Double(),
            "proteins_points": Double(),
            "fruits_vegetables_nuts_colza_walnut_olive_oils_points": Double(),
            "is_cheese": Double(),
            "sugars_points": Double(),
            "saturated_fat_ratio_points": Double(),
            "fiber_points": Double(),
            "grade": Keyword(),
            "fiber": Double(),
            "sodium": Double(),
            "energy": Double(),
            "fruits_vegetables_nuts_colza_walnut_olive_oils_value": Double(),
            "saturated_fat_value": Double(),
            "saturated_fat_ratio_value": Double(),
            "fruits_vegetables_nuts_colza_walnut_olive_oils": Double(),
            "sodium_points": Double(),
            "energy_value": Double(),
            "energy_points": Double(),
            "saturated_fat_ratio": Double(),
            "is_fat": Double(),
            "sugars_value": Double(),
            "sodium_value": Double(),
            "is_beverage": Double(),
            "saturated_fat_points": Double(),
            "positive_points": Double(),
            "negative_points": Double(),
            "score": Double(),
            "is_water": Double(),
            "proteins_value": Double(),
            "saturated_fat": Double(),
        },
    )
    nutriscore_score_opposite = Double()
    nutrition_score_warning_fruits_vegetables_nuts_estimate_from_ingredients = Double()
    ecoscore_score = Double()
    new_additives_n = Double()
    editors = Keyword(multi=True)
    nutriscore_score = Double()
    nutrition_score_warning_no_fiber = Double()
    downgraded = Keyword()
    nutrition_score_warning_no_fruits_vegetables_nuts = Double()
    forest_footprint_data = Nested(
        properties={
            "footprint_per_kg": Double(),
            "ingredients": Nested(
                properties={
                    "footprint_per_kg": Double(),
                    "percent_estimate": Double(),
                    "tag_type": Keyword(),
                    "tag_id": Keyword(),
                    "matching_tag_id": Keyword(),
                    "percent": Double(),
                    "processing_factor": Keyword(),
                    "conditions_tags": Keyword(multi=True),
                    "type": Nested(
                        properties={
                            "soy_feed_factor": Keyword(),
                            "deforestation_risk": Keyword(),
                            "name": Keyword(),
                            "soy_yield": Keyword(),
                        },
                    ),
                },
                multi=True,
            ),
            "grade": Keyword(),
        },
    )
    nova_group = Double()
    allergens_debug_tags = Keyword(multi=True)
    nova_groups = Keyword()
    carbon_footprint_from_known_ingredients_debug = Keyword()
    carbon_footprint_percent_of_known_ingredients = Double()
    nutrition_score_warning_fruits_vegetables_nuts_from_category_value = Double()
    nutrition_score_warning_fruits_vegetables_nuts_from_category = Keyword()
    allergens_lc = Keyword()
    traces_lc = Keyword()
    nova_groups_markers = Nested(
        properties={},
    )
    carbon_footprint_from_meat_or_fish_debug = Keyword()
    labels_prev_tags = Keyword(multi=True)
    labels_prev_hierarchy = Keyword(multi=True)
    emb_codes_20141016 = Keyword()
    categories_prev_hierarchy = Keyword(multi=True)
    categories_prev_tags = Keyword(multi=True)
    labels_debug_tags = Keyword(multi=True)
    categories_debug_tags = Keyword(multi=True)
    additives_tags_n = Keyword()
    origins_fr = Keyword()
    with_sweeteners = Double()
    nutrition_score_warning_fruits_vegetables_nuts_estimate = Double()
    specific_ingredients = Nested(
        properties={
            "ingredient": Keyword(),
            "id": Keyword(),
            "label": Keyword(),
            "origins": Keyword(),
        },
        multi=True,
    )
    data_quality_warning_tags = Keyword(multi=True)
    product_name_de = Keyword()
    product_name_de_debug_tags = Keyword(multi=True)
    ingredients_text_with_allergens_de = Keyword()
    generic_name_de = Keyword()
    ingredients_text_de = Keyword()
    generic_name_de_debug_tags = Keyword(multi=True)
    ingredients_text_de_debug_tags = Keyword(multi=True)
    photographers = Keyword(multi=True)
    correctors = Keyword(multi=True)
    checkers = Keyword(multi=True)
    informers = Keyword(multi=True)
    generic_name_nl = Keyword()
    product_name_nl = Keyword()
    generic_name_it_debug_tags = Keyword(multi=True)
    ingredients_text_es_debug_tags = Keyword(multi=True)
    generic_name_es_debug_tags = Keyword(multi=True)
    ingredients_text_it = Keyword()
    ingredients_text_nl = Keyword()
    ingredients_text_nl_debug_tags = Keyword(multi=True)
    obsolete = Keyword()
    product_name_es_debug_tags = Keyword(multi=True)
    generic_name_nl_debug_tags = Keyword(multi=True)
    ingredients_text_with_allergens_es = Keyword()
    ingredients_text_es = Keyword()
    ingredients_text_it_debug_tags = Keyword(multi=True)
    product_name_es = Keyword()
    generic_name_es = Keyword()
    product_name_it = Keyword()
    obsolete_since_date = Keyword()
    ingredients_text_with_allergens_it = Keyword()
    product_name_it_debug_tags = Keyword(multi=True)
    ingredients_text_with_allergens_nl = Keyword()
    generic_name_it = Keyword()
    product_name_nl_debug_tags = Keyword(multi=True)
    ingredients_text_en_imported = Keyword()
    categories_imported = Keyword()
    brand_owner = Keyword()
    sources_fields = Nested(
        properties={
            "org-database-usda": Nested(
                properties={
                    "fdc_category": Keyword(),
                    "fdc_id": Keyword(),
                    "available_date": Keyword(),
                    "publication_date": Keyword(),
                    "fdc_data_source": Keyword(),
                    "modified_date": Keyword(),
                },
            ),
        },
    )
    nutrition_data_per_imported = Keyword()
    lc_imported = Keyword()
    countries_imported = Keyword()
    product_name_en_imported = Keyword()
    brand_owner_imported = Keyword()
    data_sources_imported = Keyword()
    nutrition_data_prepared_per_imported = Keyword()
    serving_size_imported = Keyword()
    allergens_imported = Keyword()
    ingredients_text_with_allergens_la = Keyword()
    ingredients_text_la = Keyword()
    product_name_la = Keyword()
    teams_tags = Keyword(multi=True)
    teams = Keyword()
    traces_imported = Keyword()
    labels_imported = Keyword()
    packaging_text_fr = Keyword()
    origin_fr = Keyword()
    packaging_text = Keyword()
    origin = Keyword()
    generic_name_en_imported = Keyword()
    ecoscore_extended_data = Flattened()
    ecoscore_extended_data_version = Keyword()
    packaging_text_en = Keyword()
    environment_impact_level_tags = Keyword(multi=True)
    origin_en = Keyword()
    environment_impact_level = Keyword()
    obsolete_since_date = Keyword()
    obsolete_since_date_imported = Keyword()
