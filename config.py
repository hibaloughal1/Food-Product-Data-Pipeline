"""
config.py
=========
Configuration centralisée de la plateforme de veille tarifaire.

Toutes les valeurs sensibles (identifiants de connexion) sont lues depuis
des variables d'environnement plutôt que codées en dur.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
# Par défaut on utilise SQLite (fichier local) pour permettre de lancer le
# projet immédiatement sans installer de serveur MySQL. Il suffit de définir
# la variable d'environnement DATABASE_URL pour basculer vers MySQL, par ex :
#   export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/products"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'products.db'}"
)

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Délai (en secondes) entre deux requêtes vers un même site,
# conformément à la contrainte "limiter la fréquence des accès" (12.2).
REQUEST_DELAY = float(os.environ.get("SCRAPER_DELAY", 2.0))
REQUEST_TIMEOUT = int(os.environ.get("SCRAPER_TIMEOUT", 15))
MAX_RETRIES = 3

# Dossier de stockage des catalogues PDF téléchargés et des images produits
CATALOGUES_DIR = BASE_DIR / "data" / "catalogues"
IMAGES_DIR = BASE_DIR / "data" / "images"
LOGS_DIR = BASE_DIR / "logs"

for d in (CATALOGUES_DIR, IMAGES_DIR, LOGS_DIR, BASE_DIR / "data"):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
OCR_LANG = os.environ.get("OCR_LANG", "fra")

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "change-moi-en-production")
DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"
