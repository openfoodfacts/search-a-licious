from __future__ import annotations

from elasticsearch_dsl import Date
from elasticsearch_dsl import Document
from elasticsearch_dsl import Double
from elasticsearch_dsl import Integer
from elasticsearch_dsl import Keyword
from elasticsearch_dsl import Text

from app.utils import constants
from app.utils.analyzers import autocomplete
from app.utils.analyzers import text_like


class Product(Document):
    """
    This should mirror the fields here: https://github.com/openfoodfacts/openfoodfacts-server/blob/main/html/data/data-fields.txt
    Use scripts/generate_product_from_data_fields.py to regenerate from data-fields.txt, but be careful for manual
    adjustments
    """

    class Index:
        name = constants.INDEX_ALIAS
        settings = {
            'number_of_shards': 4,
        }

    # barcode of the product (can be EAN-13 or internal codes for some food stores), for products without a barcode, Open Food Facts assigns a number starting with the 200 reserved prefix
    code = Keyword()
    # date that the product was added (iso8601 format: yyyy-mm-ddThh:mn:ssZ)
    created_datetime = Date()
    # date that the product was added (UNIX timestamp format)
    created_t = Integer()
    # contributor who first added the product
    creator = Keyword()
    generic_name = Keyword()
    last_modified_datetime = Date()
    # date that the product page was last modified
    last_modified_t = Integer()
    # name of the product
    product_name = Text(
        analyzer=text_like, fields={
            'autocomplete': Text(analyzer=autocomplete), 'raw': Keyword(),
        },
    )
    # quantity and unit
    quantity = Keyword()
    # url of the product page on Open Food Facts
    url = Keyword()
    brands = Text(
        analyzer=text_like, fields={
            'autocomplete': Text(analyzer=autocomplete), 'raw': Keyword(),
        },
    )
    brands_tags = Text(multi=True)
    categories = Text(
        analyzer=text_like, fields={
            'autocomplete': Text(analyzer=autocomplete), 'raw': Keyword(),
        },
    )
    categories_fr = Keyword()
    categories_tags = Text(multi=True)
    cities = Keyword()
    cities_tags = Text(multi=True)
    # list of countries where the product is sold
    countries = Keyword()
    countries_fr = Keyword()
    countries_tags = Text(multi=True)
    emb_codes = Keyword()
    emb_codes_tags = Text(multi=True)
    # coordinates corresponding to the first packaging code indicated
    first_packaging_code_geo = Keyword()
    labels = Keyword()
    labels_fr = Keyword()
    labels_tags = Text(multi=True)
    # places where manufactured or transformed
    manufacturing_places = Keyword()
    manufacturing_places_tags = Text(multi=True)
    # origins of ingredients
    origins = Keyword()
    origins_tags = Text(multi=True)
    # shape, material
    packaging = Keyword()
    packaging_tags = Text(multi=True)
    purchase_places = Keyword()
    stores = Keyword()
    ingredients_from_palm_oil = Keyword()
    ingredients_from_palm_oil_n = Keyword()
    ingredients_from_palm_oil_tags = Text(multi=True)
    ingredients_tags = Text(multi=True)
    ingredients_text = Keyword()
    ingredients_that_may_be_from_palm_oil = Keyword()
    ingredients_that_may_be_from_palm_oil_n = Keyword()
    ingredients_that_may_be_from_palm_oil_tags = Text(multi=True)
    traces = Keyword()
    traces_tags = Text(multi=True)
    abbreviated_product_name = Keyword()
    additives = Keyword()
    additives_en = Keyword()
    # number of food additives
    additives_n = Keyword()
    additives_tags = Text(multi=True)
    allergens = Keyword()
    allergens_en = Keyword()
    brand_owner = Keyword()
    categories_en = Keyword()
    countries_en = Keyword()
    ecoscore_grade = Keyword()
    ecoscore_score = Keyword()
    food_groups = Keyword()
    food_groups_en = Keyword()
    food_groups_tags = Text(multi=True)
    image_ingredients_small_url = Keyword()
    image_ingredients_url = Keyword()
    image_nutrition_small_url = Keyword()
    image_nutrition_url = Keyword()
    image_small_url = Keyword()
    image_url = Keyword()
    labels_en = Keyword()
    main_category = Keyword()
    main_category_en = Keyword()
    main_category_fr = Keyword()
    # indicates if the nutrition facts are indicated on the food label
    no_nutriments = Keyword()
    nova_group = Keyword()
    nutriscore_grade = Keyword()
    nutriscore_score = Keyword()
    # nutrition grade ('a' to 'e'). see https://fr.openfoodfacts.org/nutriscore
    nutrition_grade_fr = Keyword()
    origins_en = Keyword()
    packaging_en = Keyword()
    packaging_text = Keyword()
    pnns_groups_1 = Keyword()
    pnns_groups_2 = Keyword()
    serving_quantity = Keyword()
    # serving size in g
    serving_size = Keyword()
    states = Keyword()
    states_en = Keyword()
    states_tags = Text(multi=True)
    traces_en = Keyword()
    # % vol of alcohol
    alcohol_100g = Double()
    alpha_linolenic_acid_100g = Double()
    arachidic_acid_100g = Double()
    arachidonic_acid_100g = Double()
    behenic_acid_100g = Double()
    beta_carotene_100g = Double()
    beta_glucan_100g = Double()
    bicarbonate_100g = Double()
    # also known as Vitamine B8
    biotin_100g = Double()
    butyric_acid_100g = Double()
    caffeine_100g = Double()
    calcium_100g = Double()
    capric_acid_100g = Double()
    caproic_acid_100g = Double()
    caprylic_acid_100g = Double()
    carbohydrates_100g = Double()
    carbon_footprint_from_meat_or_fish_100g = Double()
    carnitine_100g = Double()
    casein_100g = Double()
    cerotic_acid_100g = Double()
    chloride_100g = Double()
    chlorophyl_100g = Double()
    cholesterol_100g = Double()
    choline_100g = Double()
    chromium_100g = Double()
    cocoa_100g = Double()
    collagen_meat_protein_ratio_100g = Double()
    copper_100g = Double()
    dihomo_gamma_linolenic_acid_100g = Double()
    docosahexaenoic_acid_100g = Double()
    eicosapentaenoic_acid_100g = Double()
    elaidic_acid_100g = Double()
    energy_kcal_100g = Double()
    energy_kj_100g = Double()
    energy_100g = Double()
    energy_from_fat_100g = Double()
    erucic_acid_100g = Double()
    fat_100g = Double()
    fiber_100g = Double()
    fluoride_100g = Double()
    folates_100g = Double()
    fructose_100g = Double()
    # % of fruits, vegetables and nuts (excluding potatoes, yams, manioc)
    fruits_vegetables_nuts_100g = Double()
    fruits_vegetables_nuts_dried_100g = Double()
    fruits_vegetables_nuts_estimate_100g = Double()
    fruits_vegetables_nuts_estimate_from_ingredients_100g = Double()
    gamma_linolenic_acid_100g = Double()
    glucose_100g = Double()
    glycemic_index_100g = Double()
    gondoic_acid_100g = Double()
    inositol_100g = Double()
    insoluble_fiber_100g = Double()
    iodine_100g = Double()
    iron_100g = Double()
    lactose_100g = Double()
    lauric_acid_100g = Double()
    lignoceric_acid_100g = Double()
    linoleic_acid_100g = Double()
    magnesium_100g = Double()
    maltodextrins_100g = Double()
    maltose_100g = Double()
    manganese_100g = Double()
    mead_acid_100g = Double()
    melissic_acid_100g = Double()
    molybdenum_100g = Double()
    monounsaturated_fat_100g = Double()
    montanic_acid_100g = Double()
    myristic_acid_100g = Double()
    nervonic_acid_100g = Double()
    nucleotides_100g = Double()
    oleic_acid_100g = Double()
    omega_3_fat_100g = Double()
    omega_6_fat_100g = Double()
    omega_9_fat_100g = Double()
    palmitic_acid_100g = Double()
    # also known as Vitamine B5
    pantothenic_acid_100g = Double()
    # pH (no unit)
    ph_100g = Double()
    phosphorus_100g = Double()
    phylloquinone_100g = Double()
    polyols_100g = Double()
    polyunsaturated_fat_100g = Double()
    potassium_100g = Double()
    proteins_100g = Double()
    salt_100g = Double()
    saturated_fat_100g = Double()
    selenium_100g = Double()
    serum_proteins_100g = Double()
    silica_100g = Double()
    sodium_100g = Double()
    soluble_fiber_100g = Double()
    starch_100g = Double()
    stearic_acid_100g = Double()
    sucrose_100g = Double()
    sugars_100g = Double()
    taurine_100g = Double()
    trans_fat_100g = Double()
    vitamin_a_100g = Double()
    vitamin_b12_100g = Double()
    vitamin_b1_100g = Double()
    vitamin_b2_100g = Double()
    vitamin_b6_100g = Double()
    vitamin_b9_100g = Double()
    vitamin_c_100g = Double()
    vitamin_d_100g = Double()
    vitamin_e_100g = Double()
    vitamin_k_100g = Double()
    vitamin_pp_100g = Double()
    water_hardness_100g = Double()
    zinc_100g = Double()
    # carbon footprint (as indicated on the packaging of some products)
    carbon_footprint_100g = Double()
    # Nutri-Score - Nutrition score derived from the UK FSA score and adapted for the French market (formula defined by the team of Professor Hercberg)
    nutrition_score_fr_100g = Double()
    # nutrition score defined by the UK Food Standards Administration (FSA)
    nutrition_score_uk_100g = Double()
