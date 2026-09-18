"""
pipeline.py
===========
Orchestrateur du pipeline complet de collecte :

    Scraping (site web ou catalogue PDF)
        -> Nettoyage
        -> Validation
        -> Alimentation de la base de données
        -> (Rapport d'erreurs pour les produits rejetés)

Utilisation en ligne de commande :
    python -m processing.pipeline --site bim
    python -m processing.pipeline --site marjane
    python -m processing.pipeline --toutes
    python -m processing.pipeline --catalogue chemin/vers/catalogue.pdf --enseigne "Carrefour Market"
"""

import argparse
import logging
from datetime import datetime

from database import get_session, init_db
from models import Enseigne, Produit, HistoriquePrix, Scraping
from processing.nettoyage import nettoyer_lot
from processing.validation import valider_lot
from scraping.scraper_bim import BimScraper
from scraping.scraper_marjane import MarjaneScraper
from scraping.scraper_catalogue_web import ENSEIGNES_CATALOGUE_WEB, creer_scraper
from scraping.catalogue_pdf import extraire_produits_catalogue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

# Scrapers "site e-commerce direct" (à utiliser seulement si l'enseigne
# possède une vraie boutique en ligne non protégée par anti-bot — voir
# scraping/scraper_bim.py et scraper_marjane.py pour le détail).
SCRAPERS_DISPONIBLES = {
    "bim": BimScraper,
    "marjane": MarjaneScraper,
}

# Scrapers "catalogues web" (RECOMMANDÉ) : source réelle et fonctionnelle
# dès aujourd'hui, republiant les catalogues promotionnels BIM/Marjane/
# Kazyon/Carrefour/Aswak Assalam sous forme de texte structuré exploitable.
# Voir scraping/scraper_catalogue_web.py pour le détail et la justification.
ENSEIGNES_CATALOGUE_WEB_DISPONIBLES = ENSEIGNES_CATALOGUE_WEB


def _get_or_create_enseigne(session, nom: str, url: str | None = None) -> Enseigne:
    enseigne = session.query(Enseigne).filter_by(nom=nom).first()
    if enseigne is None:
        enseigne = Enseigne(nom=nom, url=url)
        session.add(enseigne)
        session.flush()  # pour obtenir l'id_enseigne
    return enseigne


def _enregistrer_scraping(session, enseigne: Enseigne, resultat_brut: dict) -> Scraping:
    scraping = Scraping(
        date_execution=resultat_brut.get("date_execution", datetime.utcnow()),
        site=resultat_brut["site"],
        temps_execution=resultat_brut["temps_execution"],
        etat=resultat_brut["etat"],
        nb_produits=resultat_brut["nb_produits"],
        message_erreur=resultat_brut.get("message_erreur"),
        id_enseigne=enseigne.id_enseigne,
    )
    session.add(scraping)
    session.flush()
    return scraping


def _alimenter_base(session, enseigne: Enseigne, scraping: Scraping, produits_valides: list[dict]) -> int:
    """Étape 'Alimenter la base' du diagramme de cas d'utilisation (9.2)."""
    compteur = 0
    for p in produits_valides:
        produit_db = (
            session.query(Produit)
            .filter_by(reference=p["reference"], id_enseigne=enseigne.id_enseigne)
            .first()
        )
        if produit_db is None:
            produit_db = Produit(
                reference=p["reference"],
                nom=p["nom"],
                marque=p.get("marque"),
                categorie=p.get("categorie"),
                image=p.get("image"),
                url_fiche=p.get("url_fiche"),
                id_enseigne=enseigne.id_enseigne,
            )
            session.add(produit_db)
            session.flush()
        else:
            # Mise à jour des informations descriptives (2.4.6)
            produit_db.nom = p["nom"]
            produit_db.categorie = p.get("categorie") or produit_db.categorie
            produit_db.image = p.get("image") or produit_db.image

        historique = HistoriquePrix(
            prix_normal=p["prix_normal"],
            prix_promotion=p.get("prix_promotion"),
            date_debut=p.get("date_debut"),
            date_fin=p.get("date_fin"),
            date_collecte=datetime.utcnow(),
            id_produit=produit_db.id_produit,
            id_scraping=scraping.id_scraping,
        )
        session.add(historique)
        compteur += 1

    return compteur


def executer_pipeline_site(nom_site: str) -> dict:
    """Exécute le pipeline complet pour un site web donné (2.4.1 à 2.4.6)."""
    if nom_site not in SCRAPERS_DISPONIBLES:
        raise ValueError(f"Scraper inconnu : {nom_site}. Disponibles : {list(SCRAPERS_DISPONIBLES)}")

    scraper_cls = SCRAPERS_DISPONIBLES[nom_site]
    scraper = scraper_cls()

    logger.info("=== Lancement du scraping : %s ===", scraper.nom_enseigne)
    resultat_brut = scraper.run()

    produits_nettoyes = nettoyer_lot(resultat_brut["produits"])
    produits_valides, produits_rejetes = valider_lot(produits_nettoyes)

    logger.info(
        "%s : %s bruts -> %s nettoyés -> %s valides / %s rejetés",
        scraper.nom_enseigne, resultat_brut["nb_produits"],
        len(produits_nettoyes), len(produits_valides), len(produits_rejetes),
    )

    with get_session() as session:
        enseigne = _get_or_create_enseigne(session, scraper.nom_enseigne, scraper.category_urls[0] if scraper.category_urls else None)
        scraping = _enregistrer_scraping(session, enseigne, resultat_brut)
        nb_inseres = _alimenter_base(session, enseigne, scraping, produits_valides)

    return {
        "enseigne": scraper.nom_enseigne,
        "nb_bruts": resultat_brut["nb_produits"],
        "nb_valides": len(produits_valides),
        "nb_rejetes": len(produits_rejetes),
        "erreurs": produits_rejetes,
        "nb_inseres": nb_inseres,
    }


def executer_pipeline_catalogue_web(cle_enseigne: str, max_articles: int = 12) -> dict:
    """
    Exécute le pipeline complet via le scraper de catalogues web réel
    (RECOMMANDÉ — voir scraping/scraper_catalogue_web.py). Fonctionne
    dès aujourd'hui pour bim, marjane, kazyon, carrefour, aswak_assalam.

    max_articles : plus ce nombre est élevé, plus le volume de produits
    alimentaires collectés est important (remonte plus loin dans
    l'historique des catalogues de l'enseigne).
    """
    scraper = creer_scraper(cle_enseigne, max_articles=max_articles)

    logger.info("=== Lancement du scraping catalogue web : %s ===", scraper.nom_enseigne)
    resultat_brut = scraper.run()

    produits_nettoyes = nettoyer_lot(resultat_brut["produits"])
    produits_valides, produits_rejetes = valider_lot(produits_nettoyes)

    logger.info(
        "%s : %s bruts -> %s nettoyés -> %s valides / %s rejetés",
        scraper.nom_enseigne, resultat_brut["nb_produits"],
        len(produits_nettoyes), len(produits_valides), len(produits_rejetes),
    )

    with get_session() as session:
        enseigne = _get_or_create_enseigne(session, scraper.nom_enseigne, scraper.categorie_url)
        scraping = _enregistrer_scraping(session, enseigne, resultat_brut)
        nb_inseres = _alimenter_base(session, enseigne, scraping, produits_valides)

    return {
        "enseigne": scraper.nom_enseigne,
        "nb_bruts": resultat_brut["nb_produits"],
        "nb_valides": len(produits_valides),
        "nb_rejetes": len(produits_rejetes),
        "erreurs": produits_rejetes,
        "nb_inseres": nb_inseres,
    }


def executer_pipeline_catalogue(chemin_pdf: str, nom_enseigne: str) -> dict:
    """Exécute le pipeline complet pour un catalogue PDF (2.4.3)."""
    from pathlib import Path
    debut = datetime.utcnow()

    produits_bruts = extraire_produits_catalogue(Path(chemin_pdf))
    produits_nettoyes = nettoyer_lot(produits_bruts)
    produits_valides, produits_rejetes = valider_lot(produits_nettoyes)

    resultat_brut = {
        "site": f"{nom_enseigne} (catalogue PDF)",
        "etat": "succes",
        "nb_produits": len(produits_bruts),
        "temps_execution": (datetime.utcnow() - debut).total_seconds(),
        "message_erreur": None,
        "date_execution": debut,
    }

    with get_session() as session:
        enseigne = _get_or_create_enseigne(session, nom_enseigne)
        scraping = _enregistrer_scraping(session, enseigne, resultat_brut)
        nb_inseres = _alimenter_base(session, enseigne, scraping, produits_valides)

    return {
        "enseigne": nom_enseigne,
        "nb_bruts": len(produits_bruts),
        "nb_valides": len(produits_valides),
        "nb_rejetes": len(produits_rejetes),
        "erreurs": produits_rejetes,
        "nb_inseres": nb_inseres,
    }


def executer_toutes_les_sources(max_articles: int = 12):
    """Lance le pipeline pour toutes les enseignes via les scrapers de
    catalogues web réels (recommandé, fonctionnel dès aujourd'hui)."""
    resultats = []
    for cle_enseigne in ENSEIGNES_CATALOGUE_WEB_DISPONIBLES:
        try:
            resultats.append(executer_pipeline_catalogue_web(cle_enseigne, max_articles=max_articles))
        except Exception:
            logger.exception("Échec du pipeline pour %s (poursuite avec les autres sites - 5.3)", cle_enseigne)
    return resultats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de collecte de prix produits")
    parser.add_argument(
        "--enseigne", choices=list(ENSEIGNES_CATALOGUE_WEB_DISPONIBLES),
        help="Scraper une seule enseigne via les catalogues web réels (RECOMMANDÉ)"
    )
    parser.add_argument("--toutes", action="store_true", help="Scraper toutes les enseignes (catalogues web réels)")
    parser.add_argument(
        "--site", choices=list(SCRAPERS_DISPONIBLES),
        help="Scraper via un site e-commerce direct (nécessite d'adapter les sélecteurs CSS)"
    )
    parser.add_argument("--catalogue", help="Chemin vers un catalogue PDF local à traiter")
    parser.add_argument("--enseigne-pdf", help="Nom de l'enseigne associée au catalogue PDF")
    parser.add_argument(
        "--max-articles", type=int, default=12,
        help="Nombre d'articles de catalogue à parcourir par enseigne (défaut : 12). "
             "Augmenter pour collecter plus de produits alimentaires."
    )
    args = parser.parse_args()

    init_db()

    if args.catalogue:
        if not args.enseigne_pdf:
            parser.error("--catalogue nécessite --enseigne-pdf")
        r = executer_pipeline_catalogue(args.catalogue, args.enseigne_pdf)
        print(r)
    elif args.toutes:
        for r in executer_toutes_les_sources(max_articles=args.max_articles):
            print(r)
    elif args.enseigne:
        r = executer_pipeline_catalogue_web(args.enseigne, max_articles=args.max_articles)
        print(r)
    elif args.site:
        r = executer_pipeline_site(args.site)
        print(r)
    else:
        parser.print_help()
