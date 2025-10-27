"""
Gunicorn WSGI entrypoint.

Run with:
  gunicorn -c gunicorn.conf.py wsgi:app
"""

from app import create_app

app = create_app()