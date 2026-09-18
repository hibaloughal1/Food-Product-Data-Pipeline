"""
scraper_marjane.py
===================
Connecteur d'exemple pour l'enseigne Marjane (même principe que scraper_bim.py :
sélecteurs à adapter au HTML réel du site cible).
"""

from bs4 import BeautifulSoup

from scraping.scraper_base import BaseScraper
from scraping.scraper_bim import BimScraper  # réutilise le parseur de prix


class MarjaneScraper(BaseScraper):
    nom_enseigne = "Marjane"

    category_urls = [
        "https://www.marjane.ma/epicerie.html",
    ]

    def get_next_page_url(self, html: str, current_url: str):
        """Exemple de gestion de pagination (bouton 'page suivante')."""
        soup = BeautifulSoup(html, "html.parser")
        lien_suivant = soup.select_one("a.pagination-next, a[rel='next']")
        if lien_suivant and lien_suivant.get("href"):
            return lien_suivant["href"]
        return None

    def parse_product_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        produits = []

        cartes = soup.select(".product-item-info, .item.product")

        for carte in cartes:
            nom_el = carte.select_one(".product-item-link, .product-name")
            prix_el = carte.select_one(".price")
            categorie_el = carte.get("data-category")
            img_el = carte.select_one("img")
            lien_el = carte.select_one("a")
            ref_el = carte.get("data-product-id")

            if not nom_el or not prix_el:
                continue

            produits.append({
                "nom": nom_el.get_text(strip=True),
                "reference": ref_el or nom_el.get_text(strip=True)[:50],
                "marque": None,
                "categorie": categorie_el,
                "prix_normal": BimScraper._parse_prix(prix_el.get_text(strip=True)),
                "prix_promotion": None,
                "image": img_el.get("data-src") or img_el.get("src") if img_el else None,
                "url_fiche": lien_el.get("href") if lien_el else None,
                "date_debut": None,
                "date_fin": None,
            })

        return produits
