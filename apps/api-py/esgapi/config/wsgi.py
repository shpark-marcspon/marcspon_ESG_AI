"""gunicorn 이 부르는 입구:  gunicorn esgapi.config.wsgi:application"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "esgapi.config.settings.base")
application = get_wsgi_application()
