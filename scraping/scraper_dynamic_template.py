"""
scraper_dynamic_template.py
============================
Modèle à copier pour les sites qui chargent leurs produits en JavaScript
(contrainte 2.7.1 : "certaines pages sont générées dynamiquement... certaines
données sont chargées uniquement après plusieurs secondes").

Utilise Playwright (recommandé, plus stable que Selenium) au lieu de
`requests`. Installation :
    pip install playwright
    playwright install chromium

Exemple d'utilisation :
    scraper = DynamicScraperTemplate()
    resultat = scraper.run()
"""

import time
from datetime import datetime

from playwright.sync_api import sync_playwright

import config
from scraping.scraper_base import BaseScraper


class DynamicScraperTemplate(BaseScraper):
    nom_enseigne = "Enseigne dynamique (exemple)"
    category_urls = ["https://exemple.com/promotions"]

    # Sélecteur CSS à attendre avant de considérer que la page est chargée
    selecteur_attente = ".product-card"

    def run(self) -> dict:
        debut = time.time()
        produits = []
        etat = "succes"
        erreur = None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=config.USER_AGENT)

                for url in self.category_urls:
                    page.goto(url, timeout=config.REQUEST_TIMEOUT * 1000)
                    page.wait_for_selector(self.selecteur_attente, timeout=10000)
                    html = page.content()
                    produits.extend(self.parse_product_list(html))
                    time.sleep(config.REQUEST_DELAY)

                browser.close()
        except Exception as exc:
            etat = "echec"
            erreur = str(exc)
            self.logger.exception("Erreur scraping dynamique %s", self.nom_enseigne)

        return {
            "site": self.nom_enseigne,
            "etat": etat,
            "nb_produits": len(produits),
            "temps_execution": round(time.time() - debut, 2),
            "produits": produits,
            "message_erreur": erreur,
            "date_execution": datetime.utcnow(),
        }

    def parse_product_list(self, html: str) -> list[dict]:
        # Réutiliser BeautifulSoup comme dans scraper_bim.py une fois le
        # HTML final (post-JavaScript) récupéré via page.content().
        raise NotImplementedError("À implémenter selon le site cible.")
