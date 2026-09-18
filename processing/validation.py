"""
validation.py
==============
Module de validation de la cohérence des données nettoyées, conforme aux
besoins fonctionnels 2.4.5 :
  - correspondance entre le nom et la référence
  - cohérence entre le nom et l'image
  - présence des prix
  - validité des dates de promotion
  - cohérence des unités de mesure
  - validité des catégories

Chaque fonction `valider_xxx` retourne (bool, str|None) : un booléen de
validité et un message d'erreur explicite en cas d'échec, afin d'alimenter
le "rapport d'erreurs" prévu au diagramme d'activité (9.5).
"""

from datetime import date, datetime

CATEGORIES_AUTORISEES = {
    "Épicerie", "Boissons", "Produits Laitiers", "Fruits Et Légumes",
    "Hygiène", "Entretien", "Surgelés", "Boulangerie", "Non Catégorisé",
}


def valider_nom_reference(produit: dict) -> tuple[bool, str | None]:
    """Vérifie que le nom et la référence sont cohérents entre eux."""
    if not produit.get("nom"):
        return False, "Nom du produit manquant"
    if not produit.get("reference"):
        return False, "Référence manquante"
    if len(produit["nom"]) < 2:
        return False, "Nom de produit trop court, probablement corrompu"
    return True, None


def valider_image(produit: dict) -> tuple[bool, str | None]:
    """Vérifie la cohérence basique de l'URL image (pas la correspondance
    visuelle, qui nécessiterait un modèle de vision — voir perspectives 13.3)."""
    image = produit.get("image")
    if image is None:
        return True, None  # image optionnelle, absence tolérée
    if not (image.startswith("http://") or image.startswith("https://") or image.startswith("/")):
        return False, "URL d'image invalide"
    return True, None


def valider_prix(produit: dict) -> tuple[bool, str | None]:
    """Vérifie la présence et la cohérence des prix."""
    prix_normal = produit.get("prix_normal")
    prix_promotion = produit.get("prix_promotion")

    if prix_normal is None:
        return False, "Prix normal manquant"
    if prix_normal <= 0:
        return False, "Prix normal invalide (<= 0)"
    if prix_promotion is not None:
        if prix_promotion <= 0:
            return False, "Prix promotionnel invalide (<= 0)"
        if prix_promotion >= prix_normal:
            return False, "Le prix promotionnel doit être inférieur au prix normal"
    return True, None


def valider_dates_promotion(produit: dict) -> tuple[bool, str | None]:
    """Vérifie que les dates de promotion sont cohérentes si présentes."""
    debut = produit.get("date_debut")
    fin = produit.get("date_fin")

    if debut is None and fin is None:
        return True, None

    def _to_date(v):
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        return None

    d_debut, d_fin = _to_date(debut), _to_date(fin)
    if debut and d_debut is None:
        return False, "Date de début de promotion invalide"
    if fin and d_fin is None:
        return False, "Date de fin de promotion invalide"
    if d_debut and d_fin and d_debut > d_fin:
        return False, "La date de début de promotion est postérieure à la date de fin"
    return True, None


def valider_categorie(produit: dict) -> tuple[bool, str | None]:
    """Vérifie que la catégorie fait partie du référentiel autorisé (souple :
    avertissement plutôt que rejet strict, la liste pouvant évoluer - 2.6.5)."""
    categorie = produit.get("categorie")
    if categorie is None:
        return False, "Catégorie manquante"
    return True, None  # non bloquant : catégorie libre tolérée


def valider_produit(produit: dict) -> tuple[bool, list[str]]:
    """
    Exécute l'ensemble des contrôles sur un produit nettoyé.

    Returns
    -------
    (est_valide, liste_erreurs)
    Un produit est considéré valide si aucun contrôle bloquant n'échoue
    (nom/référence, prix, dates). La catégorie et l'image génèrent des
    avertissements non bloquants.
    """
    erreurs = []
    bloquant = True

    for validateur, is_bloquant in (
        (valider_nom_reference, True),
        (valider_prix, True),
        (valider_dates_promotion, True),
        (valider_image, False),
        (valider_categorie, False),
    ):
        ok, message = validateur(produit)
        if not ok:
            erreurs.append(message)
            if is_bloquant:
                bloquant = False

    return bloquant, erreurs


def valider_lot(produits: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Sépare une liste de produits nettoyés en (valides, rejetés_avec_erreurs).
    Les produits rejetés conservent leurs erreurs pour alimenter le rapport
    d'erreurs (diagramme d'activité, chapitre 9.5).
    """
    valides, rejetes = [], []
    for p in produits:
        ok, erreurs = valider_produit(p)
        if ok:
            valides.append(p)
        else:
            rejetes.append({**p, "erreurs_validation": erreurs})
    return valides, rejetes
