Deployment and healthcheck for TORR API

Overview
- Production entrypoint is Gunicorn serving the Falcon app [create_app()](app.py:173) via [wsgi:app](wsgi.py:1). The Dockerfile [Dockerfile_torrapi](../Dockerfile_torrapi) now sets this as the default ENTRYPOINT.
- Health endpoint [HealthResource.on_get()](app.py:86) returns 200 when DB and Transmission RPC are reachable, 503 otherwise.
- Request handler [TORRAPI.on_get()](torr_service_utils.py:32) is hardened with validation, correlation IDs, and latency logging.

Run command (inside container)
- gunicorn -c gunicorn.conf.py --bind 0.0.0.0:${TORR_API_PORT:-9092} wsgi:app (default via [Dockerfile_torrapi](../Dockerfile_torrapi))

Environment variables
- TORR_API_PORT: port to bind (default 9092)
- TORR_API_PATH: base path for routes (default /torr-api)
- TRANSMISSION_HOST, TRANSMISSION_PORT, TRANSMISSION_USER, TRANSMISSION_PASSWORD, TRANSMISSION_SCHEME: Transmission RPC config
- ENABLE_HEARTBEAT: set to 1 to enable internal heartbeat that pings /torr-api/health every HEARTBEAT_INTERVAL_MIN minutes (default 5)
- HEARTBEAT_INTERVAL_MIN: heartbeat interval in minutes

Docker Compose service snippet (example)

version: "3.8"
services:
  torr_api:
    build: .
    image: torr_api:latest
    ports:
      - "9092:9092"
    environment:
      TORR_API_PORT: 9092
      TORR_API_PATH: /torr-api
      TRANSMISSION_HOST: transmission
      TRANSMISSION_PORT: 9091
      TRANSMISSION_USER: ""
      TRANSMISSION_PASSWORD: ""
      ENABLE_HEARTBEAT: "1"
      HEARTBEAT_INTERVAL_MIN: "5"
    # command override not required; Dockerfile ENTRYPOINT already runs Gunicorn
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:9092/torr-api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    restart: unless-stopped
    depends_on:
      - transmission
      - db

Logging
- Access and error logs are emitted by Gunicorn as configured in [gunicorn.conf.py](gunicorn.conf.py:1). App-level logs include request IDs and response times via middleware.

Notes
- The service is designed to tolerate intermittent network issues under load by using 4 gevent workers and aggressive timeouts; adjust worker count to match CPU/IO profile.
- Healthcheck is suitable for Kubernetes/Docker restart policies; it reflects dependencies status (DB and Transmission). Ensure compose wait-for dependencies or start_period is sufficient.
- For local debugging, you can still run the dev server in [server.py](server.py:1) or [app.py](app.py:122), but production should use Gunicorn.
- If APScheduler heartbeat is enabled, duplication is mitigated by a sentinel lock file; it is optional when Docker healthchecks are present.