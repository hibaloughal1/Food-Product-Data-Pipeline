"""
app.py
======
Application Flask exposant le tableau de bord de veille tarifaire, ainsi
qu'une petite API interne utilisée par les graphiques (Chart.js) et les
filtres.

Lancement :
    python app.py
puis ouvrir http://127.0.0.1:5000
"""

import csv
import io
from datetime import datetime

from flask import Flask, render_template, request, jsonify, Response, send_file
from sqlalchemy import func, desc

import config
from database import get_session, init_db
from models import Enseigne, Produit, HistoriquePrix, Scraping

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

init_db()


# ---------------------------------------------------------------------------
# Fonctions utilitaires : sous-requête du dernier prix connu par produit
# ---------------------------------------------------------------------------
def _sous_requete_dernier_prix(session):
    """
    Retourne, pour chaque produit, l'id de son relevé de prix le plus récent.
    Sert de base à la quasi-totalité des indicateurs du dashboard (10.4).
    """
    sub = (
        session.query(
            HistoriquePrix.id_produit,
            func.max(HistoriquePrix.date_collecte).label("derniere_date")
        )
        .group_by(HistoriquePrix.id_produit)
        .subquery()
    )
    return sub


def _requete_derniers_prix(session, enseigne_id=None, categorie=None, recherche=None):
    """Requête jointe Produit + Enseigne + dernier HistoriquePrix, avec filtres (10.7)."""
    sub = _sous_requete_dernier_prix(session)

    q = (
        session.query(Produit, HistoriquePrix, Enseigne)
        .join(HistoriquePrix, HistoriquePrix.id_produit == Produit.id_produit)
        .join(sub, (sub.c.id_produit == HistoriquePrix.id_produit) &
                    (sub.c.derniere_date == HistoriquePrix.date_collecte))
        .join(Enseigne, Enseigne.id_enseigne == Produit.id_enseigne)
    )

    if enseigne_id:
        q = q.filter(Produit.id_enseigne == enseigne_id)
    if categorie:
        q = q.filter(Produit.categorie == categorie)
    if recherche:
        like = f"%{recherche}%"
        q = q.filter(
            (Produit.nom.ilike(like)) |
            (Produit.reference.ilike(like)) |
            (Produit.marque.ilike(like))
        )
    return q


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def dashboard():
    with get_session() as session:
        enseignes = [
            {"id": e.id_enseigne, "nom": e.nom}
            for e in session.query(Enseigne).order_by(Enseigne.nom).all()
        ]
        categories = [
            c[0] for c in session.query(Produit.categorie).distinct().order_by(Produit.categorie).all() if c[0]
        ]
    return render_template("dashboard.html", enseignes=enseignes, categories=categories)


# ---------------------------------------------------------------------------
# API : KPI globaux (10.4)
# ---------------------------------------------------------------------------
@app.route("/api/kpis")
def api_kpis():
    enseigne_id = request.args.get("enseigne_id", type=int)
    categorie = request.args.get("categorie")

    with get_session() as session:
        q = _requete_derniers_prix(session, enseigne_id, categorie)
        lignes = q.all()

        nb_produits = len(lignes)
        prix_effectifs = [
            (hp.prix_promotion or hp.prix_normal) for _, hp, _ in lignes if (hp.prix_promotion or hp.prix_normal)
        ]
        nb_promotions = sum(1 for _, hp, _ in lignes if hp.prix_promotion)

        derniere_maj = session.query(func.max(Scraping.date_execution)).scalar()

        return jsonify({
            "nb_produits": nb_produits,
            "nb_promotions": nb_promotions,
            "prix_min": round(min(prix_effectifs), 2) if prix_effectifs else 0,
            "prix_max": round(max(prix_effectifs), 2) if prix_effectifs else 0,
            "prix_moyen": round(sum(prix_effectifs) / len(prix_effectifs), 2) if prix_effectifs else 0,
            "derniere_maj": derniere_maj.strftime("%d/%m/%Y %H:%M") if derniere_maj else "Aucune collecte",
        })


# ---------------------------------------------------------------------------
# API : produits par enseigne (10.6.1)
# ---------------------------------------------------------------------------
@app.route("/api/produits-par-enseigne")
def api_produits_par_enseigne():
    with get_session() as session:
        resultats = (
            session.query(Enseigne.nom, func.count(Produit.id_produit))
            .join(Produit, Produit.id_enseigne == Enseigne.id_enseigne)
            .group_by(Enseigne.nom)
            .all()
        )
    return jsonify({"labels": [r[0] for r in resultats], "valeurs": [r[1] for r in resultats]})


# ---------------------------------------------------------------------------
# API : répartition par catégorie (10.6.2)
# ---------------------------------------------------------------------------
@app.route("/api/repartition-categories")
def api_repartition_categories():
    with get_session() as session:
        resultats = (
            session.query(Produit.categorie, func.count(Produit.id_produit))
            .group_by(Produit.categorie)
            .order_by(desc(func.count(Produit.id_produit)))
            .all()
        )
    return jsonify({"labels": [r[0] or "Non catégorisé" for r in resultats], "valeurs": [r[1] for r in resultats]})


# ---------------------------------------------------------------------------
# API : évolution des prix d'un produit (10.6.3)
# ---------------------------------------------------------------------------
@app.route("/api/evolution-prix/<int:id_produit>")
def api_evolution_prix(id_produit):
    with get_session() as session:
        historique = (
            session.query(HistoriquePrix)
            .filter_by(id_produit=id_produit)
            .order_by(HistoriquePrix.date_collecte)
            .all()
        )
    return jsonify({
        "labels": [h.date_collecte.strftime("%d/%m/%Y") for h in historique],
        "prix_normal": [h.prix_normal for h in historique],
        "prix_promotion": [h.prix_promotion for h in historique],
    })


# ---------------------------------------------------------------------------
# API : comparaison des prix entre enseignes pour un même produit (2.4.9)
# ---------------------------------------------------------------------------
@app.route("/api/comparaison")
def api_comparaison():
    terme = request.args.get("q", "")
    if not terme:
        return jsonify([])

    with get_session() as session:
        q = _requete_derniers_prix(session, recherche=terme)
        lignes = q.order_by(Produit.nom).all()

        regroupement = {}
        for produit, hp, enseigne in lignes:
            regroupement.setdefault(produit.nom, []).append({
                "enseigne": enseigne.nom,
                "prix": hp.prix_effectif,
                "prix_normal": hp.prix_normal,
                "prix_promotion": hp.prix_promotion,
                "reference": produit.reference,
            })

        resultat = []
        for nom, offres in regroupement.items():
            prix_min = min(o["prix"] for o in offres)
            for o in offres:
                o["meilleure_offre"] = (o["prix"] == prix_min)
            resultat.append({"produit": nom, "offres": offres})

    return jsonify(resultat)


# ---------------------------------------------------------------------------
# API : top 10 des produits les moins chers (10.6.5)
# ---------------------------------------------------------------------------
@app.route("/api/top-moins-chers")
def api_top_moins_chers():
    enseigne_id = request.args.get("enseigne_id", type=int)
    categorie = request.args.get("categorie")

    with get_session() as session:
        q = _requete_derniers_prix(session, enseigne_id, categorie)
        lignes = [
            (p.nom, e.nom, (hp.prix_promotion or hp.prix_normal))
            for p, hp, e in q.all() if (hp.prix_promotion or hp.prix_normal)
        ]
        lignes.sort(key=lambda x: x[2])

    return jsonify([{"produit": n, "enseigne": e, "prix": pr} for n, e, pr in lignes[:10]])


# ---------------------------------------------------------------------------
# API : produits en promotion (10.6.6)
# ---------------------------------------------------------------------------
@app.route("/api/promotions")
def api_promotions():
    with get_session() as session:
        q = _requete_derniers_prix(session)
        lignes = [
            {
                "produit": p.nom,
                "enseigne": e.nom,
                "prix_normal": hp.prix_normal,
                "prix_promotion": hp.prix_promotion,
                "reduction": hp.taux_reduction,
                "date_fin": hp.date_fin.strftime("%d/%m/%Y") if hp.date_fin else None,
            }
            for p, hp, e in q.all() if hp.prix_promotion
        ]
        lignes.sort(key=lambda x: x["reduction"], reverse=True)

    return jsonify(lignes)


# ---------------------------------------------------------------------------
# API : recherche multicritère + tableau produits (2.4.8, 10.5)
# ---------------------------------------------------------------------------
@app.route("/api/produits")
def api_produits():
    enseigne_id = request.args.get("enseigne_id", type=int)
    categorie = request.args.get("categorie")
    recherche = request.args.get("q")

    with get_session() as session:
        q = _requete_derniers_prix(session, enseigne_id, categorie, recherche)
        lignes = q.order_by(Produit.nom).limit(500).all()

        data = [{
            "id": p.id_produit,
            "nom": p.nom,
            "reference": p.reference,
            "marque": p.marque,
            "categorie": p.categorie,
            "enseigne": e.nom,
            "prix_normal": hp.prix_normal,
            "prix_promotion": hp.prix_promotion,
            "prix_effectif": hp.prix_effectif,
            "date_collecte": hp.date_collecte.strftime("%d/%m/%Y %H:%M"),
        } for p, hp, e in lignes]

    return jsonify(data)


# ---------------------------------------------------------------------------
# Export CSV / Excel / PDF (2.4.10)
# ---------------------------------------------------------------------------
@app.route("/export/csv")
def export_csv():
    with get_session() as session:
        q = _requete_derniers_prix(
            session,
            request.args.get("enseigne_id", type=int),
            request.args.get("categorie"),
            request.args.get("q"),
        )
        lignes = [
            [p.nom, p.reference, p.marque, p.categorie, e.nom, hp.prix_normal, hp.prix_promotion, hp.date_collecte]
            for p, hp, e in q.order_by(Produit.nom).all()
        ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Produit", "Référence", "Marque", "Catégorie", "Enseigne", "Prix normal", "Prix promo", "Date collecte"])
    writer.writerows(lignes)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=veille_tarifaire_{datetime.now():%Y%m%d}.csv"},
    )


@app.route("/export/excel")
def export_excel():
    try:
        import pandas as pd
    except ImportError:
        return "Le module pandas/openpyxl est requis pour l'export Excel.", 500

    with get_session() as session:
        q = _requete_derniers_prix(
            session,
            request.args.get("enseigne_id", type=int),
            request.args.get("categorie"),
            request.args.get("q"),
        )
        donnees = [{
            "Produit": p.nom, "Référence": p.reference, "Marque": p.marque,
            "Catégorie": p.categorie, "Enseigne": e.nom,
            "Prix normal": hp.prix_normal, "Prix promo": hp.prix_promotion,
            "Date collecte": hp.date_collecte,
        } for p, hp, e in q.order_by(Produit.nom).all()]

    df = pd.DataFrame(donnees)

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return send_file(
        buffer, as_attachment=True,
        download_name=f"veille_tarifaire_{datetime.now():%Y%m%d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=config.DEBUG, port=5000)
