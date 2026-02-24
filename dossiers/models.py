"""
RiskGuard 360 - Modèles de données
===================================
Gestion des clients (Particulier / Entreprise), dossiers de prêt,
scores de risque, pièces justificatives, audit et agences.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid


# ──────────────────────────────────────────────
# AGENCES (Multi-agences / SaaS)
# ──────────────────────────────────────────────

class Agence(models.Model):
    """Agence bancaire pour la gestion multi-sites."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=200, verbose_name="Nom de l'agence")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code agence")
    adresse = models.TextField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='agences_gerees'
    )
    est_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Agence"
        verbose_name_plural = "Agences"
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom}"


class ProfilUtilisateur(models.Model):
    """Profil étendu avec rôle et agence."""

    ROLE_CHOICES = [
        ('conseiller', 'Conseiller Clientèle'),
        ('gestionnaire', 'Gestionnaire de Compte'),
        ('manager_risque', 'Manager Risque'),
        ('admin', 'Administrateur'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='profil'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='conseiller')
    agence = models.ForeignKey(
        Agence, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='membres'
    )
    telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_role_display()})"

    @property
    def est_conseiller(self):
        return self.role == 'conseiller'

    @property
    def est_gestionnaire(self):
        return self.role == 'gestionnaire'

    @property
    def est_manager(self):
        return self.role in ('manager_risque', 'admin')

    @property
    def est_admin(self):
        return self.role == 'admin'


def get_user_role(user):
    """
    Retourne le rôle de l'utilisateur.
    Superuser = 'admin', sinon lecture du ProfilUtilisateur.
    """
    if user.is_superuser:
        return 'admin'
    try:
        return user.profil.role
    except ProfilUtilisateur.DoesNotExist:
        return 'conseiller'


def user_can_view_all(user):
    """Le manager risque et l'admin voient tout."""
    return get_user_role(user) in ('manager_risque', 'admin')


def user_can_change_etat(user):
    """Seuls le manager risque et l'admin peuvent valider/refuser."""
    return get_user_role(user) in ('manager_risque', 'admin')


def user_can_edit_dossier(user, dossier):
    """
    Le conseiller peut modifier son dossier seulement si état = 'soumis'.
    Le gestionnaire peut modifier les infos financières de ses clients.
    Le manager/admin peut toujours modifier.
    """
    role = get_user_role(user)
    if role in ('manager_risque', 'admin'):
        return True
    if role == 'conseiller' and dossier.conseiller == user and dossier.etat == 'soumis':
        return True
    if role == 'gestionnaire' and dossier.client.cree_par == user:
        return True
    return False


# ──────────────────────────────────────────────
# CLIENTS
# ──────────────────────────────────────────────

class Client(models.Model):
    """Modèle de base pour tous les clients (héritage)."""

    TYPE_CHOICES = [
        ('particulier', 'Particulier'),
        ('entreprise', 'Entreprise'),
    ]

    PROFESSION_CHOICES = [
        ('etudiant', 'Étudiant'),
        ('salarie_junior', 'Salarié Junior (< 2 ans)'),
        ('salarie_confirme', 'Salarié Confirmé (2-5 ans)'),
        ('salarie_senior', 'Salarié Senior (> 5 ans)'),
        ('entrepreneur', 'Entrepreneur'),
        ('retraite', 'Retraité'),
        ('entreprise', 'Entreprise'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type_client = models.CharField(max_length=20, choices=TYPE_CHOICES, default='particulier')
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom", blank=True)
    date_naissance = models.DateField(verbose_name="Date de naissance", null=True, blank=True)
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")
    email = models.EmailField(verbose_name="Email", blank=True)
    adresse = models.TextField(verbose_name="Adresse", blank=True)
    numero_cni = models.CharField(max_length=30, blank=True, verbose_name="N° CNI")
    profession = models.CharField(max_length=30, choices=PROFESSION_CHOICES)
    revenu_mensuel = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Revenu mensuel (FCFA)",
        validators=[MinValueValidator(0)]
    )
    charges_mensuelles = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Charges mensuelles (FCFA)",
        validators=[MinValueValidator(0)]
    )
    dettes_existantes = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Dettes mensuelles existantes (FCFA)",
        validators=[MinValueValidator(0)]
    )
    anciennete_emploi = models.DecimalField(
        max_digits=5, decimal_places=1, default=0,
        verbose_name="Ancienneté emploi (années)",
        validators=[MinValueValidator(0)]
    )
    incidents_paiement = models.PositiveIntegerField(
        default=0,
        verbose_name="Incidents de paiement (12 derniers mois)"
    )
    # Champs spécifiques Entreprise
    raison_sociale = models.CharField(max_length=200, blank=True, verbose_name="Raison sociale")
    numero_registre_commerce = models.CharField(max_length=50, blank=True, verbose_name="N° Registre Commerce")
    secteur_activite = models.CharField(max_length=100, blank=True, verbose_name="Secteur d'activité")
    chiffre_affaires_annuel = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name="Chiffre d'affaires annuel (FCFA)"
    )

    # Multi-agences
    agence = models.ForeignKey(
        Agence, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='clients'
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='clients_crees'
    )

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['-date_creation']
        permissions = [
            ('view_own_client', 'Peut voir ses propres clients'),
            ('view_all_clients', 'Peut voir tous les clients'),
        ]

    def __str__(self):
        if self.type_client == 'entreprise':
            return f"{self.raison_sociale} (Entreprise)"
        return f"{self.prenom} {self.nom}"

    @property
    def age(self):
        if self.date_naissance:
            today = timezone.now().date()
            return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
            )
        return 30  # valeur par défaut


# ──────────────────────────────────────────────
# COMPTES BANCAIRES
# ──────────────────────────────────────────────

class CompteBancaire(models.Model):
    """Compte bancaire lié à un client."""

    TYPE_COMPTE_CHOICES = [
        ('epargne', 'Épargne'),
        ('courant', 'Courant'),
        ('professionnel', 'Professionnel'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='comptes')
    numero_compte = models.CharField(max_length=30, unique=True, verbose_name="Numéro de compte")
    type_compte = models.CharField(max_length=20, choices=TYPE_COMPTE_CHOICES)
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Solde (FCFA)")
    date_ouverture = models.DateField(verbose_name="Date d'ouverture")
    est_actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Compte bancaire"
        verbose_name_plural = "Comptes bancaires"

    def __str__(self):
        return f"{self.numero_compte} ({self.get_type_compte_display()}) - {self.client}"


# ──────────────────────────────────────────────
# DOSSIERS DE PRÊT
# ──────────────────────────────────────────────

class DossierPret(models.Model):
    """Dossier de demande de prêt avec workflow d'états."""

    ETAT_CHOICES = [
        ('soumis', 'Soumis'),
        ('en_analyse', 'En Analyse'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
        ('alerte_fraude', 'Alerte Fraude'),
    ]

    OBJET_PRET_CHOICES = [
        ('personnel', 'Prêt Personnel'),
        ('immobilier', 'Prêt Immobilier'),
        ('vehicule', 'Prêt Véhicule'),
        ('education', 'Prêt Éducation'),
        ('commerce', 'Prêt Commercial'),
        ('agricole', 'Prêt Agricole'),
        ('equipement', 'Prêt Équipement'),
        ('autre', 'Autre'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=20, unique=True, verbose_name="Référence dossier")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dossiers')
    conseiller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='dossiers_geres',
        verbose_name="Conseiller"
    )

    # Informations du prêt
    montant_demande = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Montant demandé (FCFA)",
        validators=[MinValueValidator(10000)]
    )
    duree_mois = models.PositiveIntegerField(
        verbose_name="Durée (mois)",
        validators=[MinValueValidator(1), MaxValueValidator(360)]
    )
    objet_pret = models.CharField(
        max_length=20, choices=OBJET_PRET_CHOICES,
        verbose_name="Objet du prêt"
    )
    apport_personnel = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Apport personnel (FCFA)",
        validators=[MinValueValidator(0)]
    )
    description = models.TextField(blank=True, verbose_name="Description / Justification")

    # Workflow
    etat = models.CharField(
        max_length=20, choices=ETAT_CHOICES, default='soumis',
        verbose_name="État du dossier"
    )
    date_soumission = models.DateTimeField(auto_now_add=True, verbose_name="Date de soumission")
    date_analyse = models.DateTimeField(null=True, blank=True)
    date_decision = models.DateTimeField(null=True, blank=True)
    motif_decision = models.TextField(blank=True, verbose_name="Motif de la décision")

    # Scoring
    score_risque = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="Score de risque"
    )
    score_fraude = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name="Score de fraude"
    )
    niveau_risque = models.CharField(max_length=30, blank=True, verbose_name="Niveau de risque")
    recommandation = models.TextField(blank=True, verbose_name="Recommandation du système")
    explication_score = models.TextField(blank=True, verbose_name="Explication du score (IA)")
    alerte_fraude = models.BooleanField(default=False, verbose_name="Alerte fraude")

    # Détails scoring (JSON)
    details_scoring = models.JSONField(null=True, blank=True, verbose_name="Détails du scoring")

    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier de prêt"
        verbose_name_plural = "Dossiers de prêt"
        ordering = ['-date_soumission']
        permissions = [
            ('view_own_dossier', 'Peut voir ses propres dossiers'),
            ('view_all_dossiers', 'Peut voir tous les dossiers'),
            ('change_etat_dossier', "Peut changer l'état d'un dossier"),
            ('generate_pdf_dossier', 'Peut générer le PDF du dossier'),
        ]

    def __str__(self):
        return f"Dossier {self.reference} - {self.client} ({self.get_etat_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generer_reference()
        super().save(*args, **kwargs)

    def _generer_reference(self):
        """Génère une référence unique : RG-AAAA-XXXXX"""
        annee = timezone.now().year
        dernier = DossierPret.objects.filter(
            reference__startswith=f'RG-{annee}-'
        ).order_by('-reference').first()
        if dernier:
            try:
                num = int(dernier.reference.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f'RG-{annee}-{num:05d}'

    @property
    def transitions_possibles(self):
        """Retourne les transitions d'état possibles."""
        transitions = {
            'soumis': ['en_analyse', 'alerte_fraude'],
            'en_analyse': ['valide', 'refuse', 'alerte_fraude'],
            'valide': [],
            'refuse': [],
            'alerte_fraude': ['en_analyse', 'refuse'],
        }
        return transitions.get(self.etat, [])


# ──────────────────────────────────────────────
# PIÈCES JUSTIFICATIVES
# ──────────────────────────────────────────────

class PieceJustificative(models.Model):
    """Pièce justificative attachée à un dossier."""

    TYPE_PIECE_CHOICES = [
        ('cni', "Carte Nationale d'Identité"),
        ('bulletin_salaire', 'Bulletin de salaire'),
        ('releve_bancaire', 'Relevé bancaire'),
        ('attestation_travail', 'Attestation de travail'),
        ('registre_commerce', 'Registre de commerce'),
        ('bilan', 'Bilan comptable'),
        ('facture_proforma', 'Facture proforma'),
        ('titre_foncier', 'Titre foncier'),
        ('autre', 'Autre document'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(DossierPret, on_delete=models.CASCADE, related_name='pieces')
    type_piece = models.CharField(max_length=30, choices=TYPE_PIECE_CHOICES, verbose_name="Type de pièce")
    nom_fichier = models.CharField(max_length=255, verbose_name="Nom du fichier")
    fichier = models.FileField(upload_to='pieces_justificatives/%Y/%m/', verbose_name="Fichier")
    date_upload = models.DateTimeField(auto_now_add=True)
    uploade_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        verbose_name = "Pièce justificative"
        verbose_name_plural = "Pièces justificatives"

    def __str__(self):
        return f"{self.get_type_piece_display()} - {self.dossier.reference}"


# ──────────────────────────────────────────────
# RÉSULTATS DE SCORING
# ──────────────────────────────────────────────

class ResultatScoring(models.Model):
    """Historique des résultats de scoring pour un dossier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(DossierPret, on_delete=models.CASCADE, related_name='resultats_scoring')

    score_global = models.DecimalField(max_digits=6, decimal_places=2)
    score_endettement = models.DecimalField(max_digits=6, decimal_places=2)
    score_historique = models.DecimalField(max_digits=6, decimal_places=2)
    score_stabilite = models.DecimalField(max_digits=6, decimal_places=2)
    score_coherence = models.DecimalField(max_digits=6, decimal_places=2)
    score_fraude = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ratio_endettement = models.DecimalField(max_digits=6, decimal_places=4)
    niveau_risque = models.CharField(max_length=30)
    recommandation = models.TextField()
    explication = models.TextField(blank=True, verbose_name="Explication IA du score")
    alerte_fraude = models.BooleanField(default=False)
    alertes = models.JSONField(default=list)
    details = models.JSONField(default=dict)

    date_calcul = models.DateTimeField(auto_now_add=True)
    calcule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        verbose_name = "Résultat de scoring"
        verbose_name_plural = "Résultats de scoring"
        ordering = ['-date_calcul']

    def __str__(self):
        return f"Score {self.score_global}/100 - {self.dossier.reference} ({self.date_calcul:%d/%m/%Y})"


# ──────────────────────────────────────────────
# LOGS D'AUDIT
# ──────────────────────────────────────────────

class AuditLog(models.Model):
    """
    Table d'audit traçant toutes les modifications.
    Qui a modifié quoi, quand, et pourquoi ?
    """

    ACTION_CHOICES = [
        ('creation', 'Création'),
        ('modification', 'Modification'),
        ('changement_etat', "Changement d'état"),
        ('calcul_score', 'Calcul de score'),
        ('modification_score', 'Modification de score'),
        ('upload_piece', 'Upload de pièce'),
        ('generation_pdf', 'Génération PDF'),
        ('export_donnees', 'Export de données'),
        ('suppression', 'Suppression'),
        ('notification', 'Notification envoyée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, verbose_name="Utilisateur"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    modele = models.CharField(max_length=50, verbose_name="Modèle concerné")
    objet_id = models.CharField(max_length=50, verbose_name="ID de l'objet")
    description = models.TextField(verbose_name="Description de l'action")
    donnees_avant = models.JSONField(null=True, blank=True, verbose_name="Données avant modification")
    donnees_apres = models.JSONField(null=True, blank=True, verbose_name="Données après modification")
    raison = models.TextField(blank=True, verbose_name="Raison / Justification")
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log d'audit"
        verbose_name_plural = "Logs d'audit"
        ordering = ['-date_action']

    def __str__(self):
        return f"[{self.date_action:%d/%m/%Y %H:%M}] {self.utilisateur} - {self.get_action_display()} - {self.modele}"


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────

class Notification(models.Model):
    """Notification interne et par email."""

    TYPE_CHOICES = [
        ('info', 'Information'),
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('danger', 'Alerte'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications'
    )
    type_notif = models.CharField(max_length=10, choices=TYPE_CHOICES, default='info')
    titre = models.CharField(max_length=200)
    message = models.TextField()
    lien = models.CharField(max_length=500, blank=True)
    lue = models.BooleanField(default=False)
    envoyee_email = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']

    def __str__(self):
        return f"[{'✓' if self.lue else '●'}] {self.titre}"
