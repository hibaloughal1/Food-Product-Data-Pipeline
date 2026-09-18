"""
catalogue_pdf.py
=================
Module de collecte et d'extraction des catalogues promotionnels au format
PDF.

Stratégie en deux temps :
  1. Tentative d'extraction directe du texte (pdfplumber) -> rapide, fiable
     quand le PDF contient du texte réel (pas juste des images scannées).
  2. Si aucun texte n'est trouvé sur une page (catalogue "image"), bascule
     automatique sur l'OCR (EasyOCR ou Tesseract) après rasterisation de
     la page en image.

Les prix et références sont ensuite repérés dans le texte brut à l'aide
d'expressions régulières simples, à affiner selon la mise en page réelle
des catalogues traités.
"""

import re
import io
import logging
from datetime import datetime
from pathlib import Path

import requests
import pdfplumber

import config

logging.basicConfig(
    filename=str(config.LOGS_DIR / "catalogue_pdf.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("catalogue_pdf")

# Regex d'extraction — à ajuster selon le format observé dans les catalogues
PRIX_REGEX = re.compile(r"(\d{1,4}[.,]\d{2})\s*(?:DH|Dh|MAD)?")
REDUCTION_REGEX = re.compile(r"-\s?(\d{1,3})\s?%")


def telecharger_catalogue(url: str, nom_fichier: str | None = None) -> Path:
    """Télécharge un catalogue PDF depuis une URL (2.4.3)."""
    nom_fichier = nom_fichier or url.split("/")[-1] or f"catalogue_{datetime.utcnow():%Y%m%d%H%M%S}.pdf"
    destination = config.CATALOGUES_DIR / nom_fichier

    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    destination.write_bytes(resp.content)
    logger.info("Catalogue téléchargé : %s", destination)
    return destination


def _extraire_texte_ocr(page) -> str:
    """Rasterise la page et applique l'OCR (Tesseract via pytesseract)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.error("pytesseract/Pillow non installés — impossible de faire l'OCR.")
        return ""

    image = page.to_image(resolution=200).original
    if not isinstance(image, Image.Image):
        buf = io.BytesIO()
        page.to_image(resolution=200).save(buf, format="PNG")
        buf.seek(0)
        image = Image.open(buf)

    texte = pytesseract.image_to_string(image, lang=config.OCR_LANG)
    return texte


def extraire_produits_catalogue(chemin_pdf: Path) -> list[dict]:
    """
    Parcourt chaque page du PDF, extrait le texte (avec fallback OCR),
    puis repère les motifs prix/réduction pour construire une liste de
    produits bruts.

    Le découpage précis "1 bloc = 1 produit" dépend fortement de la mise
    en page du catalogue ; ici on regroupe le texte ligne par ligne et on
    associe chaque prix trouvé à la ligne de texte la plus proche (nom
    probable du produit), ce qui donne un résultat exploitable pour la
    majorité des catalogues simples et sert de base à affiner.
    """
    produits = []

    with pdfplumber.open(chemin_pdf) as pdf:
        for num_page, page in enumerate(pdf.pages, start=1):
            texte = page.extract_text() or ""

            if not texte.strip():
                logger.info("Page %s sans texte détecté -> bascule OCR", num_page)
                texte = _extraire_texte_ocr(page)

            lignes = [l.strip() for l in texte.splitlines() if l.strip()]

            for i, ligne in enumerate(lignes):
                match_prix = PRIX_REGEX.search(ligne)
                if not match_prix:
                    continue

                prix = float(match_prix.group(1).replace(",", "."))
                match_reduc = REDUCTION_REGEX.search(ligne)
                reduction = int(match_reduc.group(1)) if match_reduc else None

                # Le nom du produit est supposé être sur la ligne précédente
                nom_probable = lignes[i - 1] if i > 0 else f"Produit page {num_page}"

                prix_normal = prix
                prix_promotion = None
                if reduction:
                    prix_promotion = prix
                    prix_normal = round(prix / (1 - reduction / 100), 2)

                produits.append({
                    "nom": nom_probable[:255],
                    "reference": f"CAT-{num_page}-{i}",
                    "marque": None,
                    "categorie": None,
                    "prix_normal": prix_normal,
                    "prix_promotion": prix_promotion,
                    "image": None,
                    "url_fiche": None,
                    "date_debut": None,
                    "date_fin": None,
                    "source_page": num_page,
                })

    logger.info("Catalogue %s -> %s produits candidats extraits", chemin_pdf.name, len(produits))
    return produits
