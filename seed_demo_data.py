"""
seed_demo_data.py
==================
Génère un jeu de données de démonstration réaliste afin de pouvoir tester
et présenter le dashboard immédiatement, sans dépendre de la disponibilité
des vrais sites concurrents (utile pour une soutenance ou une démo).

Usage :
    python seed_demo_data.py
"""

import random
from datetime import datetime, timedelta

from database import get_session, init_db
from models import Enseigne, Produit, HistoriquePrix, Scraping

random.seed(42)

ENSEIGNES = ["BIM", "Marjane", "Carrefour Market", "Aswak Assalam"]

CATALOGUE_PRODUITS = [
    ("Huile d'olive extra vierge 1L", "Épicerie", "Ola"),
    ("Riz basmati 1kg", "Épicerie", "Dari"),
    ("Sucre blanc 2kg", "Épicerie", "Cosumar"),
    ("Farine de blé 5kg", "Épicerie", "Moulin d'Or"),
    ("Lait demi-écrémé 1L", "Produits Laitiers", "Centrale Danone"),
    ("Yaourt nature x8", "Produits Laitiers", "Danone"),
    ("Fromage frais 500g", "Produits Laitiers", "Jibal"),
    ("Beurre doux 250g", "Produits Laitiers", "President"),
    ("Eau minérale 1.5L x6", "Boissons", "Sidi Ali"),
    ("Jus d'orange 1L", "Boissons", "Marrakech"),
    ("Café moulu 250g", "Boissons", "Café Extra"),
    ("Thé vert 25 sachets", "Boissons", "Sultan"),
    ("Tomates fraîches 1kg", "Fruits Et Légumes", "Local"),
    ("Pommes Golden 1kg", "Fruits Et Légumes", "Local"),
    ("Bananes 1kg", "Fruits Et Légumes", "Import"),
    ("Poulet entier frais 1kg", "Épicerie", "Koutoubia"),
    ("Pâtes spaghetti 500g", "Épicerie", "Panzani"),
    ("Conserve thon 3x160g", "Épicerie", "Titus"),
    ("Lessive liquide 3L", "Entretien", "Ariel"),
    ("Liquide vaisselle 1L", "Entretien", "Paic"),
    ("Papier toilette x12", "Hygiène", "Nouba"),
    ("Shampoing 400ml", "Hygiène", "Head&Shoulders"),
    ("Pain de mie complet", "Boulangerie", "Panetti"),
    ("Croissants x6", "Boulangerie", "Maison"),
    ("Poisson surgelé 1kg", "Surgelés", "Copêche"),
    ("Légumes surgelés mélangés 1kg", "Surgelés", "Bonduelle"),
]


def _generer_prix_base(nom: str) -> float:
    """Prix de base pseudo-réaliste selon un hash simple du nom."""
    return round(10 + (abs(hash(nom)) % 1500) / 10, 2)


def main():
    init_db()

    with get_session() as session:
        # Reset des données existantes pour repartir sur une base propre
        session.query(HistoriquePrix).delete()
        session.query(Scraping).delete()
        session.query(Produit).delete()
        session.query(Enseigne).delete()
        session.flush()

        enseignes_db = {}
        for nom in ENSEIGNES:
            e = Enseigne(nom=nom, url=f"https://www.{nom.lower().replace(' ', '')}.ma")
            session.add(e)
            session.flush()
            enseignes_db[nom] = e

        for nom_enseigne, enseigne in enseignes_db.items():
            scraping = Scraping(
                date_execution=datetime.utcnow() - timedelta(hours=random.randint(0, 12)),
                site=nom_enseigne,
                temps_execution=round(random.uniform(5, 40), 2),
                etat="succes",
                nb_produits=len(CATALOGUE_PRODUITS),
                id_enseigne=enseigne.id_enseigne,
            )
            session.add(scraping)
            session.flush()

            for nom_produit, categorie, marque in CATALOGUE_PRODUITS:
                base = _generer_prix_base(nom_produit)
                # Chaque enseigne pratique un prix légèrement différent
                variation = random.uniform(0.85, 1.15)
                prix_normal = round(base * variation, 2)

                en_promo = random.random() < 0.3
                prix_promo = round(prix_normal * random.uniform(0.6, 0.9), 2) if en_promo else None

                produit = Produit(
                    reference=f"{nom_enseigne[:3].upper()}-{abs(hash(nom_produit)) % 10000}",
                    nom=nom_produit,
                    marque=marque,
                    categorie=categorie,
                    image=None,
                    url_fiche=None,
                    id_enseigne=enseigne.id_enseigne,
                )
                session.add(produit)
                session.flush()

                # Historique sur 14 jours pour permettre le graphique d'évolution
                for jour in range(14, -1, -1):
                    date_collecte = datetime.utcnow() - timedelta(days=jour)
                    fluctuation = random.uniform(0.97, 1.03)
                    hp = HistoriquePrix(
                        prix_normal=round(prix_normal * fluctuation, 2),
                        prix_promotion=prix_promo if (en_promo and jour <= 5) else None,
                        date_debut=(datetime.utcnow() - timedelta(days=5)).date() if en_promo else None,
                        date_fin=(datetime.utcnow() + timedelta(days=3)).date() if en_promo else None,
                        date_collecte=date_collecte,
                        id_produit=produit.id_produit,
                        id_scraping=scraping.id_scraping,
                    )
                    session.add(hp)

    print("✅ Données de démonstration générées avec succès.")
    print(f"   {len(ENSEIGNES)} enseignes × {len(CATALOGUE_PRODUITS)} produits × 15 jours d'historique.")


if __name__ == "__main__":
    main()
