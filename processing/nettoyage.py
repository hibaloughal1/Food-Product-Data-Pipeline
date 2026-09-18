"""
nettoyage.py
============
Module de nettoyage des données brutes collectées, conforme aux besoins
fonctionnels 2.4.4 :
  - suppression des doublons
  - suppression des espaces inutiles
  - uniformisation des références
  - normalisation des noms de produits
  - correction des formats numériques
  - gestion des valeurs manquantes
  - suppression des caractères spéciaux inutiles
  - correction des erreurs d'encodage
"""

import re
import unicodedata

CARACTERES_INDESIRABLES = re.compile(r"[^\w\s\-.,%()àâäéèêëïîôöùûüçÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]")
ESPACES_MULTIPLES = re.compile(r"\s+")


def _corriger_encodage(texte: str) -> str:
    """Corrige les erreurs d'encodage courantes (ex: 'Ã©' -> 'é')."""
    if not texte:
        return texte
    try:
        texte = texte.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return unicodedata.normalize("NFC", texte)


def normaliser_nom(nom: str | None) -> str | None:
    """Uniformise un nom de produit : espaces, casse, caractères parasites."""
    if not nom:
        return None
    nom = _corriger_encodage(nom)
    nom = CARACTERES_INDESIRABLES.sub(" ", nom)
    nom = ESPACES_MULTIPLES.sub(" ", nom).strip()
    # Casse "Titre" : première lettre de chaque mot en majuscule, reste inchangé
    return nom[:255] if nom else None


def normaliser_reference(reference: str | None, nom_secours: str | None = None) -> str:
    """Uniformise une référence produit (majuscules, sans espaces)."""
    ref = reference or nom_secours or "REF-INCONNUE"
    ref = _corriger_encodage(str(ref))
    ref = re.sub(r"\s+", "-", ref.strip())
    ref = re.sub(r"[^A-Za-z0-9\-_.]", "", ref)
    return ref.upper()[:100]


def normaliser_prix(valeur) -> float | None:
    """Corrige le format numérique d'un prix (virgule/point, texte parasite)."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, (int, float)):
        return round(float(valeur), 2) if valeur > 0 else None
    texte = str(valeur)
    texte = re.sub(r"(DH|Dh|dh|MAD|€|\s)", "", texte)
    texte = texte.replace(",", ".")
    try:
        prix = float(texte)
        return round(prix, 2) if prix > 0 else None
    except ValueError:
        return None


def normaliser_categorie(categorie: str | None) -> str:
    if not categorie:
        return "Non catégorisé"
    categorie = _corriger_encodage(categorie)
    return ESPACES_MULTIPLES.sub(" ", categorie.strip()).title()


def nettoyer_produit(produit_brut: dict) -> dict | None:
    """
    Applique l'ensemble des règles de nettoyage à un produit brut issu du
    scraping ou de l'extraction PDF.

    Retourne None si le produit ne peut pas être exploité (nom absent),
    conformément à la gestion des valeurs manquantes.
    """
    nom = normaliser_nom(produit_brut.get("nom"))
    if not nom:
        return None  # valeur manquante critique -> produit rejeté

    prix_normal = normaliser_prix(produit_brut.get("prix_normal"))
    prix_promotion = normaliser_prix(produit_brut.get("prix_promotion"))

    # Si aucun prix normal mais un prix promo existe, on utilise le promo
    # comme prix de référence pour ne pas perdre l'information (2.6.3 fiabilité)
    if prix_normal is None and prix_promotion is not None:
        prix_normal = prix_promotion
        prix_promotion = None

    return {
        "nom": nom,
        "reference": normaliser_reference(produit_brut.get("reference"), nom),
        "marque": normaliser_nom(produit_brut.get("marque")) if produit_brut.get("marque") else None,
        "categorie": normaliser_categorie(produit_brut.get("categorie")),
        "prix_normal": prix_normal,
        "prix_promotion": prix_promotion,
        "image": (produit_brut.get("image") or "").strip() or None,
        "url_fiche": (produit_brut.get("url_fiche") or "").strip() or None,
        "date_debut": produit_brut.get("date_debut"),
        "date_fin": produit_brut.get("date_fin"),
    }


def supprimer_doublons(produits: list[dict]) -> list[dict]:
    """
    Supprime les doublons sur la base du couple (reference, nom normalisé).
    Conserve la première occurrence rencontrée.
    """
    vus = set()
    resultat = []
    for p in produits:
        cle = (p["reference"], p["nom"].lower())
        if cle in vus:
            continue
        vus.add(cle)
        resultat.append(p)
    return resultat


def nettoyer_lot(produits_bruts: list[dict]) -> list[dict]:
    """Pipeline complet de nettoyage appliqué à une liste de produits bruts."""
    nettoyes = [nettoyer_produit(p) for p in produits_bruts]
    nettoyes = [p for p in nettoyes if p is not None]
    return supprimer_doublons(nettoyes)
