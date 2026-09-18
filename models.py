"""
models.py
=========
Modèles SQLAlchemy correspondant au Modèle Conceptuel de Données (MCD)
du projet :

    Enseigne (1) ----- (0..*) Produit
    Produit  (1) ----- (0..*) HistoriquePrix
    Scraping (1) ----- (0..*) HistoriquePrix

Une table Utilisateur est ajoutée pour préparer une future gestion des
droits d'accès.
"""

from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Date,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Enseigne(Base):
    """Table Enseigne (8.4.1) : magasin / site concurrent analysé."""
    __tablename__ = "enseigne"

    id_enseigne = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(100), nullable=False, unique=True)
    url = Column(String(255))
    logo = Column(String(255))
    actif = Column(Integer, default=1)  # 1 = actif, 0 = désactivé (2.4.1)

    produits = relationship("Produit", back_populates="enseigne", cascade="all, delete-orphan")
    scrapings = relationship("Scraping", back_populates="enseigne", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Enseigne {self.nom}>"


class Produit(Base):
    """Table Produit (8.4.2)."""
    __tablename__ = "produit"
    __table_args__ = (
        UniqueConstraint("reference", "id_enseigne", name="uq_reference_enseigne"),
    )

    id_produit = Column(Integer, primary_key=True, autoincrement=True)
    reference = Column(String(100), nullable=False)
    nom = Column(String(255), nullable=False)
    marque = Column(String(120))
    categorie = Column(String(100))
    image = Column(Text)
    url_fiche = Column(Text)
    id_enseigne = Column(Integer, ForeignKey("enseigne.id_enseigne"), nullable=False)

    enseigne = relationship("Enseigne", back_populates="produits")
    historique = relationship(
        "HistoriquePrix", back_populates="produit",
        cascade="all, delete-orphan", order_by="HistoriquePrix.date_collecte"
    )

    def __repr__(self):
        return f"<Produit {self.nom} ({self.reference})>"


class Scraping(Base):
    """Table Scraping (8.4.4) : journal des exécutions de collecte."""
    __tablename__ = "scraping"

    id_scraping = Column(Integer, primary_key=True, autoincrement=True)
    date_execution = Column(DateTime, default=datetime.utcnow)
    site = Column(String(100))
    temps_execution = Column(Float)
    etat = Column(String(30), default="en_cours")  # succes / echec / en_cours
    nb_produits = Column(Integer, default=0)
    message_erreur = Column(Text)
    id_enseigne = Column(Integer, ForeignKey("enseigne.id_enseigne"))

    enseigne = relationship("Enseigne", back_populates="scrapings")
    releves = relationship("HistoriquePrix", back_populates="scraping")

    def __repr__(self):
        return f"<Scraping {self.site} {self.etat}>"


class HistoriquePrix(Base):
    """Table HistoriquePrix (8.4.3) : relevé de prix horodaté."""
    __tablename__ = "historique_prix"

    id_prix = Column(Integer, primary_key=True, autoincrement=True)
    prix_normal = Column(Float)
    prix_promotion = Column(Float)
    date_debut = Column(Date, nullable=True)
    date_fin = Column(Date, nullable=True)
    date_collecte = Column(DateTime, default=datetime.utcnow)
    id_produit = Column(Integer, ForeignKey("produit.id_produit"), nullable=False)
    id_scraping = Column(Integer, ForeignKey("scraping.id_scraping"), nullable=True)

    produit = relationship("Produit", back_populates="historique")
    scraping = relationship("Scraping", back_populates="releves")

    @property
    def prix_effectif(self):
        """Prix réellement payé (promo si disponible, sinon prix normal)."""
        return self.prix_promotion if self.prix_promotion else self.prix_normal

    @property
    def taux_reduction(self):
        if self.prix_promotion and self.prix_normal and self.prix_normal > 0:
            return round(100 * (1 - self.prix_promotion / self.prix_normal), 1)
        return 0

    def __repr__(self):
        return f"<HistoriquePrix produit={self.id_produit} prix={self.prix_effectif}>"


class Utilisateur(Base):
    """Table Utilisateur (9.3) : gestion basique des comptes (évolutivité)."""
    __tablename__ = "utilisateur"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String(120), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    role = Column(String(30), default="analyste")  # administrateur / analyste
    mot_de_passe_hash = Column(String(255))

    def __repr__(self):
        return f"<Utilisateur {self.email}>"
