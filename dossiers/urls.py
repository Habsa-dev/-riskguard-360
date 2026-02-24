"""
RiskGuard 360 - URLs de l'application dossiers
"""

from django.urls import path
from . import views

urlpatterns = [
    # Landing page
    path('', views.landing_page, name='accueil'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('quick-login/<str:role>/', views.quick_login, name='quick_login'),

    # Clients
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/nouveau/', views.creer_client, name='creer_client'),
    path('clients/<uuid:pk>/', views.detail_client, name='detail_client'),
    path('clients/<uuid:pk>/modifier/', views.modifier_client, name='modifier_client'),

    # Dossiers de prêt
    path('dossiers/', views.liste_dossiers, name='liste_dossiers'),
    path('dossiers/nouveau/', views.creer_dossier, name='creer_dossier'),
    path('dossiers/<uuid:pk>/', views.detail_dossier, name='detail_dossier'),
    path('dossiers/<uuid:pk>/calculer-score/', views.calculer_score_view, name='calculer_score'),
    path('dossiers/<uuid:pk>/changer-etat/', views.changer_etat_view, name='changer_etat'),
    path('dossiers/<uuid:pk>/upload-piece/', views.upload_piece, name='upload_piece'),
    path('dossiers/<uuid:pk>/rapport-pdf/', views.generer_pdf_view, name='generer_pdf'),

    # Simulation
    path('simulation/', views.simulation_pret, name='simulation_pret'),

    # Export
    path('export/excel/', views.export_excel, name='export_excel'),

    # Notifications
    path('notifications/', views.liste_notifications, name='liste_notifications'),
    path('notifications/<uuid:pk>/lue/', views.marquer_notification_lue, name='marquer_notification_lue'),

    # Audit
    path('audit/', views.liste_audits, name='liste_audits'),

    # API JSON
    path('api/dashboard/', views.api_dashboard_data, name='api_dashboard'),
]
