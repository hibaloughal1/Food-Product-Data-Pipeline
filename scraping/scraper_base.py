"""
scraper_base.py
================
Classe de base pour tous les scrapers de sites d'enseignes.

Conformément à la contrainte de maintenabilité (2.6.4) : "l'ajout d'un
nouveau site concurrent devra pouvoir être réalisé sans modifier toute
l'architecture du projet", chaque enseigne est implémentée comme une
sous-classe de `BaseScraper` qui ne redéfinit que :
    - la liste des URLs de catégories à parcourir (`category_urls`)
    - la méthode `parse_product_list(html)` -> liste de dicts bruts
    - éventuellement `parse_product_detail(html)` pour enrichir la fiche

Le comportement commun (requêtes HTTP, délais, retries, logging,
journalisation dans la table Scraping) est géré ici une seule fois.
"""

import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import requests
from requests.exceptions import RequestException

import config

logging.basicConfig(
    filename=str(config.LOGS_DIR / "scraping.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class BaseScraper(ABC):
    """Scraper générique basé sur requests + un parseur HTML (BeautifulSoup)."""

    #: Nom de l'enseigne tel qu'il apparaît en base (table Enseigne.nom)
    nom_enseigne: str = "Inconnue"

    #: Liste des URLs de catégories à parcourir
    category_urls: list[str] = []

    def __init__(self, session: requests.Session | None = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.http = session or requests.Session()
        self.http.headers.update({"User-Agent": config.USER_AGENT})

    # ------------------------------------------------------------------
    # Méthodes à implémenter par chaque enseigne
    # ------------------------------------------------------------------
    @abstractmethod
    def parse_product_list(self, html: str) -> list[dict]:
        """
        Doit retourner une liste de dictionnaires bruts avec, au minimum,
        les clés : nom, reference, prix_normal (les autres sont optionnelles :
        prix_promotion, categorie, marque, image, url_fiche, date_debut,
        date_fin).
        """
        raise NotImplementedError

    def get_next_page_url(self, html: str, current_url: str) -> str | None:
        """Pagination : à surcharger si le site possède plusieurs pages
        par catégorie. Retourne None s'il n'y a pas de page suivante."""
        return None

    # ------------------------------------------------------------------
    # Logique commune (requêtes, retries, délais anti-blocage)
    # ------------------------------------------------------------------
    def _fetch(self, url: str) -> str | None:
        for tentative in range(1, config.MAX_RETRIES + 1):
            try:
                resp = self.http.get(url, timeout=config.REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except RequestException as exc:
                self.logger.warning(
                    "Échec requête %s (tentative %s/%s): %s",
                    url, tentative, config.MAX_RETRIES, exc
                )
                time.sleep(config.REQUEST_DELAY * tentative)
        self.logger.error("Abandon après %s tentatives : %s", config.MAX_RETRIES, url)
        return None

    def run(self) -> dict:
        """
        Exécute le scraping complet de l'enseigne.

        Returns
        -------
        dict avec les clés : site, etat, nb_produits, temps_execution,
        produits (liste de dicts bruts), message_erreur.
        """
        debut = time.time()
        produits: list[dict] = []
        erreur = None

        try:
            for url in self.category_urls:
                page_url = url
                while page_url:
                    self.logger.info("Scraping %s -> %s", self.nom_enseigne, page_url)
                    html = self._fetch(page_url)
                    if html is None:
                        break
                    produits.extend(self.parse_product_list(html))
                    page_url = self.get_next_page_url(html, page_url)
                    time.sleep(config.REQUEST_DELAY)
            etat = "succes"
        except Exception as exc:  # pragma: no cover - robustesse pipeline
            etat = "echec"
            erreur = str(exc)
            self.logger.exception("Erreur durant le scraping de %s", self.nom_enseigne)

        return {
            "site": self.nom_enseigne,
            "etat": etat,
            "nb_produits": len(produits),
            "temps_execution": round(time.time() - debut, 2),
            "produits": produits,
            "message_erreur": erreur,
            "date_execution": datetime.utcnow(),
        }
