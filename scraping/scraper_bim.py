"""
scraper_bim.py
==============
Exemple de connecteur pour l'enseigne BIM Maroc.

IMPORTANT : les sélecteurs CSS ci-dessous (`select`, `select_one`) sont des
EXEMPLES à adapter une fois que tu inspecteras le HTML réel du site cible
(clic droit > Inspecter sur une page produit). La structure d'un site peut
changer à tout moment (risque identifié en 12.2 : "Modification de la
structure HTML"), c'est pourquoi tout le code spécifique au site est
isolé dans cette seule classe.

Pour trouver les bons sélecteurs :
  1. Ouvrir la page catégorie du site dans le navigateur.
  2. Inspecter un bloc "carte produit" (nom, prix, image...).
  3. Repérer les classes CSS utilisées et les reporter ci-dessous.

Si le site charge son contenu en JavaScript (React/Vue/Angular), `requests`
ne suffira pas : utiliser Playwright/Selenium à la place (voir
scraping/scraper_dynamic_template.py).
"""

from bs4 import BeautifulSoup

from scraping.scraper_base import BaseScraper


class BimScraper(BaseScraper):
    nom_enseigne = "BIM"

    # À remplacer par les vraies URLs de catégories du site BIM
    category_urls = [
        "https://www.bim.ma/fr/promotions",
    ]

    def parse_product_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        produits = []

        # --- EXEMPLE : à adapter selon la structure réelle du site ---
        cartes = soup.select(".product-card, .product-item, .promo-card")

        for carte in cartes:
            nom_el = carte.select_one(".product-title, .product-name, h3")
            prix_el = carte.select_one(".price, .product-price")
            prix_promo_el = carte.select_one(".price-promo, .old-price ~ .price")
            img_el = carte.select_one("img")
            lien_el = carte.select_one("a")
            ref_el = carte.get("data-reference") or carte.get("data-sku")

            if not nom_el or not prix_el:
                continue

            produits.append({
                "nom": nom_el.get_text(strip=True),
                "reference": ref_el or nom_el.get_text(strip=True)[:50],
                "marque": None,
                "categorie": None,
                "prix_normal": self._parse_prix(prix_el.get_text(strip=True)),
                "prix_promotion": self._parse_prix(prix_promo_el.get_text(strip=True)) if prix_promo_el else None,
                "image": img_el.get("src") if img_el else None,
                "url_fiche": lien_el.get("href") if lien_el else None,
                "date_debut": None,
                "date_fin": None,
            })

        return produits

    @staticmethod
    def _parse_prix(texte: str) -> float | None:
        """Convertit '129,90 DH' -> 129.90"""
        if not texte:
            return None
        nettoye = (
            texte.replace("DH", "").replace("Dh", "").replace("MAD", "")
            .replace("\xa0", "").replace(" ", "").replace(",", ".")
            .strip()
        )
        try:
            return float(nettoye)
        except ValueError:
            return None
