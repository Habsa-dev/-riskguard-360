"""
Script de configuration initiale et données de démonstration.
RiskGuard 360 — Version Pro avec RBAC (4 acteurs)
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskguard.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from dossiers.models import Client, DossierPret, Agence, ProfilUtilisateur
from dossiers.services import calculer_score_dossier
from guardian.shortcuts import assign_perm
from datetime import date

print("=" * 60)
print("  RISKGUARD 360 — Configuration Initiale (RBAC)")
print("=" * 60)


# ──────────────────────────────────────────────
# 1. GROUPES DJANGO (RBAC)
# ──────────────────────────────────────────────

def setup_groups():
    """Crée les 4 groupes avec les permissions appropriées."""

    # Permissions modèle Client
    ct_client = ContentType.objects.get_for_model(Client)
    ct_dossier = ContentType.objects.get_for_model(DossierPret)

    # ─── Groupe Conseiller Clientèle ───
    grp_conseiller, _ = Group.objects.get_or_create(name='Conseiller Clientèle')
    grp_conseiller.permissions.clear()
    perms_conseiller = [
        'add_client', 'change_client', 'view_client',
        'view_own_client',
        'add_dossierpret', 'view_dossierpret',
        'view_own_dossier',
        'add_piecejustificative', 'view_piecejustificative',
        'generate_pdf_dossier',
    ]
    for codename in perms_conseiller:
        try:
            perm = Permission.objects.get(codename=codename)
            grp_conseiller.permissions.add(perm)
        except Permission.DoesNotExist:
            pass

    # ─── Groupe Gestionnaire de Compte ───
    grp_gestionnaire, _ = Group.objects.get_or_create(name='Gestionnaire de Compte')
    grp_gestionnaire.permissions.clear()
    perms_gestionnaire = [
        'add_client', 'change_client', 'view_client',
        'view_own_client',
        'view_dossierpret',
        'view_own_dossier',
        'view_comptebancaire', 'add_comptebancaire', 'change_comptebancaire',
        'add_piecejustificative', 'view_piecejustificative',
        'generate_pdf_dossier',
    ]
    for codename in perms_gestionnaire:
        try:
            perm = Permission.objects.get(codename=codename)
            grp_gestionnaire.permissions.add(perm)
        except Permission.DoesNotExist:
            pass

    # ─── Groupe Manager Risque ───
    grp_manager, _ = Group.objects.get_or_create(name='Manager Risque')
    grp_manager.permissions.clear()
    perms_manager = [
        'view_client', 'view_all_clients',
        'view_dossierpret', 'view_all_dossiers',
        'change_etat_dossier',
        'generate_pdf_dossier',
        'view_resultatscoring',
        'view_auditlog',
        'view_piecejustificative',
        'view_notification',
    ]
    for codename in perms_manager:
        try:
            perm = Permission.objects.get(codename=codename)
            grp_manager.permissions.add(perm)
        except Permission.DoesNotExist:
            pass

    # ─── Groupe Administrateur ───
    grp_admin, _ = Group.objects.get_or_create(name='Administrateur')
    grp_admin.permissions.clear()
    all_perms = Permission.objects.filter(
        content_type__app_label='dossiers'
    )
    grp_admin.permissions.set(all_perms)

    print("[OK] Groupes RBAC créés :")
    print("     - Conseiller Clientèle")
    print("     - Gestionnaire de Compte")
    print("     - Manager Risque")
    print("     - Administrateur")

    return grp_conseiller, grp_gestionnaire, grp_manager, grp_admin


grp_conseiller, grp_gestionnaire, grp_manager, grp_admin = setup_groups()


# ──────────────────────────────────────────────
# 2. AGENCES
# ──────────────────────────────────────────────

agence_dkr, _ = Agence.objects.get_or_create(
    code='DKR-001',
    defaults={
        'nom': 'Agence Dakar Plateau',
        'adresse': 'Avenue Léopold Sédar Senghor, Dakar',
        'telephone': '338001122',
    }
)
agence_thies, _ = Agence.objects.get_or_create(
    code='THS-001',
    defaults={
        'nom': 'Agence Thiès Centre',
        'adresse': 'Boulevard de la Gare, Thiès',
        'telephone': '338003344',
    }
)
print(f"[OK] Agences créées : {agence_dkr.nom}, {agence_thies.nom}")


# ──────────────────────────────────────────────
# 3. UTILISATEURS + PROFILS + GROUPES
# ──────────────────────────────────────────────

def create_user(username, first_name, last_name, email, password, role, agence, group, is_staff=False):
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'is_staff': is_staff,
        }
    )
    user.set_password(password)
    user.is_staff = is_staff
    user.save()
    user.groups.clear()
    user.groups.add(group)
    ProfilUtilisateur.objects.update_or_create(
        user=user, defaults={'role': role, 'agence': agence}
    )
    return user


# Admin
admin = User.objects.filter(username='admin').first()
if not admin:
    admin = User.objects.create_superuser('admin', 'admin@riskguard.com', 'admin123')
admin.set_password('admin123')
admin.first_name = 'Administrateur'
admin.last_name = 'RiskGuard'
admin.is_staff = True
admin.is_superuser = True
admin.save()
admin.groups.add(grp_admin)
ProfilUtilisateur.objects.update_or_create(
    user=admin, defaults={'role': 'admin', 'agence': agence_dkr}
)
print("[OK] Admin         : admin / admin123")

# Conseiller 1
conseiller1 = create_user(
    'conseiller1', 'Moussa', 'Diop', 'moussa.diop@riskguard.sn',
    'conseiller123', 'conseiller', agence_dkr, grp_conseiller
)
print("[OK] Conseiller 1  : conseiller1 / conseiller123 (Dakar)")

# Conseiller 2
conseiller2 = create_user(
    'conseiller2', 'Fatou', 'Ndiaye', 'fatou.ndiaye@riskguard.sn',
    'conseiller123', 'conseiller', agence_thies, grp_conseiller
)
print("[OK] Conseiller 2  : conseiller2 / conseiller123 (Thiès)")

# Gestionnaire de Compte
gestionnaire = create_user(
    'gestionnaire1', 'Aminata', 'Sow', 'aminata.sow@riskguard.sn',
    'gestionnaire123', 'gestionnaire', agence_dkr, grp_gestionnaire
)
print("[OK] Gestionnaire  : gestionnaire1 / gestionnaire123 (Dakar)")

# Manager Risque
manager = create_user(
    'manager1', 'Ousmane', 'Ba', 'ousmane.ba@riskguard.sn',
    'manager123', 'manager_risque', agence_dkr, grp_manager,
    is_staff=True
)
print("[OK] Manager Risque: manager1 / manager123")


# ──────────────────────────────────────────────
# 4. CLIENTS
# ──────────────────────────────────────────────

clients_data = [
    {
        'nom': 'Diouf', 'prenom': 'Paul', 'type_client': 'particulier',
        'profession': 'salarie_confirme', 'telephone': '772347689',
        'revenu_mensuel': 450000, 'charges_mensuelles': 80000,
        'dettes_existantes': 30000, 'anciennete_emploi': 4,
        'incidents_paiement': 0, 'date_naissance': date(1988, 5, 15),
        'email': 'paul.diouf@email.sn', 'adresse': 'Dakar, Plateau',
        'numero_cni': 'SN-1234567890',
        'cree_par': conseiller1, 'agence': agence_dkr,
    },
    {
        'nom': 'Diop', 'prenom': 'Marie', 'type_client': 'particulier',
        'profession': 'salarie_senior', 'telephone': '781234567',
        'revenu_mensuel': 800000, 'charges_mensuelles': 150000,
        'dettes_existantes': 0, 'anciennete_emploi': 8,
        'incidents_paiement': 0, 'date_naissance': date(1980, 3, 22),
        'email': 'marie.diop@email.sn', 'adresse': 'Thiès, Centre',
        'numero_cni': 'SN-9876543210',
        'cree_par': conseiller2, 'agence': agence_thies,
    },
    {
        'nom': 'Talla', 'prenom': 'Ibrahim', 'type_client': 'particulier',
        'profession': 'etudiant', 'telephone': '769876543',
        'revenu_mensuel': 50000, 'charges_mensuelles': 20000,
        'dettes_existantes': 10000, 'anciennete_emploi': 0,
        'incidents_paiement': 2, 'date_naissance': date(2001, 11, 8),
        'email': 'ibrahim.talla@email.sn', 'adresse': 'Dakar, Parcelles',
        'cree_par': conseiller1, 'agence': agence_dkr,
    },
    {
        'nom': 'SARL Tech Innovation', 'prenom': '', 'type_client': 'entreprise',
        'profession': 'entreprise', 'telephone': '705551234',
        'revenu_mensuel': 5000000, 'charges_mensuelles': 2000000,
        'dettes_existantes': 500000, 'anciennete_emploi': 6,
        'incidents_paiement': 1,
        'raison_sociale': 'SARL Tech Innovation',
        'numero_registre_commerce': 'RC/DKR/2019/B/4521',
        'secteur_activite': "Technologies de l'information",
        'chiffre_affaires_annuel': 60000000,
        'cree_par': gestionnaire, 'agence': agence_dkr,
    },
    {
        'nom': 'Faye', 'prenom': 'Christelle', 'type_client': 'particulier',
        'profession': 'entrepreneur', 'telephone': '776789012',
        'revenu_mensuel': 1200000, 'charges_mensuelles': 350000,
        'dettes_existantes': 200000, 'anciennete_emploi': 3,
        'incidents_paiement': 1, 'date_naissance': date(1992, 7, 3),
        'email': 'christelle.faye@email.sn', 'adresse': 'Dakar, Almadies',
        'numero_cni': 'SN-5551234567',
        'cree_par': conseiller1, 'agence': agence_dkr,
    },
]

clients = []
for data in clients_data:
    client, created = Client.objects.get_or_create(
        nom=data['nom'],
        prenom=data.get('prenom', ''),
        defaults=data,
    )
    clients.append(client)
    if created:
        assign_perm('view_own_client', data['cree_par'], client)
        print(f"[OK] Client créé : {client} (par {data['cree_par']})")
    else:
        print(f"[--] Client existant : {client}")


# ──────────────────────────────────────────────
# 5. DOSSIERS DE PRÊT
# ──────────────────────────────────────────────

dossiers_data = [
    {
        'client': clients[0], 'montant_demande': 5000000,
        'duree_mois': 36, 'objet_pret': 'personnel',
        'apport_personnel': 500000,
        'description': 'Prêt personnel pour travaux de rénovation domicile.',
        'conseiller': conseiller1,
    },
    {
        'client': clients[1], 'montant_demande': 15000000,
        'duree_mois': 60, 'objet_pret': 'immobilier',
        'apport_personnel': 3000000,
        'description': "Acquisition d'un terrain à bâtir à Thiès.",
        'conseiller': conseiller2,
    },
    {
        'client': clients[2], 'montant_demande': 50000000,
        'duree_mois': 24, 'objet_pret': 'commerce',
        'apport_personnel': 0,
        'description': 'Demande suspecte — étudiant demandant un montant très élevé.',
        'conseiller': conseiller1,
    },
    {
        'client': clients[3], 'montant_demande': 25000000,
        'duree_mois': 48, 'objet_pret': 'equipement',
        'apport_personnel': 5000000,
        'description': "Achat de matériel informatique pour expansion de l'entreprise.",
        'conseiller': gestionnaire,
    },
    {
        'client': clients[4], 'montant_demande': 8000000,
        'duree_mois': 24, 'objet_pret': 'commerce',
        'apport_personnel': 1000000,
        'description': "Ouverture d'un salon de coiffure haut de gamme.",
        'conseiller': conseiller1,
    },
]

print("\n--- Calcul des scores ---")
for data in dossiers_data:
    dossier, created = DossierPret.objects.get_or_create(
        client=data['client'],
        montant_demande=data['montant_demande'],
        defaults=data,
    )
    if created:
        assign_perm('view_own_dossier', data['conseiller'], dossier)
        try:
            resultat = calculer_score_dossier(dossier, admin)
            print(f"[OK] {dossier.reference} | Score: {resultat.score_global}/100 "
                  f"({resultat.niveau_risque}) | Fraude: {resultat.score_fraude}/100"
                  + (" | ALERTE FRAUDE" if resultat.alerte_fraude else ""))
        except Exception as e:
            print(f"[!!] {dossier.reference} — Erreur scoring : {e}")
    else:
        print(f"[--] Dossier existant : {dossier.reference}")


# ──────────────────────────────────────────────
# RÉSUMÉ
# ──────────────────────────────────────────────

print("\n" + "=" * 60)
print("  CONFIGURATION TERMINEE — RiskGuard 360 Pro (RBAC)")
print("=" * 60)
print(f"""
  Donnees creees :
     {Agence.objects.count()} agences
     {User.objects.count()} utilisateurs
     {Group.objects.count()} groupes
     {Client.objects.count()} clients
     {DossierPret.objects.count()} dossiers de pret

  Comptes disponibles :
     Admin              : admin / admin123          (tout voir, tout faire)
     Conseiller 1       : conseiller1 / conseiller123  (ses dossiers uniquement)
     Conseiller 2       : conseiller2 / conseiller123  (ses dossiers uniquement)
     Gestionnaire       : gestionnaire1 / gestionnaire123 (portefeuille clients)
     Manager Risque     : manager1 / manager123     (tout voir, valider/refuser)

  Matrice des droits :
     Conseiller  -> Creer clients/dossiers, modifier si etat=soumis, upload pieces
     Gestionnaire-> Voir ses clients, infos financieres, historique paiements
     Manager     -> Tout voir, valider/refuser, alertes fraude, audit
     Admin       -> Tout + gestion users, configuration seuils

  Lancez le serveur :
     python manage.py runserver

  URLs importantes :
     Landing page  : http://127.0.0.1:8000/
     Connexion     : http://127.0.0.1:8000/login/
     Dashboard     : http://127.0.0.1:8000/dashboard/
     API REST      : http://127.0.0.1:8000/api/
     Simulation    : http://127.0.0.1:8000/simulation/
     Admin Django  : http://127.0.0.1:8000/admin/
""")
print("=" * 60)
