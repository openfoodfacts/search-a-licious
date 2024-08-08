# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Search-a-licious"
copyright = "2024, Open Food Facts"
author = "Open Food Facts"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.linkcode",
    "alabaster",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.typer",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
html_theme_options = {
    "github_user": "openfoodfacts",
    "github_repo": "search-a-licious",
    "github_banner": True,
    "extra_nav_links": {
        "🢀 Back to main doc": "/search-a-licious",
    },
}

# -- Options for autodoc pydantic --------------------------------------------
autodoc_pydantic_model_show_json = True
autodoc_pydantic_settings_show_json = False


def linkcode_resolve(domain, info):
    """Getting url for source file for sphinx.ext.linkcode"""
    if domain != "py":
        return None
    if not info["module"]:
        return None
    filename = info["module"].replace(".", "/")
    return (
        "https://github.com/openfoodfacts/search-a-licious/tree/main/%s.py" % filename
    )
