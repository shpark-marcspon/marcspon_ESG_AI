#!/usr/bin/env python
"""Django 의 명령 입구.  예: python manage.py migrate / python manage.py export_openapi"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "esgapi.config.settings.base")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
