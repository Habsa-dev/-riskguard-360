"""
RiskGuard 360 - API REST Views
================================
API complète pour intégration avec des systèmes externes.
"""

from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from .models import Client, DossierPret, ResultatScoring, AuditLog
from .serializers import (
    ClientSerializer, DossierPretSerializer, DossierPretListSerializer,
    ResultatScoringSerializer, ScoreRequestSerializer,
    SimulationSerializer, WorkflowSerializer, AuditLogSerializer,
    DashboardSerializer,
)
from .services import (
    calculer_score_dossier, changer_etat_dossier, get_dashboard_data,
    get_client_ip,
)
from scoring_engine.scoring import simuler_pret


# ──────────────────────────────────────────────
# ViewSets CRUD
# ──────────────────────────────────────────────

class ClientViewSet(viewsets.ModelViewSet):
    """
    API CRUD pour les clients.
    GET /api/clients/ - Liste
    POST /api/clients/ - Créer
    GET /api/clients/{id}/ - Détail
    PUT/PATCH /api/clients/{id}/ - Modifier
    DELETE /api/clients/{id}/ - Supprimer
    """
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filterset_fields = ['type_client', 'profession']
    search_fields = ['nom', 'prenom', 'telephone', 'raison_sociale']
    ordering_fields = ['nom', 'date_creation', 'revenu_mensuel']

    def perform_create(self, serializer):
        serializer.save(cree_par=self.request.user)


class DossierPretViewSet(viewsets.ModelViewSet):
    """
    API CRUD pour les dossiers de prêt.
    GET /api/dossiers/ - Liste
    POST /api/dossiers/ - Créer
    GET /api/dossiers/{id}/ - Détail
    """
    queryset = DossierPret.objects.select_related('client', 'conseiller').all()
    filterset_fields = ['etat', 'objet_pret', 'alerte_fraude']
    search_fields = ['reference', 'client__nom', 'client__prenom']
    ordering_fields = ['date_soumission', 'score_risque', 'montant_demande']

    def get_serializer_class(self):
        if self.action == 'list':
            return DossierPretListSerializer
        return DossierPretSerializer

    def perform_create(self, serializer):
        serializer.save(conseiller=self.request.user)

    @action(detail=True, methods=['post'])
    def calculer_score(self, request, pk=None):
        """POST /api/dossiers/{id}/calculer_score/ - Calcule le score."""
        dossier = self.get_object()
        resultat = calculer_score_dossier(dossier, request.user, get_client_ip(request))
        return Response({
            'score_global': float(resultat.score_global),
            'score_fraude': float(resultat.score_fraude),
            'niveau_risque': resultat.niveau_risque,
            'recommandation': resultat.recommandation,
            'explication': resultat.explication,
            'alerte_fraude': resultat.alerte_fraude,
            'alertes': resultat.alertes,
        })

    @action(detail=True, methods=['post'])
    def changer_etat(self, request, pk=None):
        """POST /api/dossiers/{id}/changer_etat/ - Change l'état."""
        dossier = self.get_object()
        serializer = WorkflowSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        success = changer_etat_dossier(
            dossier,
            serializer.validated_data['nouvel_etat'],
            request.user,
            serializer.validated_data['motif'],
            get_client_ip(request),
        )

        if success:
            return Response({
                'status': 'success',
                'nouvel_etat': dossier.etat,
                'etat_display': dossier.get_etat_display(),
            })
        return Response(
            {'error': 'Transition non autorisée'},
            status=status.HTTP_400_BAD_REQUEST,
        )


# ──────────────────────────────────────────────
# Vues spéciales
# ──────────────────────────────────────────────

class ScoreAPIView(APIView):
    """
    GET /api/score/{dossier_id}/ - Obtenir le score d'un dossier.
    """
    def get(self, request, pk):
        try:
            dossier = DossierPret.objects.get(pk=pk)
        except DossierPret.DoesNotExist:
            return Response({'error': 'Dossier non trouvé'}, status=404)

        if dossier.score_risque is None:
            return Response({'error': 'Score non calculé'}, status=404)

        return Response({
            'reference': dossier.reference,
            'score_risque': float(dossier.score_risque),
            'score_fraude': float(dossier.score_fraude or 0),
            'niveau_risque': dossier.niveau_risque,
            'recommandation': dossier.recommandation,
            'explication': dossier.explication_score,
            'alerte_fraude': dossier.alerte_fraude,
            'details': dossier.details_scoring,
        })


class SimulationAPIView(APIView):
    """
    POST /api/simulation/ - Simulation de prêt.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SimulationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        resultat = simuler_pret(
            montant=data['montant'],
            duree_mois=data['duree_mois'],
            taux_annuel=data.get('taux_annuel', 0.15),
            revenu_mensuel=data.get('revenu_mensuel', 0),
            charges=data.get('charges', 0),
        )
        return Response(resultat)


class PortfolioRiskAPIView(APIView):
    """
    GET /api/portfolio-risk/ - Statistiques du portefeuille risque.
    """
    def get(self, request):
        data = get_dashboard_data(request.user)
        serializer = DashboardSerializer(data)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/audit/ - Journal d'audit (lecture seule).
    """
    queryset = AuditLog.objects.select_related('utilisateur').all()
    serializer_class = AuditLogSerializer
    filterset_fields = ['action', 'modele']
    search_fields = ['description']
    ordering_fields = ['date_action']






