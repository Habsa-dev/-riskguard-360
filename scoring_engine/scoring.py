"""
RiskGuard 360 - Moteur de Scoring Risque Client
================================================
Module Python indépendant de Django.
Utilisable en CLI ou importable comme bibliothèque.

Algorithme de scoring basé sur des variables pondérées :
  - Ratio d'endettement (dette mensuelle / revenu mensuel)
  - Historique de paiement (incidents sur les 12 derniers mois)
  - Stabilité professionnelle (ancienneté en années)
  - Analyse de cohérence (montant demandé vs profil)

Fonctionnalités avancées :
  - Explainable AI : justification textuelle automatique du score
  - Score de fraude séparé du score de risque
  - Détection de doublons et anomalies comportementales
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import math


# ──────────────────────────────────────────────
# Constantes & Pondérations
# ──────────────────────────────────────────────

class RiskLevel(Enum):
    """Niveaux de risque calculés."""
    TRES_FAIBLE = "Très faible"
    FAIBLE = "Faible"
    MODERE = "Modéré"
    ELEVE = "Élevé"
    TRES_ELEVE = "Très élevé"
    CRITIQUE = "Critique"


# Pondérations des critères (total = 100%)
POIDS = {
    "ratio_endettement": 0.35,    # 35%
    "historique_paiement": 0.30,  # 30%
    "stabilite_pro": 0.20,        # 20%
    "coherence_montant": 0.15,    # 15%
}

# Seuils de risque (score sur 100)
SEUILS_RISQUE = {
    RiskLevel.TRES_FAIBLE: (80, 100),
    RiskLevel.FAIBLE: (65, 80),
    RiskLevel.MODERE: (50, 65),
    RiskLevel.ELEVE: (35, 50),
    RiskLevel.TRES_ELEVE: (20, 35),
    RiskLevel.CRITIQUE: (0, 20),
}

# Seuils de montant max selon le profil professionnel (FCFA)
SEUILS_MONTANT_PROFIL = {
    "etudiant": 500_000,
    "salarie_junior": 5_000_000,
    "salarie_confirme": 20_000_000,
    "salarie_senior": 50_000_000,
    "entrepreneur": 30_000_000,
    "retraite": 10_000_000,
    "entreprise": 200_000_000,
}


# ──────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────

@dataclass
class ProfilClient:
    """Données du profil client nécessaires au scoring."""
    nom: str
    prenom: str
    type_client: str
    profession: str
    revenu_mensuel: float
    charges_mensuelles: float
    dettes_existantes: float
    anciennete_emploi: float
    incidents_paiement_12m: int
    montant_demande: float
    duree_pret_mois: int
    age: int = 30
    apport_personnel: float = 0.0
    numero_cni: str = ""


@dataclass
class ResultatScoring:
    """Résultat complet du scoring."""
    score_global: float
    niveau_risque: RiskLevel
    score_endettement: float
    score_historique: float
    score_stabilite: float
    score_coherence: float
    score_fraude: float
    ratio_endettement: float
    alertes: list = field(default_factory=list)
    recommandation: str = ""
    explication: str = ""
    alerte_fraude: bool = False
    details: dict = field(default_factory=dict)
    facteurs_importants: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convertit le résultat en dictionnaire."""
        return {
            "score_global": round(self.score_global, 2),
            "niveau_risque": self.niveau_risque.value,
            "score_endettement": round(self.score_endettement, 2),
            "score_historique": round(self.score_historique, 2),
            "score_stabilite": round(self.score_stabilite, 2),
            "score_coherence": round(self.score_coherence, 2),
            "score_fraude": round(self.score_fraude, 2),
            "ratio_endettement": round(self.ratio_endettement, 4),
            "alertes": self.alertes,
            "recommandation": self.recommandation,
            "explication": self.explication,
            "alerte_fraude": self.alerte_fraude,
            "details": self.details,
            "facteurs_importants": self.facteurs_importants,
        }

    def to_json(self) -> str:
        """Sérialise en JSON."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# Fonctions de scoring unitaires
# ──────────────────────────────────────────────

def calculer_score_endettement(revenu: float, charges: float,
                                dettes: float, montant_demande: float,
                                duree_mois: int) -> tuple[float, float]:
    """
    Calcule le score lié au ratio d'endettement.
    Ratio = (charges + dettes + mensualité_pret) / revenu
    """
    if revenu <= 0:
        return 0.0, 1.0

    taux_mensuel = 0.15 / 12
    if taux_mensuel > 0 and duree_mois > 0:
        mensualite = montant_demande * (taux_mensuel * (1 + taux_mensuel) ** duree_mois) / \
                     ((1 + taux_mensuel) ** duree_mois - 1)
    else:
        mensualite = montant_demande / max(duree_mois, 1)

    ratio = (charges + dettes + mensualite) / revenu

    if ratio <= 0.20:
        score = 100
    elif ratio <= 0.33:
        score = 100 - ((ratio - 0.20) / 0.13) * 30
    elif ratio <= 0.45:
        score = 70 - ((ratio - 0.33) / 0.12) * 30
    elif ratio <= 0.60:
        score = 40 - ((ratio - 0.45) / 0.15) * 25
    else:
        score = max(0, 15 - ((ratio - 0.60) / 0.40) * 15)

    return round(score, 2), round(ratio, 4)


def calculer_score_historique(incidents: int) -> float:
    """Score basé sur le nombre d'incidents de paiement (12 derniers mois)."""
    if incidents == 0:
        return 100.0
    elif incidents == 1:
        return 75.0
    elif incidents == 2:
        return 50.0
    elif incidents == 3:
        return 25.0
    else:
        return max(0.0, 10.0 - (incidents - 4) * 2.5)


def calculer_score_stabilite(anciennete: float, age: int) -> float:
    """Score basé sur la stabilité professionnelle."""
    if anciennete >= 10:
        score = 100
    elif anciennete >= 5:
        score = 85 + ((anciennete - 5) / 5) * 15
    elif anciennete >= 2:
        score = 65 + ((anciennete - 2) / 3) * 20
    elif anciennete >= 1:
        score = 45 + (anciennete - 1) * 20
    else:
        score = 20 + anciennete * 25

    if 30 <= age <= 55:
        score = min(100, score + 5)
    elif age < 23 or age > 65:
        score = max(0, score - 10)

    return round(min(100, max(0, score)), 2)


def calculer_score_coherence(profil: ProfilClient) -> tuple[float, list]:
    """Analyse de cohérence entre le montant demandé et le profil client."""
    alertes = []
    score = 100.0

    seuil = SEUILS_MONTANT_PROFIL.get(profil.profession, 10_000_000)
    if profil.type_client == 'entreprise':
        seuil = SEUILS_MONTANT_PROFIL['entreprise']

    ratio_seuil = profil.montant_demande / seuil if seuil > 0 else 999
    if ratio_seuil > 2.0:
        score -= 60
        alertes.append(
            f"ALERTE: Montant demandé ({profil.montant_demande:,.0f} FCFA) "
            f"très supérieur au seuil du profil '{profil.profession}' "
            f"({seuil:,.0f} FCFA) — ratio {ratio_seuil:.1f}x"
        )
    elif ratio_seuil > 1.0:
        score -= 30
        alertes.append(
            f"ATTENTION: Montant demandé ({profil.montant_demande:,.0f} FCFA) "
            f"supérieur au seuil recommandé ({seuil:,.0f} FCFA)"
        )

    ratio_revenu = profil.montant_demande / max(profil.revenu_mensuel, 1)
    if ratio_revenu > 60:
        score -= 30
        alertes.append(
            f"ALERTE: Montant demandé = {ratio_revenu:.0f}x le revenu mensuel (seuil critique: 60x)"
        )
    elif ratio_revenu > 48:
        score -= 15
        alertes.append(
            f"ATTENTION: Montant demandé = {ratio_revenu:.0f}x le revenu mensuel (seuil d'alerte: 48x)"
        )

    if profil.duree_pret_mois > 84:
        score -= 10
        alertes.append(f"Durée de prêt très longue : {profil.duree_pret_mois} mois (> 7 ans)")

    age_fin_pret = profil.age + (profil.duree_pret_mois / 12)
    if age_fin_pret > 70:
        score -= 15
        alertes.append(f"Le client aura {age_fin_pret:.0f} ans en fin de prêt (> 70 ans)")

    return round(max(0, score), 2), alertes


# ──────────────────────────────────────────────
# Score de fraude avancé (séparé du risque)
# ──────────────────────────────────────────────

def calculer_score_fraude(profil: ProfilClient, score_coherence: float) -> tuple[float, list]:
    """
    Calcule un score de fraude séparé (0 = pas de fraude, 100 = fraude certaine).

    Critères :
    - Incohérence montant/profil
    - Revenus suspects (trop élevés vs profession)
    - Absence de charges (suspect si revenu élevé)
    - Montant démesuré vs revenus
    """
    score = 0.0
    alertes_fraude = []

    # 1. Incohérence montant / profil
    if score_coherence <= 20:
        score += 40
        alertes_fraude.append("Incohérence majeure entre montant et profil client")
    elif score_coherence <= 50:
        score += 20

    # 2. Montant démesuré vs revenus
    if profil.revenu_mensuel > 0:
        ratio = profil.montant_demande / profil.revenu_mensuel
        if ratio > 100:
            score += 30
            alertes_fraude.append(f"Montant demandé = {ratio:.0f}x le revenu mensuel")
        elif ratio > 60:
            score += 15

    # 3. Revenus suspects vs profession
    seuils_revenus = {
        'etudiant': 200_000,
        'salarie_junior': 500_000,
        'salarie_confirme': 2_000_000,
        'retraite': 1_000_000,
    }
    seuil_rev = seuils_revenus.get(profil.profession)
    if seuil_rev and profil.revenu_mensuel > seuil_rev * 3:
        score += 15
        alertes_fraude.append(
            f"Revenu déclaré ({profil.revenu_mensuel:,.0f} FCFA) "
            f"anormalement élevé pour le profil '{profil.profession}'"
        )

    # 4. Absence suspecte de charges
    if profil.revenu_mensuel > 300_000 and profil.charges_mensuelles == 0:
        score += 10
        alertes_fraude.append("Aucune charge déclarée malgré un revenu significatif")

    # 5. Profil à haut risque + montant élevé
    if profil.incidents_paiement_12m >= 3 and profil.montant_demande > 10_000_000:
        score += 15
        alertes_fraude.append(
            f"Client avec {profil.incidents_paiement_12m} incidents "
            f"demandant {profil.montant_demande:,.0f} FCFA"
        )

    return round(min(100, score), 2), alertes_fraude


# ──────────────────────────────────────────────
# Explainable AI - Justification du score
# ──────────────────────────────────────────────

def generer_explication(profil: ProfilClient, score_end: float, score_hist: float,
                        score_stab: float, score_coh: float, ratio: float,
                        score_global: float, score_fraude: float) -> tuple[str, list]:
    """
    Génère une explication textuelle automatique du score.
    Identifie les facteurs les plus importants (positifs et négatifs).

    Returns:
        (explication textuelle, liste de facteurs importants)
    """
    facteurs = []
    explications = []

    # Analyse de chaque composante
    # Endettement (poids 35%)
    impact_end = (score_end - 50) * POIDS["ratio_endettement"]
    if score_end < 40:
        facteurs.append({
            "facteur": "Ratio d'endettement",
            "impact": "très négatif",
            "score": score_end,
            "detail": f"Ratio d'endettement de {ratio*100:.1f}% (critique > 45%)"
        })
        explications.append(
            f"Le ratio d'endettement est très élevé ({ratio*100:.1f}%), "
            f"ce qui indique une capacité de remboursement insuffisante"
        )
    elif score_end < 60:
        facteurs.append({
            "facteur": "Ratio d'endettement",
            "impact": "négatif",
            "score": score_end,
            "detail": f"Ratio d'endettement de {ratio*100:.1f}% (élevé > 33%)"
        })
        explications.append(
            f"Le ratio d'endettement ({ratio*100:.1f}%) dépasse le seuil recommandé de 33%"
        )
    elif score_end >= 80:
        facteurs.append({
            "facteur": "Ratio d'endettement",
            "impact": "très positif",
            "score": score_end,
            "detail": f"Ratio d'endettement maîtrisé à {ratio*100:.1f}%"
        })

    # Historique (poids 30%)
    if score_hist < 50:
        facteurs.append({
            "facteur": "Historique de paiement",
            "impact": "très négatif",
            "score": score_hist,
            "detail": f"{profil.incidents_paiement_12m} incidents sur 12 mois"
        })
        explications.append(
            f"L'historique de paiement est préoccupant avec "
            f"{profil.incidents_paiement_12m} incidents sur les 12 derniers mois"
        )
    elif score_hist < 75:
        facteurs.append({
            "facteur": "Historique de paiement",
            "impact": "négatif",
            "score": score_hist,
            "detail": f"{profil.incidents_paiement_12m} incident(s) sur 12 mois"
        })
    elif score_hist == 100:
        facteurs.append({
            "facteur": "Historique de paiement",
            "impact": "très positif",
            "score": score_hist,
            "detail": "Aucun incident de paiement"
        })

    # Stabilité (poids 20%)
    if score_stab < 45:
        facteurs.append({
            "facteur": "Stabilité professionnelle",
            "impact": "négatif",
            "score": score_stab,
            "detail": f"Ancienneté de {profil.anciennete_emploi} an(s)"
        })
        explications.append(
            f"La stabilité professionnelle est faible "
            f"(ancienneté de {profil.anciennete_emploi} an(s) seulement)"
        )
    elif score_stab >= 85:
        facteurs.append({
            "facteur": "Stabilité professionnelle",
            "impact": "positif",
            "score": score_stab,
            "detail": f"Ancienneté solide de {profil.anciennete_emploi} ans"
        })

    # Cohérence (poids 15%)
    if score_coh < 50:
        facteurs.append({
            "facteur": "Cohérence montant/profil",
            "impact": "très négatif",
            "score": score_coh,
            "detail": "Montant demandé incohérent avec le profil"
        })
        explications.append(
            f"Le montant demandé ({profil.montant_demande:,.0f} FCFA) est incohérent "
            f"avec le profil '{profil.profession}'"
        )

    # Score de fraude
    if score_fraude >= 50:
        explications.append(
            f"⚠️ Le score de fraude est élevé ({score_fraude}/100), "
            f"des vérifications approfondies sont nécessaires"
        )

    # Trier facteurs par impact
    ordre_impact = {"très négatif": 0, "négatif": 1, "positif": 2, "très positif": 3}
    facteurs.sort(key=lambda x: ordre_impact.get(x["impact"], 2))

    # Construire l'explication finale
    if score_global >= 65:
        intro = f"Le score de {score_global:.1f}/100 est favorable."
    elif score_global >= 50:
        intro = f"Le score de {score_global:.1f}/100 est modéré et nécessite une analyse approfondie."
    elif score_global >= 35:
        intro = f"Le score de {score_global:.1f}/100 est faible, principalement en raison de :"
    else:
        intro = f"Le score de {score_global:.1f}/100 est critique. Les facteurs de risque majeurs sont :"

    explication_finale = intro
    if explications:
        explication_finale += "\n• " + "\n• ".join(explications)

    return explication_finale, facteurs


# ──────────────────────────────────────────────
# Moteur de Scoring principal
# ──────────────────────────────────────────────

def calculer_score_risque(profil: ProfilClient) -> ResultatScoring:
    """
    Fonction principale du moteur de scoring.
    Calcule le score de risque global + score de fraude + explication IA.
    """
    # 1. Calcul des scores unitaires
    score_endettement, ratio = calculer_score_endettement(
        profil.revenu_mensuel,
        profil.charges_mensuelles,
        profil.dettes_existantes,
        profil.montant_demande,
        profil.duree_pret_mois
    )

    score_historique = calculer_score_historique(profil.incidents_paiement_12m)
    score_stabilite = calculer_score_stabilite(profil.anciennete_emploi, profil.age)
    score_coherence, alertes_coherence = calculer_score_coherence(profil)

    # 2. Score global pondéré
    score_global = (
        score_endettement * POIDS["ratio_endettement"] +
        score_historique * POIDS["historique_paiement"] +
        score_stabilite * POIDS["stabilite_pro"] +
        score_coherence * POIDS["coherence_montant"]
    )

    # 3. Score de fraude séparé
    score_fraude, alertes_fraude = calculer_score_fraude(profil, score_coherence)

    # 4. Détermination du niveau de risque
    niveau_risque = RiskLevel.CRITIQUE
    for niveau, (seuil_bas, seuil_haut) in SEUILS_RISQUE.items():
        if seuil_bas <= score_global <= seuil_haut:
            niveau_risque = niveau
            break

    # 5. Alertes globales
    alertes = list(alertes_coherence)

    if ratio > 0.50:
        alertes.append(f"Ratio d'endettement critique: {ratio*100:.1f}% (seuil: 50%)")
    if profil.incidents_paiement_12m >= 3:
        alertes.append(
            f"Historique de paiement préoccupant: {profil.incidents_paiement_12m} incidents sur 12 mois"
        )

    # Ajouter alertes fraude
    for af in alertes_fraude:
        alertes.append(f"🔍 FRAUDE: {af}")

    # 6. Détection de fraude
    alerte_fraude = score_fraude >= 50
    if score_coherence <= 20:
        alerte_fraude = True
    if profil.revenu_mensuel > 0 and profil.montant_demande > 100 * profil.revenu_mensuel:
        alerte_fraude = True

    # 7. Explainable AI
    explication, facteurs = generer_explication(
        profil, score_endettement, score_historique, score_stabilite,
        score_coherence, ratio, score_global, score_fraude
    )

    # 8. Recommandation
    if alerte_fraude:
        recommandation = "REFUS IMMEDIAT - Dossier à transmettre au service fraude"
    elif score_global >= 65:
        recommandation = "ACCORD DE PRINCIPE - Dossier éligible sous réserve de vérifications"
    elif score_global >= 50:
        recommandation = "ÉTUDE APPROFONDIE - Demander des garanties supplémentaires"
    elif score_global >= 35:
        recommandation = "RISQUE ÉLEVÉ - Accord possible avec conditions strictes (garant, nantissement)"
    else:
        recommandation = "REFUS RECOMMANDÉ - Risque trop élevé pour le profil"

    # 9. Détails additionnels
    mensualite = 0
    if profil.duree_pret_mois > 0:
        taux_m = 0.15 / 12
        mensualite = profil.montant_demande * (taux_m * (1 + taux_m) ** profil.duree_pret_mois) / \
                     ((1 + taux_m) ** profil.duree_pret_mois - 1)

    details = {
        "poids_appliques": POIDS,
        "mensualite_estimee": round(mensualite, 0),
        "capacite_remboursement": round(
            profil.revenu_mensuel - profil.charges_mensuelles - profil.dettes_existantes, 0
        ),
        "taux_annuel": "15%",
    }

    return ResultatScoring(
        score_global=round(score_global, 2),
        niveau_risque=niveau_risque,
        score_endettement=score_endettement,
        score_historique=score_historique,
        score_stabilite=score_stabilite,
        score_coherence=score_coherence,
        score_fraude=score_fraude,
        ratio_endettement=ratio,
        alertes=alertes,
        recommandation=recommandation,
        explication=explication,
        alerte_fraude=alerte_fraude,
        details=details,
        facteurs_importants=facteurs,
    )


# ──────────────────────────────────────────────
# Simulation de prêt
# ──────────────────────────────────────────────

def simuler_pret(montant: float, duree_mois: int, taux_annuel: float = 0.15,
                 revenu_mensuel: float = 0, charges: float = 0) -> dict:
    """
    Simule un prêt et retourne les informations clés.

    Args:
        montant: Montant du prêt
        duree_mois: Durée en mois
        taux_annuel: Taux d'intérêt annuel (défaut 15%)
        revenu_mensuel: Revenu mensuel du client (optionnel)
        charges: Charges mensuelles (optionnel)

    Returns:
        dict avec mensualité, coût total, etc.
    """
    taux_mensuel = taux_annuel / 12

    if taux_mensuel > 0 and duree_mois > 0:
        mensualite = montant * (taux_mensuel * (1 + taux_mensuel) ** duree_mois) / \
                     ((1 + taux_mensuel) ** duree_mois - 1)
    else:
        mensualite = montant / max(duree_mois, 1)

    cout_total = mensualite * duree_mois
    cout_credit = cout_total - montant

    # Capacité de remboursement
    capacite = revenu_mensuel - charges if revenu_mensuel > 0 else 0
    ratio_endettement = mensualite / revenu_mensuel if revenu_mensuel > 0 else 0

    # Tableau d'amortissement simplifié (premiers et derniers mois)
    amortissement = []
    capital_restant = montant
    for mois in range(1, duree_mois + 1):
        interets = capital_restant * taux_mensuel
        capital_rembourse = mensualite - interets
        capital_restant -= capital_rembourse
        if mois <= 3 or mois >= duree_mois - 1:
            amortissement.append({
                "mois": mois,
                "mensualite": round(mensualite, 0),
                "capital": round(capital_rembourse, 0),
                "interets": round(interets, 0),
                "capital_restant": round(max(0, capital_restant), 0),
            })

    return {
        "montant": montant,
        "duree_mois": duree_mois,
        "taux_annuel": taux_annuel * 100,
        "taux_mensuel": round(taux_mensuel * 100, 3),
        "mensualite": round(mensualite, 0),
        "cout_total": round(cout_total, 0),
        "cout_credit": round(cout_credit, 0),
        "capacite_remboursement": round(capacite, 0),
        "ratio_endettement": round(ratio_endettement * 100, 1),
        "eligible": ratio_endettement < 0.33 if revenu_mensuel > 0 else None,
        "amortissement": amortissement,
    }


# ──────────────────────────────────────────────
# Interface CLI
# ──────────────────────────────────────────────

def cli_scoring():
    """Interface en ligne de commande pour le moteur de scoring."""
    import argparse

    parser = argparse.ArgumentParser(
        description="RiskGuard 360 - Moteur de Scoring Risque Client"
    )
    parser.add_argument("--nom", required=True, help="Nom du client")
    parser.add_argument("--prenom", required=True, help="Prénom du client")
    parser.add_argument("--type", dest="type_client", default="particulier",
                        choices=["particulier", "entreprise"])
    parser.add_argument("--profession", required=True,
                        choices=list(SEUILS_MONTANT_PROFIL.keys()))
    parser.add_argument("--revenu", type=float, required=True, help="Revenu mensuel (FCFA)")
    parser.add_argument("--charges", type=float, required=True, help="Charges mensuelles (FCFA)")
    parser.add_argument("--dettes", type=float, default=0, help="Dettes existantes (FCFA)")
    parser.add_argument("--anciennete", type=float, required=True, help="Ancienneté emploi (années)")
    parser.add_argument("--incidents", type=int, default=0, help="Incidents paiement (12 mois)")
    parser.add_argument("--montant", type=float, required=True, help="Montant prêt (FCFA)")
    parser.add_argument("--duree", type=int, required=True, help="Durée prêt (mois)")
    parser.add_argument("--age", type=int, default=30, help="Âge du client")
    parser.add_argument("--apport", type=float, default=0, help="Apport personnel (FCFA)")
    parser.add_argument("--json", action="store_true", help="Sortie JSON")

    args = parser.parse_args()

    profil = ProfilClient(
        nom=args.nom, prenom=args.prenom,
        type_client=args.type_client, profession=args.profession,
        revenu_mensuel=args.revenu, charges_mensuelles=args.charges,
        dettes_existantes=args.dettes, anciennete_emploi=args.anciennete,
        incidents_paiement_12m=args.incidents, montant_demande=args.montant,
        duree_pret_mois=args.duree, age=args.age, apport_personnel=args.apport,
    )

    resultat = calculer_score_risque(profil)

    if args.json:
        print(resultat.to_json())
    else:
        print("\n" + "=" * 60)
        print("   RISKGUARD 360 - RAPPORT DE SCORING")
        print("=" * 60)
        print(f"\n  Client : {profil.prenom} {profil.nom}")
        print(f"  Profil : {profil.type_client} / {profil.profession}")
        print(f"  Montant demandé : {profil.montant_demande:,.0f} FCFA")
        print(f"\n{'─' * 60}")
        print(f"  SCORE RISQUE : {resultat.score_global}/100 ({resultat.niveau_risque.value})")
        print(f"  SCORE FRAUDE : {resultat.score_fraude}/100")
        print(f"{'─' * 60}")
        print(f"\n  Détail :")
        print(f"    • Endettement : {resultat.score_endettement}/100 (ratio: {resultat.ratio_endettement*100:.1f}%)")
        print(f"    • Historique   : {resultat.score_historique}/100")
        print(f"    • Stabilité    : {resultat.score_stabilite}/100")
        print(f"    • Cohérence    : {resultat.score_coherence}/100")
        print(f"\n{'─' * 60}")
        print(f"  EXPLICATION IA :")
        print(f"  {resultat.explication}")
        print(f"\n  RECOMMANDATION : {resultat.recommandation}")
        if resultat.alerte_fraude:
            print(f"\n  🚨 ALERTE FRAUDE DÉTECTÉE 🚨")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    cli_scoring()
