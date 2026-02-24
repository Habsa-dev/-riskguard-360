"""
WSGI config for RiskGuard 360 project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskguard.settings')
application = get_wsgi_application()






