"""
RiskGuard 360 - Administration Django
"""

from django.contrib import admin
from guardian.admin import GuardedModelAdmin
from .models import (
    Client, CompteBancaire, DossierPret, PieceJustificative,
    ResultatScoring, AuditLog, Agence, ProfilUtilisateur, Notification
)


@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ('code', 'nom', 'responsable', 'est_active', 'date_creation')
    list_filter = ('est_active',)
    search_fields = ('nom', 'code')


@admin.register(ProfilUtilisateur)
class ProfilUtilisateurAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'agence', 'telephone')
    list_filter = ('role', 'agence')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')


@admin.register(Client)
class ClientAdmin(GuardedModelAdmin):
    list_display = ('nom', 'prenom', 'type_client', 'profession', 'revenu_mensuel', 'agence', 'date_creation')
    list_filter = ('type_client', 'profession', 'agence')
    search_fields = ('nom', 'prenom', 'telephone', 'raison_sociale', 'numero_cni')


@admin.register(CompteBancaire)
class CompteBancaireAdmin(admin.ModelAdmin):
    list_display = ('numero_compte', 'client', 'type_compte', 'solde', 'est_actif')
    list_filter = ('type_compte', 'est_actif')


@admin.register(DossierPret)
class DossierPretAdmin(GuardedModelAdmin):
    list_display = ('reference', 'client', 'montant_demande', 'etat', 'score_risque', 'score_fraude', 'alerte_fraude', 'date_soumission')
    list_filter = ('etat', 'objet_pret', 'alerte_fraude')
    search_fields = ('reference', 'client__nom', 'client__prenom')
    readonly_fields = ('reference', 'score_risque', 'score_fraude', 'niveau_risque', 'explication_score', 'details_scoring')


@admin.register(PieceJustificative)
class PieceJustificativeAdmin(admin.ModelAdmin):
    list_display = ('type_piece', 'dossier', 'nom_fichier', 'date_upload')
    list_filter = ('type_piece',)


@admin.register(ResultatScoring)
class ResultatScoringAdmin(admin.ModelAdmin):
    list_display = ('dossier', 'score_global', 'score_fraude', 'niveau_risque', 'alerte_fraude', 'date_calcul')
    list_filter = ('niveau_risque', 'alerte_fraude')
    readonly_fields = ('dossier', 'score_global', 'score_endettement', 'score_historique',
                       'score_stabilite', 'score_coherence', 'score_fraude', 'explication',
                       'alertes', 'details')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('date_action', 'utilisateur', 'action', 'modele', 'description')
    list_filter = ('action', 'modele')
    search_fields = ('description', 'utilisateur__username')
    readonly_fields = ('utilisateur', 'action', 'modele', 'objet_id', 'description',
                       'donnees_avant', 'donnees_apres', 'raison', 'adresse_ip', 'date_action')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('titre', 'destinataire', 'type_notif', 'lue', 'envoyee_email', 'date_creation')
    list_filter = ('type_notif', 'lue', 'envoyee_email')
    search_fields = ('titre', 'message')
