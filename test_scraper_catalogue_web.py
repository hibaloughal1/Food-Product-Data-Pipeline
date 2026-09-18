"""
test_scraper_catalogue_web.py
==============================
Valide l'extraction du scraper de catalogues web (scraping/scraper_catalogue_web.py)
contre un contenu RÉEL récupéré le 01/07/2026 depuis hmizate.ma (article
"Catalogue Kazyon du 25 juin 2026"), figé dans
tests_fixtures/kazyon_25juin2026_reconstruit.html pour un test reproductible.

Usage :
    python test_scraper_catalogue_web.py
"""

from pathlib import Path

from scraping.scraper_catalogue_web import CatalogueWebScraper

FIXTURE = Path(__file__).parent / "tests_fixtures" / "kazyon_25juin2026_reconstruit.html"

# Vérité terrain relevée manuellement dans l'article source réel
# (uniquement des produits ALIMENTAIRES — le scraper doit exclure tout le
# reste : climatiseur, ventilateur, piscine, table de plage, hygiène...)
ATTENDUS = {
    "yaourt velouté danone 110 g x 8": (16.95, 19.95),
    "lait uht demi-écrémé jaouda 500 ml": (4.50, None),
    "farine luxe sania 25 kg": (79.90, None),
    "thon à l'huile végétale atlanta 80 g x 3": (15.95, 20.95),
    "café moulu moka carrion 200 g": (28.50, None),
}

# Produits non-alimentaires qui NE DOIVENT PAS apparaître dans le résultat
EXCLUS_ATTENDUS = [
    "climatiseur tcl 9000 btu inverter",
    "ventilateur à pied kenz 18 pouces",
    "table de plage",
    "piscine ronde bestway",
]


def main():
    html = FIXTURE.read_text(encoding="utf-8")
    scraper = CatalogueWebScraper(nom_enseigne="Kazyon", categorie_url="https://hmizate.ma/deal/catalogue-kazyon-c26")
    produits = scraper.parse_article(html, "test")

    index = {
        p["nom"].lower(): (p["prix_promotion"] or p["prix_normal"], p["prix_normal"] if p["prix_promotion"] else None)
        for p in produits
    }

    reussites = 0
    for nom, (prix_attendu, normal_attendu) in ATTENDUS.items():
        trouve = index.get(nom)
        ok = bool(trouve) and abs(trouve[0] - prix_attendu) < 0.01 and trouve[1] == normal_attendu
        reussites += int(ok)
        print(f"{'OK   ' if ok else 'ECHEC'} {nom:50} attendu={prix_attendu}/{normal_attendu}  trouvé={trouve}")

    print("\n--- Vérification de l'exclusion des produits non-alimentaires ---")
    exclusion_ok = 0
    for nom in EXCLUS_ATTENDUS:
        absent = nom not in index
        exclusion_ok += int(absent)
        print(f"{'OK   ' if absent else 'ECHEC'} '{nom}' correctement exclu : {absent}")

    total_ok = reussites + exclusion_ok
    total = len(ATTENDUS) + len(EXCLUS_ATTENDUS)
    print(f"\n{total_ok}/{total} vérifications passées — {len(produits)} produits alimentaires extraits au total.")
    assert total_ok == total, "Certaines vérifications ont échoué."
    print("✅ Le parseur extrait correctement les produits alimentaires et exclut le reste.")


if __name__ == "__main__":
    main()
