"""
RiskGuard 360 - URLs de l'API REST
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'clients', api_views.ClientViewSet, basename='api-client')
router.register(r'dossiers', api_views.DossierPretViewSet, basename='api-dossier')
router.register(r'audit', api_views.AuditLogViewSet, basename='api-audit')

urlpatterns = [
    path('', include(router.urls)),
    path('score/<uuid:pk>/', api_views.ScoreAPIView.as_view(), name='api-score'),
    path('simulation/', api_views.SimulationAPIView.as_view(), name='api-simulation'),
    path('portfolio-risk/', api_views.PortfolioRiskAPIView.as_view(), name='api-portfolio-risk'),
    # Authentification DRF (browsable API)
    path('auth/', include('rest_framework.urls')),
]






