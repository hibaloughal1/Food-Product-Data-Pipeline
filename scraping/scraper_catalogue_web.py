"""
scraper_catalogue_web.py
=========================
Scraper RÉEL et fonctionnel qui collecte des prix de produits ALIMENTAIRES
marocains actuels, sans dépendre d'un site e-commerce direct.

CONTEXTE (vérifié en direct le 01/07/2026) :
  - BIM Maroc ne dispose d'AUCUN site e-commerce : ses promotions ne sont
    publiées que sous forme de catalogues hebdomadaires en image/PDF.
  - Marjane.ma dispose d'une vraie boutique en ligne mais c'est une SPA
    (React) protégée par une détection anti-bot qui bloque les requêtes
    HTTP simples (confirmé : erreur "Site blocked the request").
  - Ce sont exactement les deux cas d'anti-scraping et de catalogues au
    format image/PDF anticipés dès la conception du projet.

SOLUTION RETENUE : hmizate.ma republie chaque semaine le contenu de ces
catalogues (BIM, Marjane, Kazyon, Carrefour, Aswak Assalam...) sous forme
d'articles texte structurés. Ces catalogues mélangent TOUS les rayons
(alimentaire, électroménager, piscine/été, hygiène...). Ce module :

  1. Récupère plusieurs articles récents d'une enseigne (`max_articles`).
  2. Suit les titres de section (<h2>) pour déterminer le rayon courant
     (ex: "Produits frais et laitiers", "Offres été et plage").
  3. Extrait les couples (nom_produit, prix, promo) via deux stratégies :
       a) paragraphes avec texte en gras (bonne précision, avec promo)
       b) liste à puces "Nom : **prix DH**" (complément)
  4. Filtre STRICTEMENT pour ne garder que les produits alimentaires
     (épicerie, produits laitiers, boissons, fruits/légumes, boulangerie,
     surgelés) et exclut l'électroménager, la piscine/plage, l'hygiène,
     l'entretien, le mobilier, les jouets, etc. (voir `est_produit_alimentaire`).

Testé et validé sur du contenu réel récupéré le 01/07/2026 (voir
tests_fixtures/kazyon_25juin2026_reconstruit.html et
test_scraper_catalogue_web.py).
"""

import re

from bs4 import BeautifulSoup

from scraping.scraper_base import BaseScraper

# Regex prix : "319.90 DH", "3599 DH", "16,95 DH"...
PRIX_REGEX = re.compile(r"([\d]+(?:[.,]\d{1,2})?)\s*(?:DH|Dh|MAD)", re.IGNORECASE)

# Regex "au lieu de XX.XX DH" pour détecter le prix normal / la promo
AU_LIEU_DE_REGEX = re.compile(r"au lieu de\s*([\d]+(?:[.,]\d{1,2})?)\s*(?:DH|Dh|MAD)", re.IGNORECASE)

# Regex de la liste à puces "Nom du produit : **prix DH**"
LISTE_PUCE_REGEX = re.compile(r"^([^:]{3,90}):\s*([\d]+(?:[.,]\d{1,2})?)\s*(?:DH|Dh|MAD)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Catégorisation alimentaire — chapitre 2.4.2 / 2.4.4 (uniformisation catégories)
# ---------------------------------------------------------------------------

# Titres de SECTION (<h2>) qui indiquent un rayon alimentaire, avec le
# libellé de catégorie normalisé à appliquer à tous les produits en dessous.
SECTIONS_ALIMENTAIRES = [
    (r"frais|laitiers?|yaourt|fromage", "Produits Laitiers"),
    (r"[ée]picerie|alimentaires?|conserve", "Épicerie"),
    (r"boissons?|jus|eaux?\b", "Boissons"),
    (r"fruits?.{0,3}l[ée]gumes?", "Fruits Et Légumes"),
    (r"boulangerie|p[âa]tisserie|viennoiserie", "Boulangerie"),
    (r"surgel[ée]s?", "Surgelés"),
    (r"petit.d[ée]jeuner|biscuits?|caf[ée]|go[uû]ter|douceurs?", "Épicerie"),
    (r"charcuterie|viandes?|volaille|poissons?", "Épicerie"),
]

# Titres de SECTION qui indiquent explicitement un rayon NON alimentaire
# -> tous les produits de cette section sont exclus, quel que soit leur nom.
SECTIONS_NON_ALIMENTAIRES = [
    r"[ée]t[ée]|plage|piscine|climat|jardin|ext[ée]rieur",
    r"hygi[èe]ne|entretien|m[ée]nage|nettoy",
    r"[ée]lectrom[ée]nager|informatique|multim[ée]dia|t[ée]l[ée]phon|high.?tech",
    r"jouets?|loisirs?|b[ée]b[ée]s?.{0,3}(jouets|puériculture)",
    r"maison.{0,3}d[ée]co|meubles?|bricolage",
    r"mode|v[êe]tements?|chaussures?|beaut[ée]",
]

# Mots-clés produit (fallback quand la section n'est pas identifiable, ex :
# la liste à puces "meilleures offres" qui mélange tous les rayons).
MOTS_NON_ALIMENTAIRES = re.compile(
    r"climatiseur|climatisation|ventilateur|piscine|plage|gonflable|bou[ée]e|"
    r"natation|parasol|tapis\b|meuble|canap[ée]|matelas|t[ée]l[ée]vis|"
    r"\btv\b|smartphone|t[ée]l[ée]phone|ordinateur|tablette\s+(?:tactile|num[ée]rique)|"
    r"montre\s+connect[ée]e|machine\s+[àa]\s+laver|lave.?linge|lave.?vaisselle|"
    r"r[ée]frig[ée]rateur|\bfrigo\b|cong[ée]lateur|four\s+[ée]lectrique|micro.?ondes?|"
    r"aspirateur|fer\s+[àa]\s+repasser|chargeur|batterie|casque\s+audio|enceinte\s+"
    r"bluetooth|v[ée]lo\b|valise|sac\s+[àa]\s+dos|chaussures?|v[êe]tements?|pyjama|"
    r"maillot|jouets?|poup[ée]e|puzzle|outillage|perceuse|tondeuse|peinture\b|"
    r"d[ée]tergent|lessive|javel|nettoyant|savon|shampoing|d[ée]odorant|dentifrice|"
    r"couches?\s+b[ée]b[ée]|mouchoirs?|papier\s+toilette|essuie.?tout|"
    r"tablettes?\s+lave.?vaisselle|sel\s+lave.?vaisselle",
    re.IGNORECASE,
)

MOTS_ALIMENTAIRES = re.compile(
    r"lait\b|yaourt|fromage|beurre|cr[èe]me\b|huile\b|farine|riz\b|p[âa]tes?\b|"
    r"spaghetti|sucre\b|caf[ée]\b|th[ée]\b|eau\s+(?:min[ée]rale|de\s+table)|jus\b|"
    r"soda|biscuits?|g[âa]teau|chocolat|confiture|miel\b|thon\b|sardine|poisson|"
    r"viande|poulet|dinde|b[oœ]uf|agneau|charcuterie|mortadelle|saucisson|jambon|"
    r"l[ée]gumes?|fruits?\b|tomates?|pommes?\b|bananes?|oranges?|citrons?|pain\b|"
    r"c[ée]r[ée]ales?|semoule|bl[ée]\b|ma[iï]s\b|conserves?|sauce\b|mayonnaise|"
    r"ketchup|moutarde|vinaigre|[ée]pices?|levure|vermicelle|couscous|dattes?|"
    r"lentilles?|pois\s+chiche|granola|dessert|cornichons?|olives?",
    re.IGNORECASE,
)


def est_produit_alimentaire(nom: str, categorie: str | None = None) -> bool:
    """
    Détermine si un produit doit être conservé (alimentaire) ou rejeté
    (électroménager, piscine, hygiène, mobilier...).

    Priorité : catégorie de section connue > mots-clés dans le nom.
    En cas d'ambiguïté totale, le produit est exclu par prudence (l'objectif
    du projet étant strictement la veille tarifaire alimentaire).
    """
    if categorie and categorie != "Non Catégorisé":
        return categorie in {
            "Épicerie", "Produits Laitiers", "Boissons",
            "Fruits Et Légumes", "Boulangerie", "Surgelés",
        }

    if MOTS_NON_ALIMENTAIRES.search(nom):
        return False
    if MOTS_ALIMENTAIRES.search(nom):
        return True
    return False


def _classifier_section(titre: str) -> tuple:
    """
    Retourne (categorie, exclure) à partir d'un titre de section <h2>.
    - categorie : libellé normalisé si section alimentaire reconnue, sinon None
    - exclure : True si la section est explicitement non alimentaire
    """
    t = titre.lower()
    for pattern, label in SECTIONS_ALIMENTAIRES:
        if re.search(pattern, t):
            return label, False
    for pattern in SECTIONS_NON_ALIMENTAIRES:
        if re.search(pattern, t):
            return None, True
    return None, False  # titre neutre/inconnu : catégorie devinée au niveau produit


def _deviner_categorie(nom: str) -> str:
    """Devine une catégorie alimentaire à partir du nom du produit (fallback)."""
    t = nom.lower()
    for pattern, label in SECTIONS_ALIMENTAIRES:
        if re.search(pattern, t):
            return label
    return "Épicerie"


class CatalogueWebScraper(BaseScraper):
    """
    Scraper générique pour une enseigne dont les promotions sont republiées
    sous forme d'articles texte sur hmizate.ma.

    Usage :
        scraper = CatalogueWebScraper(
            nom_enseigne="BIM",
            categorie_url="https://hmizate.ma/deal/catalogue-bim-c20",
            max_articles=12,   # plus d'articles = plus de produits collectés
        )
        resultat = scraper.run()
    """

    def __init__(self, nom_enseigne: str, categorie_url: str, max_articles: int = 12,
                 only_food: bool = True, **kwargs):
        self.nom_enseigne = nom_enseigne
        self.categorie_url = categorie_url
        self.max_articles = max_articles
        self.only_food = only_food
        super().__init__(**kwargs)
        # category_urls est utilisé par BaseScraper.run() pour la boucle principale
        self.category_urls = [categorie_url]

    # ------------------------------------------------------------------
    def parse_product_list(self, html: str) -> list:
        """
        Sur une page de catégorie (ex: /deal/catalogue-bim-c20), on ne
        trouve que des liens vers les articles individuels. On les
        récupère ici, puis on scrape chaque article séparément afin de
        maximiser le nombre de produits alimentaires collectés.
        """
        soup = BeautifulSoup(html, "html.parser")
        liens_articles = self._extraire_liens_articles(soup)

        produits = []
        for url_article in liens_articles[: self.max_articles]:
            html_article = self._fetch(url_article)
            if html_article:
                produits.extend(self.parse_article(html_article, url_article))

        return produits

    def _extraire_liens_articles(self, soup: BeautifulSoup) -> list:
        """Repère les liens d'articles de catalogue sur la page de catégorie."""
        liens = []
        for a in soup.select("a[href*='/deal/']"):
            href = a.get("href", "")
            # Les articles individuels ont un suffixe -nXXXX (ex: ...-n1043)
            if re.search(r"-n\d+$", href.strip("/")) or re.search(r"-n\d+/", href):
                if href not in liens:
                    liens.append(href)
        return liens

    # ------------------------------------------------------------------
    def parse_article(self, html: str, url_article: str) -> list:
        """
        Extrait les produits alimentaires (nom, prix, promo, catégorie)
        d'un article de catalogue, en suivant les titres de section pour
        déterminer le rayon et exclure les rayons non alimentaires.
        """
        soup = BeautifulSoup(html, "html.parser")
        produits = []
        vus = set()
        categorie_courante = None
        exclure_section = False

        for element in soup.find_all(["h2", "h3", "p", "li"]):
            if element.name in ("h2", "h3"):
                categorie_courante, exclure_section = _classifier_section(element.get_text(strip=True))
                continue

            if exclure_section:
                continue  # on ignore tout le contenu d'une section non alimentaire

            if element.name == "p":
                produits.extend(
                    self._extraire_depuis_paragraphe(element, url_article, vus, categorie_courante)
                )
            elif element.name == "li":
                produits.extend(
                    self._extraire_depuis_puce(element, url_article, vus, categorie_courante)
                )

        return produits

    def _extraire_depuis_puce(self, li, url_article: str, vus: set, categorie_courante) -> list:
        texte = li.get_text(" ", strip=True)
        match = LISTE_PUCE_REGEX.match(texte)
        if not match:
            return []

        nom = match.group(1).strip()
        prix = self._to_float(match.group(2))
        if not (nom and prix) or nom.lower() in vus:
            return []

        categorie = categorie_courante or _deviner_categorie(nom)
        if self.only_food and not est_produit_alimentaire(nom, categorie_courante):
            return []

        vus.add(nom.lower())
        return [self._construire_produit(nom, prix, None, url_article, categorie)]

    def _extraire_depuis_paragraphe(self, p, url_article: str, vus: set, categorie_courante) -> list:
        """
        Un paragraphe contient typiquement plusieurs segments en gras qui
        alternent nom de produit / prix, ex :
            "Le <b>café moulu 200g</b> est proposé à <b>28.50 DH</b>,
             le <b>thé vert 500g</b> à <b>27.90 DH</b>"
        On classe chaque segment <strong>/<b> comme "prix" s'il matche le
        regex prix, sinon comme "nom candidat". Pour la détection de promo
        ("au lieu de X DH"), on ne regarde que le texte qui suit
        IMMÉDIATEMENT le segment prix, afin d'éviter d'associer par erreur
        la promo d'un produit à un autre produit du même paragraphe.
        """
        produits = []
        segments = p.find_all(["strong", "b"])
        nom_candidat = None

        for segment in segments:
            texte = segment.get_text(strip=True)
            match_prix = PRIX_REGEX.search(texte)

            if match_prix and len(texte) < 20:
                if nom_candidat:
                    prix = self._to_float(match_prix.group(1))
                    if prix:
                        categorie = categorie_courante or _deviner_categorie(nom_candidat)
                        if not self.only_food or est_produit_alimentaire(nom_candidat, categorie_courante):
                            texte_suivant = self._texte_immediatement_apres(segment)
                            promo_info = self._detecter_promo(texte_suivant, prix)

                            cle = nom_candidat.lower()
                            if cle not in vus:
                                vus.add(cle)
                                produits.append(self._construire_produit(
                                    nom_candidat, promo_info["prix_normal"], promo_info["prix_promotion"],
                                    url_article, categorie
                                ))
                    nom_candidat = None
            else:
                if 3 < len(texte) < 90 and not texte.replace(" ", "").isdigit():
                    nom_candidat = texte

        return produits

    @staticmethod
    def _texte_immediatement_apres(segment, limite_caracteres: int = 40) -> str:
        """Texte brut qui suit directement un segment <strong>, pour scoper
        la recherche de 'au lieu de X DH' au bon produit uniquement."""
        morceau = segment.next_sibling
        if morceau is None:
            return ""
        texte = str(morceau) if not hasattr(morceau, "get_text") else morceau.get_text()
        return texte[:limite_caracteres]

    @staticmethod
    def _detecter_promo(texte_apres_prix: str, prix_affiche: float) -> dict:
        """Si le texte qui suit immédiatement le prix contient 'au lieu de
        X DH', le prix affiché est la promo et X devient le prix normal ;
        sinon le prix affiché est simplement le prix normal."""
        match_au_lieu = AU_LIEU_DE_REGEX.search(texte_apres_prix)

        if match_au_lieu and prix_affiche:
            prix_normal = CatalogueWebScraper._to_float_static(match_au_lieu.group(1))
            return {"prix_normal": prix_normal, "prix_promotion": prix_affiche}
        return {"prix_normal": prix_affiche, "prix_promotion": None}

    @staticmethod
    def _to_float(texte: str):
        return CatalogueWebScraper._to_float_static(texte)

    @staticmethod
    def _to_float_static(texte: str):
        if not texte:
            return None
        try:
            return round(float(texte.replace(",", ".")), 2)
        except (ValueError, AttributeError):
            return None

    def _construire_produit(self, nom: str, prix_normal, prix_promotion, url_article: str, categorie: str) -> dict:
        return {
            "nom": nom,
            "reference": f"{self.nom_enseigne[:3].upper()}-{abs(hash(nom)) % 100000}",
            "marque": None,
            "categorie": categorie,
            "prix_normal": prix_normal,
            "prix_promotion": prix_promotion,
            "image": None,
            "url_fiche": url_article,
            "date_debut": None,
            "date_fin": None,
        }


# ---------------------------------------------------------------------------
# Configuration des enseignes disponibles via hmizate.ma
# ---------------------------------------------------------------------------
ENSEIGNES_CATALOGUE_WEB = {
    "bim": {"nom": "BIM", "url": "https://hmizate.ma/deal/catalogue-bim-c20"},
    "marjane": {"nom": "Marjane", "url": "https://hmizate.ma/deal/catalogue-marjane-c25"},
    "kazyon": {"nom": "Kazyon", "url": "https://hmizate.ma/deal/catalogue-kazyon-c26"},
    "carrefour": {"nom": "Carrefour Market", "url": "https://hmizate.ma/deal/catalogue-carrefour-c21"},
    "aswak_assalam": {"nom": "Aswak Assalam", "url": "https://hmizate.ma/deal/catalogue-aswak-assalam-c23"},
}


def creer_scraper(cle_enseigne: str, max_articles: int = 12) -> CatalogueWebScraper:
    """Fabrique un scraper prêt à l'emploi pour l'une des enseignes configurées.

    max_articles : nombre d'articles de catalogue à parcourir. Plus ce nombre
    est élevé, plus la collecte remonte loin dans l'historique des articles
    et plus le volume de produits alimentaires collectés est important.
    """
    if cle_enseigne not in ENSEIGNES_CATALOGUE_WEB:
        raise ValueError(f"Enseigne inconnue : {cle_enseigne}. Disponibles : {list(ENSEIGNES_CATALOGUE_WEB)}")
    config = ENSEIGNES_CATALOGUE_WEB[cle_enseigne]
    return CatalogueWebScraper(nom_enseigne=config["nom"], categorie_url=config["url"], max_articles=max_articles)
