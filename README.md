# RiskGuard 360

Plateforme Django d'analyse de risque client pour micro-finance: scoring, détection de fraude, workflow de dossier, dashboard, API REST et gestion des rôles (RBAC).

## Fonctionnalités

- Scoring risque (endettement, historique, stabilité, cohérence).
- Détection de fraude avancée + alertes.
- Workflow dossier: `soumis -> en_analyse -> valide/refuse/alerte_fraude`.
- Dashboard KPI + graphiques (Chart.js).
- Génération de rapport PDF.
- Export Excel des dossiers.
- API REST (DRF) pour clients, dossiers, scoring, simulation.
- RBAC 4 acteurs: Conseiller, Gestionnaire, Manager Risque, Administrateur.
- Permissions objet avec Django Guardian.

## Stack technique

- Python 3.x
- Django 4.2
- Django REST Framework
- django-guardian
- reportlab
- openpyxl
- qrcode

## Installation locale

```bash
# 1) Cloner
git clone https://github.com/Habsa-dev/-riskguard-360.git
cd -riskguard-360

# 2) Environnement virtuel
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# 3) Dépendances
pip install -r requirements.txt

# 4) Migrations
python manage.py migrate

# 5) Données de démo (utilisateurs, rôles, dossiers)
python setup_demo.py

# 6) Lancer le serveur
python manage.py runserver
```

Application: `http://127.0.0.1:8000/`

## Comptes de démo

- Admin: `admin / admin123`
- Conseiller: `conseiller1 / conseiller123`
- Gestionnaire: `gestionnaire1 / gestionnaire123`
- Manager Risque: `manager1 / manager123`

## RBAC (résumé)

- **Conseiller Clientèle**
  - Créer clients/dossiers, upload pièces, voir ses dossiers.
  - Modification dossier autorisée seulement à l'état `soumis`.
- **Gestionnaire de Compte**
  - Voir dossiers de son portefeuille client.
  - Mettre à jour données financières/bancaires.
- **Manager Risque**
  - Voir tous les dossiers.
  - Valider/refuser/changer état.
  - Consulter alertes fraude et logs d'audit.
- **Administrateur**
  - Accès complet + gestion utilisateurs/rôles/configuration.

## API REST

Base URL: `http://127.0.0.1:8000/api/`

Exemples:

- `GET /api/clients/`
- `GET /api/dossiers/`
- `POST /api/score/`
- `POST /api/simulation/`
- `GET /api/portfolio-risk/`

## Structure projet

```text
projet6/
├─ dossiers/            # app Django principale (models, views, services, API)
├─ riskguard/           # settings, urls, wsgi
├─ scoring_engine/      # moteur de scoring Python
├─ templates/           # templates UI
├─ setup_demo.py        # seed data + groupes RBAC
└─ manage.py
```

## Notes

- Le fichier `db.sqlite3` est ignoré par Git.
- Le projet contient un mode de connexion rapide par rôle pour la démo.

