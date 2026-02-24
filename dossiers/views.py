"""
RiskGuard 360 - Vues
=====================
Contrôle d'accès strict par rôle :
  - Conseiller : ses propres dossiers/clients, modification si état=soumis
  - Gestionnaire : dossiers de ses clients, mise à jour infos financières
  - Manager Risque : tout voir, valider/refuser, alertes fraude, audit
  - Admin : tout, gestion utilisateurs, configuration
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db.models import Q, Count, Avg
from django.utils import timezone

from guardian.shortcuts import assign_perm

from .models import (
    Client, DossierPret, PieceJustificative, AuditLog, ResultatScoring,
    Notification, get_user_role, user_can_view_all, user_can_change_etat,
    user_can_edit_dossier,
)
from .forms import ClientForm, DossierPretForm, PieceJustificativeForm, ChangerEtatForm
from .services import (
    calculer_score_dossier, changer_etat_dossier, generer_rapport_pdf,
    get_dashboard_data, creer_audit_log, get_client_ip,
    exporter_dossiers_excel,
)
from scoring_engine.scoring import simuler_pret


def _get_role_context(user):
    """Contexte de rôle injecté dans chaque template."""
    role = get_user_role(user)
    return {
        'user_role': role,
        'is_conseiller': role == 'conseiller',
        'is_gestionnaire': role == 'gestionnaire',
        'is_manager': role in ('manager_risque', 'admin'),
        'is_admin': role == 'admin',
        'can_change_etat': user_can_change_etat(user),
        'can_view_all': user_can_view_all(user),
    }


# ──────────────────────────────────────────────
# LANDING PAGE
# ──────────────────────────────────────────────

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')


def quick_login(request, role):
    """Connexion rapide en un clic pour la démo."""
    accounts = {
        'admin': ('admin', 'admin123'),
        'conseiller': ('conseiller1', 'conseiller123'),
        'gestionnaire': ('gestionnaire1', 'gestionnaire123'),
        'manager': ('manager1', 'manager123'),
    }
    if role not in accounts:
        messages.error(request, "Rôle inconnu.")
        return redirect('login')

    username, password = accounts[role]
    user = authenticate(request, username=username, password=password)
    if user:
        login(request, user)
        return redirect('dashboard')
    messages.error(request, "Erreur de connexion.")
    return redirect('login')


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

@login_required
def dashboard(request):
    data = get_dashboard_data(request.user)

    etats_labels = ['Soumis', 'En Analyse', 'Validé', 'Refusé', 'Alerte Fraude']
    etats_keys = ['soumis', 'en_analyse', 'valide', 'refuse', 'alerte_fraude']
    etats_data = [data['dossiers_par_etat'].get(k, 0) for k in etats_keys]

    risque_labels = list(data['risque_distribution'].keys()) or ['Aucun']
    risque_data = list(data['risque_distribution'].values()) or [0]

    objet_display = dict(DossierPret.OBJET_PRET_CHOICES)
    objet_labels = [objet_display.get(k, k) for k in data['par_objet'].keys()]
    objet_data = list(data['par_objet'].values())

    notifications = Notification.objects.filter(
        destinataire=request.user, lue=False
    )[:5]

    context = {
        'data': data,
        'etats_labels': json.dumps(etats_labels),
        'etats_data': json.dumps(etats_data),
        'risque_labels': json.dumps(risque_labels),
        'risque_data': json.dumps(risque_data),
        'objet_labels': json.dumps(objet_labels),
        'objet_data': json.dumps(objet_data),
        'notifications': notifications,
        **_get_role_context(request.user),
    }
    return render(request, 'dossiers/dashboard.html', context)


# ──────────────────────────────────────────────
# GESTION CLIENTS
# ──────────────────────────────────────────────

def _get_visible_clients(user):
    """
    Retourne le queryset des clients visibles par l'utilisateur.
    - Admin / Manager : tous les clients
    - Gestionnaire : clients qu'il a créés (son portefeuille)
    - Conseiller : clients qu'il a créés
    """
    if user_can_view_all(user):
        return Client.objects.all()
    return Client.objects.filter(cree_par=user)


@login_required
def liste_clients(request):
    q = request.GET.get('q', '')
    clients = _get_visible_clients(request.user)

    if q:
        clients = clients.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) |
            Q(telephone__icontains=q) | Q(raison_sociale__icontains=q)
        )

    context = {'clients': clients, 'q': q, **_get_role_context(request.user)}
    return render(request, 'dossiers/clients/liste.html', context)


@login_required
def creer_client(request):
    role = get_user_role(request.user)
    # Le gestionnaire peut créer des clients, mais le manager ne crée pas directement
    if role not in ('conseiller', 'gestionnaire', 'admin'):
        messages.error(request, "Vous n'avez pas la permission de créer un client.")
        return redirect('liste_clients')

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.cree_par = request.user
            client.save()
            assign_perm('view_own_client', request.user, client)
            creer_audit_log(
                utilisateur=request.user, action='creation', modele='Client',
                objet_id=client.id, description=f"Création du client {client}",
                adresse_ip=get_client_ip(request),
            )
            messages.success(request, f"Client {client} créé avec succès.")
            return redirect('liste_clients')
    else:
        form = ClientForm()

    return render(request, 'dossiers/clients/form.html', {
        'form': form, 'titre': 'Nouveau Client', **_get_role_context(request.user)
    })


@login_required
def modifier_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    role = get_user_role(request.user)

    # Vérifier l'accès
    if not user_can_view_all(request.user) and client.cree_par != request.user:
        messages.error(request, "Vous n'avez pas accès à ce client.")
        return redirect('liste_clients')

    # Le gestionnaire peut modifier les infos financières, le conseiller aussi si c'est son client
    if role == 'manager_risque':
        messages.error(request, "En tant que Manager Risque, la modification directe des données client nécessite une justification via l'admin.")
        return redirect('detail_client', pk=pk)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            creer_audit_log(
                utilisateur=request.user, action='modification', modele='Client',
                objet_id=client.id, description=f"Modification du client {client}",
                adresse_ip=get_client_ip(request),
            )
            messages.success(request, f"Client {client} modifié.")
            return redirect('detail_client', pk=pk)
    else:
        form = ClientForm(instance=client)

    return render(request, 'dossiers/clients/form.html', {
        'form': form, 'titre': f'Modifier {client}', 'client': client,
        **_get_role_context(request.user),
    })


@login_required
def detail_client(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if not user_can_view_all(request.user) and client.cree_par != request.user:
        messages.error(request, "Accès refusé.")
        return redirect('liste_clients')
    dossiers = client.dossiers.all()
    return render(request, 'dossiers/clients/detail.html', {
        'client': client, 'dossiers': dossiers, **_get_role_context(request.user)
    })


# ──────────────────────────────────────────────
# GESTION DOSSIERS
# ──────────────────────────────────────────────

def _get_visible_dossiers(user):
    """
    Retourne les dossiers visibles :
    - Admin / Manager : tous
    - Gestionnaire : dossiers dont le client est dans son portefeuille
    - Conseiller : ses propres dossiers (conseiller = user)
    """
    qs = DossierPret.objects.select_related('client', 'conseiller')
    role = get_user_role(user)
    if role in ('manager_risque', 'admin'):
        return qs
    elif role == 'gestionnaire':
        return qs.filter(client__cree_par=user)
    else:  # conseiller
        return qs.filter(conseiller=user)


@login_required
def liste_dossiers(request):
    q = request.GET.get('q', '')
    etat = request.GET.get('etat', '')
    dossiers = _get_visible_dossiers(request.user)

    if q:
        dossiers = dossiers.filter(
            Q(reference__icontains=q) | Q(client__nom__icontains=q) | Q(client__prenom__icontains=q)
        )
    if etat:
        dossiers = dossiers.filter(etat=etat)

    return render(request, 'dossiers/dossiers/liste.html', {
        'dossiers': dossiers, 'q': q, 'etat': etat, 'etats': DossierPret.ETAT_CHOICES,
        **_get_role_context(request.user),
    })


@login_required
def creer_dossier(request):
    role = get_user_role(request.user)
    if role not in ('conseiller', 'admin'):
        messages.error(request, "Seuls les conseillers peuvent créer des dossiers de prêt.")
        return redirect('liste_dossiers')

    if request.method == 'POST':
        form = DossierPretForm(request.POST)
        if form.is_valid():
            dossier = form.save(commit=False)
            dossier.conseiller = request.user
            dossier.save()
            assign_perm('view_own_dossier', request.user, dossier)
            creer_audit_log(
                utilisateur=request.user, action='creation', modele='DossierPret',
                objet_id=dossier.id,
                description=f"Création du dossier {dossier.reference} pour {dossier.client}",
                adresse_ip=get_client_ip(request),
            )
            messages.success(request, f"Dossier {dossier.reference} créé.")
            return redirect('detail_dossier', pk=dossier.pk)
    else:
        form = DossierPretForm()
        # Le conseiller ne voit que ses propres clients
        if role == 'conseiller':
            form.fields['client'].queryset = Client.objects.filter(cree_par=request.user)

    return render(request, 'dossiers/dossiers/form.html', {
        'form': form, 'titre': 'Nouveau Dossier de Prêt',
        **_get_role_context(request.user),
    })


@login_required
def detail_dossier(request, pk):
    dossier = get_object_or_404(DossierPret.objects.select_related('client', 'conseiller'), pk=pk)
    role = get_user_role(request.user)

    # Contrôle d'accès par rôle
    if role == 'conseiller' and dossier.conseiller != request.user:
        messages.error(request, "Vous ne pouvez voir que vos propres dossiers.")
        return redirect('liste_dossiers')
    elif role == 'gestionnaire' and dossier.client.cree_par != request.user:
        messages.error(request, "Ce dossier n'est pas dans votre portefeuille.")
        return redirect('liste_dossiers')

    pieces = dossier.pieces.all()
    resultats = dossier.resultats_scoring.all()[:5]
    audits = AuditLog.objects.filter(modele='DossierPret', objet_id=str(dossier.id))[:20]

    piece_form = PieceJustificativeForm()
    etat_form = ChangerEtatForm()

    transitions = dossier.transitions_possibles
    etat_form.fields['nouvel_etat'].choices = [
        (k, v) for k, v in DossierPret.ETAT_CHOICES if k in transitions
    ]

    details = dossier.details_scoring or {}
    radar_data = json.dumps({
        'endettement': details.get('score_endettement', 0),
        'historique': details.get('score_historique', 0),
        'stabilite': details.get('score_stabilite', 0),
        'coherence': details.get('score_coherence', 0),
    })

    can_edit = user_can_edit_dossier(request.user, dossier)

    return render(request, 'dossiers/dossiers/detail.html', {
        'dossier': dossier, 'pieces': pieces, 'resultats': resultats,
        'audits': audits, 'piece_form': piece_form, 'etat_form': etat_form,
        'radar_data': radar_data, 'can_edit': can_edit,
        **_get_role_context(request.user),
    })


@login_required
def calculer_score_view(request, pk):
    dossier = get_object_or_404(DossierPret, pk=pk)

    # Seul le conseiller propriétaire ou le manager peut lancer le scoring
    role = get_user_role(request.user)
    if role == 'conseiller' and dossier.conseiller != request.user:
        messages.error(request, "Vous ne pouvez scorer que vos propres dossiers.")
        return redirect('liste_dossiers')
    if role == 'gestionnaire':
        messages.error(request, "Les gestionnaires ne peuvent pas lancer le scoring.")
        return redirect('detail_dossier', pk=pk)

    if dossier.etat not in ('soumis', 'en_analyse'):
        messages.warning(request, "Le scoring ne peut être calculé que pour les dossiers soumis ou en analyse.")
        return redirect('detail_dossier', pk=pk)

    try:
        resultat = calculer_score_dossier(dossier, request.user, get_client_ip(request))

        if resultat.alerte_fraude and dossier.etat == 'soumis':
            changer_etat_dossier(
                dossier, 'alerte_fraude', request.user,
                "Alerte fraude détectée par le moteur de scoring",
                get_client_ip(request)
            )
            messages.warning(request, f"ALERTE FRAUDE ! Score fraude: {resultat.score_fraude}/100")
        elif dossier.etat == 'soumis':
            changer_etat_dossier(
                dossier, 'en_analyse', request.user,
                "Passage automatique en analyse après calcul du score",
                get_client_ip(request)
            )

        messages.success(request,
            f"Score calculé : {resultat.score_global}/100 ({resultat.niveau_risque}) "
            f"| Fraude : {resultat.score_fraude}/100")
    except Exception as e:
        messages.error(request, f"Erreur : {e}")

    return redirect('detail_dossier', pk=pk)


@login_required
def changer_etat_view(request, pk):
    """Seuls le Manager Risque et l'Admin peuvent valider/refuser."""
    dossier = get_object_or_404(DossierPret, pk=pk)

    if not user_can_change_etat(request.user):
        messages.error(request, "Seul le Manager Risque peut valider ou refuser un dossier.")
        return redirect('detail_dossier', pk=pk)

    if request.method == 'POST':
        form = ChangerEtatForm(request.POST)
        if form.is_valid():
            success = changer_etat_dossier(
                dossier, form.cleaned_data['nouvel_etat'],
                request.user, form.cleaned_data['motif'],
                get_client_ip(request),
            )
            if success:
                messages.success(request, f"État changé en : {dossier.get_etat_display()}")
            else:
                messages.error(request, "Transition non autorisée.")
    return redirect('detail_dossier', pk=pk)


@login_required
def upload_piece(request, pk):
    """Le conseiller et le gestionnaire peuvent uploader des pièces."""
    dossier = get_object_or_404(DossierPret, pk=pk)
    role = get_user_role(request.user)

    if role == 'conseiller' and dossier.conseiller != request.user:
        messages.error(request, "Accès refusé.")
        return redirect('liste_dossiers')

    if request.method == 'POST':
        form = PieceJustificativeForm(request.POST, request.FILES)
        if form.is_valid():
            piece = form.save(commit=False)
            piece.dossier = dossier
            piece.nom_fichier = request.FILES['fichier'].name
            piece.uploade_par = request.user
            piece.save()
            creer_audit_log(
                utilisateur=request.user, action='upload_piece',
                modele='PieceJustificative', objet_id=piece.id,
                description=f"Upload {piece.get_type_piece_display()} pour {dossier.reference}",
                adresse_ip=get_client_ip(request),
            )
            messages.success(request, "Pièce justificative uploadée.")
        else:
            messages.error(request, "Erreur lors de l'upload.")
    return redirect('detail_dossier', pk=pk)


@login_required
def generer_pdf_view(request, pk):
    dossier = get_object_or_404(DossierPret, pk=pk)
    try:
        pdf_bytes = generer_rapport_pdf(dossier)
        creer_audit_log(
            utilisateur=request.user, action='generation_pdf',
            modele='DossierPret', objet_id=dossier.id,
            description=f"Génération PDF pour {dossier.reference}",
            adresse_ip=get_client_ip(request),
        )
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="rapport_{dossier.reference}.pdf"'
        return response
    except Exception as e:
        messages.error(request, f"Erreur PDF : {e}")
        return redirect('detail_dossier', pk=pk)


# ──────────────────────────────────────────────
# SIMULATION DE PRÊT
# ──────────────────────────────────────────────

@login_required
def simulation_pret(request):
    resultat = None
    if request.method == 'POST':
        try:
            montant = float(request.POST.get('montant', 0))
            duree = int(request.POST.get('duree', 12))
            taux = float(request.POST.get('taux', 15)) / 100
            revenu = float(request.POST.get('revenu', 0))
            charges = float(request.POST.get('charges', 0))
            resultat = simuler_pret(montant, duree, taux, revenu, charges)
        except (ValueError, TypeError) as e:
            messages.error(request, f"Erreur dans les données : {e}")

    return render(request, 'dossiers/simulation.html', {
        'resultat': resultat, **_get_role_context(request.user)
    })


# ──────────────────────────────────────────────
# EXPORT EXCEL
# ──────────────────────────────────────────────

@login_required
def export_excel(request):
    dossiers = _get_visible_dossiers(request.user)
    excel_bytes = exporter_dossiers_excel(dossiers)

    creer_audit_log(
        utilisateur=request.user, action='export_donnees',
        modele='DossierPret', objet_id='all',
        description=f"Export Excel de {dossiers.count()} dossiers",
        adresse_ip=get_client_ip(request),
    )

    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="riskguard_dossiers_{timezone.now().strftime("%Y%m%d")}.xlsx"'
    return response


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────

@login_required
def liste_notifications(request):
    notifications = Notification.objects.filter(destinataire=request.user)
    return render(request, 'dossiers/notifications.html', {
        'notifications': notifications, **_get_role_context(request.user)
    })


@login_required
def marquer_notification_lue(request, pk):
    notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    notif.lue = True
    notif.save()
    if notif.lien:
        return redirect(notif.lien)
    return redirect('liste_notifications')


# ──────────────────────────────────────────────
# AUDIT (Manager Risque + Admin uniquement)
# ──────────────────────────────────────────────

@login_required
def liste_audits(request):
    if not user_can_view_all(request.user):
        messages.error(request, "Seuls le Manager Risque et l'Administrateur ont accès aux logs d'audit.")
        return redirect('dashboard')

    audits = AuditLog.objects.select_related('utilisateur').all()[:100]
    return render(request, 'dossiers/audit/liste.html', {
        'audits': audits, **_get_role_context(request.user)
    })


# ──────────────────────────────────────────────
# API JSON (dashboard)
# ──────────────────────────────────────────────

@login_required
def api_dashboard_data(request):
    data = get_dashboard_data(request.user)
    return JsonResponse({
        'total_dossiers': data['total_dossiers'],
        'dossiers_par_etat': data['dossiers_par_etat'],
        'risque_distribution': data['risque_distribution'],
        'score_moyen': data['score_moyen'],
        'montant_total': float(data['montant_total']),
        'alertes_fraude': data['alertes_fraude'],
        'taux_approbation': data['taux_approbation'],
    })
