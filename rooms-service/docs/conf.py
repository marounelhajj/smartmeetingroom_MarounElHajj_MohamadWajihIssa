import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "Smart Meeting Room - Rooms Service"
author = "Maroun El Hajj"
release = "1.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "undoc-members": True,
}
