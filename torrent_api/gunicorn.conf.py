"""
Gunicorn configuration for the TORR API service.
Use with:
  gunicorn -c gunicorn.conf.py wsgi:app
"""

import os

# Workers and class
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
worker_class = "gevent"

# Timeouts and keepalive
timeout = int(os.getenv("GUNICORN_TIMEOUT", "30"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Request recycling to mitigate memory leaks under gevent
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", "100"))

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
capture_output = True

# Proxy / reverse proxy headers
forwarded_allow_ips = "*"
# bind should be set via CLI/env to work with Docker port mapping:
# e.g., gunicorn -c gunicorn.conf.py --bind 0.0.0.0:${TORR_API_PORT:-9092} wsgi:app

# Preload app (disabled to avoid scheduler duplication)
preload_app = False

# Worker connections (used by some async workers; gevent tolerates this setting)
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))
# Graceful shutdown and lifecycle hooks
def on_starting(server):
    server.log.info("Gunicorn server starting")


def when_ready(server):
    server.log.info("Gunicorn server ready; workers spawning")


def worker_int(worker):
    # Called when a worker gets INT or QUIT signal
    worker.log.info("Gunicorn worker received INT/QUIT signal pid=%s", worker.pid)


def worker_exit(server, worker):
    # Called just after a worker has been exited, to perform any cleanup
    worker.log.info("Gunicorn worker exiting pid=%s", worker.pid)
    # If you have persistent resources to close from utils (DB pools, clients), do it here.


def pre_request(worker, req):
    # Per-request hook
    worker.log.debug("pre_request %s %s", req.method, req.path)


def post_request(worker, req, environ, resp):
    # Per-request completion hook
    worker.log.debug("post_request status=%s", getattr(resp, "status", "unknown"))