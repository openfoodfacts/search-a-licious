from pathlib import Path


from dotenv import load_dotenv

load_dotenv()

from app.cli.main import import_data, import_taxonomies
import_taxonomies()

# import_data("/home/frank/Downloads/openfoodfacts-products.jsonl.gz", 1, 10000, Path("data/config/openfoodfacts.yml"))
