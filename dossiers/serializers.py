"""
RiskGuard 360 - Sérialiseurs API REST
======================================
"""

from rest_framework import serializers
from .models import Client, DossierPret, ResultatScoring, AuditLog, PieceJustificative


class ClientSerializer(serializers.ModelSerializer):
    age = serializers.ReadOnlyField()

    class Meta:
        model = Client
        fields = [
            'id', 'type_client', 'nom', 'prenom', 'date_naissance',
            'telephone', 'email', 'adresse', 'numero_cni', 'profession',
            'revenu_mensuel', 'charges_mensuelles', 'dettes_existantes',
            'anciennete_emploi', 'incidents_paiement',
            'raison_sociale', 'numero_registre_commerce',
            'secteur_activite', 'chiffre_affaires_annuel',
            'age', 'date_creation',
        ]
        read_only_fields = ['id', 'date_creation', 'age']


class DossierPretSerializer(serializers.ModelSerializer):
    client_nom = serializers.StringRelatedField(source='client', read_only=True)
    conseiller_nom = serializers.StringRelatedField(source='conseiller', read_only=True)
    etat_display = serializers.CharField(source='get_etat_display', read_only=True)
    objet_display = serializers.CharField(source='get_objet_pret_display', read_only=True)
    transitions_possibles = serializers.ReadOnlyField()

    class Meta:
        model = DossierPret
        fields = [
            'id', 'reference', 'client', 'client_nom', 'conseiller', 'conseiller_nom',
            'montant_demande', 'duree_mois', 'objet_pret', 'objet_display',
            'apport_personnel', 'description',
            'etat', 'etat_display', 'transitions_possibles',
            'score_risque', 'score_fraude', 'niveau_risque',
            'recommandation', 'explication_score', 'alerte_fraude',
            'details_scoring',
            'date_soumission', 'date_analyse', 'date_decision',
        ]
        read_only_fields = [
            'id', 'reference', 'etat', 'score_risque', 'score_fraude',
            'niveau_risque', 'recommandation', 'explication_score',
            'alerte_fraude', 'details_scoring',
            'date_soumission', 'date_analyse', 'date_decision',
        ]


class DossierPretListSerializer(serializers.ModelSerializer):
    """Sérialiseur léger pour les listes."""
    client_nom = serializers.StringRelatedField(source='client', read_only=True)
    etat_display = serializers.CharField(source='get_etat_display', read_only=True)

    class Meta:
        model = DossierPret
        fields = [
            'id', 'reference', 'client_nom', 'montant_demande',
            'duree_mois', 'objet_pret', 'etat', 'etat_display',
            'score_risque', 'score_fraude', 'niveau_risque',
            'alerte_fraude', 'date_soumission',
        ]


class ResultatScoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultatScoring
        fields = '__all__'


class ScoreRequestSerializer(serializers.Serializer):
    """Sérialiseur pour le calcul de score via API."""
    dossier_id = serializers.UUIDField()


class SimulationSerializer(serializers.Serializer):
    """Sérialiseur pour la simulation de prêt."""
    montant = serializers.FloatField(min_value=10000)
    duree_mois = serializers.IntegerField(min_value=1, max_value=360)
    taux_annuel = serializers.FloatField(min_value=0.01, max_value=1.0, default=0.15)
    revenu_mensuel = serializers.FloatField(min_value=0, required=False, default=0)
    charges = serializers.FloatField(min_value=0, required=False, default=0)


class WorkflowSerializer(serializers.Serializer):
    """Sérialiseur pour le changement d'état."""
    nouvel_etat = serializers.ChoiceField(choices=DossierPret.ETAT_CHOICES)
    motif = serializers.CharField(required=True)


class AuditLogSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.StringRelatedField(source='utilisateur', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'utilisateur', 'utilisateur_nom', 'action', 'action_display',
            'modele', 'objet_id', 'description', 'raison', 'date_action',
        ]


class DashboardSerializer(serializers.Serializer):
    """Sérialiseur pour les données du dashboard."""
    total_dossiers = serializers.IntegerField()
    dossiers_par_etat = serializers.DictField()
    risque_distribution = serializers.DictField()
    score_moyen = serializers.FloatField()
    montant_total = serializers.FloatField()
    alertes_fraude = serializers.IntegerField()
    taux_approbation = serializers.FloatField()
    par_objet = serializers.DictField()






