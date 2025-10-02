import os
import time
import uuid
from typing import Tuple, Dict, Any

import falcon

try:
    from transmission_rpc import Client as TransmissionClient  # transmission-rpc >= 3.3.0
except Exception:
    TransmissionClient = None

from utils import setup_logger, check_database
from torr_service_utils import TORRAPI


logger = setup_logger('TORR_API_APP')


class RequestContextMiddleware:
    def process_request(self, req: falcon.Request, resp: falcon.Response) -> None:
        rid = str(uuid.uuid4())
        req.context.request_id = rid
        req.context.start_time = time.time()

    def process_response(self, req: falcon.Request, resp: falcon.Response, resource: Any, req_succeeded: bool) -> None:
        rid = getattr(req.context, 'request_id', None)
        start = getattr(req.context, 'start_time', None)
        if rid:
            resp.set_header('X-Request-ID', rid)
        if start:
            latency_ms = int((time.time() - start) * 1000)
            resp.set_header('X-Response-Time-ms', str(latency_ms))
            path = req.path
            logger.info(f"[{rid}] {req.method} {path} {resp.status} {latency_ms}ms")


class HealthResource:
    def __init__(self) -> None:
        self.logger = logger

    @staticmethod
    def _transmission_check() -> Tuple[bool, Dict[str, Any]]:
        diag: Dict[str, Any] = {}
        if TransmissionClient is None:
            diag['available'] = False
            diag['error'] = 'transmission-rpc not installed'
            return False, diag
        # Resolve Transmission RPC connection details with broader env fallbacks
        host = (
            os.getenv('TRANSMISSION_HOST')
            or os.getenv('TR_HOST')
            or os.getenv('TORR_HOST')
            or 'localhost'
        )
        port = int(
            os.getenv('TRANSMISSION_PORT')
            or os.getenv('TR_PORT')
            or os.getenv('TORR_PORT')
            or '9091'
        )
        username = (
            os.getenv('TRANSMISSION_USER')
            or os.getenv('TR_USER')
            or os.getenv('TRANSMISSION_USERNAME')
            or os.getenv('TR_USERNAME')
            or ''
        )
        password = (
            os.getenv('TRANSMISSION_PASSWORD')
            or os.getenv('TR_PASSWORD')
            or os.getenv('TRANSMISSION_PASS')
            or os.getenv('TR_PASS')
            or ''
        )
        scheme = os.getenv('TRANSMISSION_SCHEME', 'http')

        # Include resolved context in diagnostics
        diag['host'] = host
        diag['port'] = port
        diag['scheme'] = scheme

        try:
            client = TransmissionClient(
                host=host,
                port=port,
                username=username or None,
                password=password or None,
                protocol=scheme
            )
            # session_get is lightweight
            session = client.get_session()
            diag['available'] = True
            diag['version'] = getattr(session, 'version', None)
            diag['rpc_version'] = getattr(session, 'rpc_version', None)
            return True, diag
        except Exception as e:
            diag['available'] = False
            diag['error'] = str(e)
            return False, diag

    @staticmethod
    def _db_check() -> Tuple[bool, Dict[str, Any]]:
        diag: Dict[str, Any] = {}
        try:
            # Assuming check_database raises or logs on failure; treat no-exception as OK
            check_database()
            diag['available'] = True
            return True, diag
        except Exception as e:
            diag['available'] = False
            diag['error'] = str(e)
            return False, diag

    def on_get(self, req: falcon.Request, resp: falcon.Response) -> None:
        rid = getattr(req.context, 'request_id', '')
        db_ok, db_diag = self._db_check()
        tr_ok, tr_diag = self._transmission_check()
        status_ok = db_ok and tr_ok
        resp.media = {
            'status': 'ok' if status_ok else 'degraded',
            'db': db_diag,
            'transmission': tr_diag,
            'request_id': rid,
        }
        resp.status = falcon.HTTP_200 if status_ok else falcon.HTTP_503
        self.logger.info(f"[{rid}] health db_ok={db_ok} tr_ok={tr_ok}")


def _resolve_base_path() -> str:
    path = os.getenv('TORR_API_PATH', '/torr-api')
    # Normalize to single segment without leading/trailing slashes
    base = path.strip('/')
    return base or 'torr-api'

# Optional heartbeat to self-ping /&lt;base&gt;/health, guarded via ENABLE_HEARTBEAT=1
def _maybe_start_heartbeat(base: str, port: int) -> None:
    """
    Start a background heartbeat that periodically pings /&lt;base&gt;/health.
    Duplication is mitigated using a /tmp lock sentinel so only one scheduler runs.
    Controlled by env:
      - ENABLE_HEARTBEAT=1 to enable
      - HEARTBEAT_INTERVAL_MIN (default 5)
    """
    if os.getenv('ENABLE_HEARTBEAT', '0') != '1':
        return

    sentinel = '/tmp/torr_api_heartbeat.lock'
    scheduler = None

    # Attempt to become heartbeat leader by creating a sentinel lock file
    try:
        fd = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        logger.info("Heartbeat already active (sentinel exists), skipping scheduler start")
        return
    except Exception as e:
        logger.error(f"Heartbeat lock acquisition failed: {e}")
        return

    try:
        # Lazy import to avoid hard dependency if not enabled
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
        import requests  # type: ignore

        interval_min = int(os.getenv('HEARTBEAT_INTERVAL_MIN', '5'))
        scheduler = BackgroundScheduler(daemon=True)

        def _ping():
            url = f"http://127.0.0.1:{port}/{base}/health"
            rid = str(uuid.uuid4())
            try:
                t0 = time.time()
                resp = requests.get(url, timeout=3)
                latency_ms = int((time.time() - t0) * 1000)
                logger.info(f"[{rid}] heartbeat GET {url} status={resp.status_code} {latency_ms}ms")
            except Exception as e:
                logger.error(f"[{rid}] heartbeat error GET {url}: {e}")

        scheduler.add_job(_ping, 'interval', minutes=interval_min, id='health_heartbeat', replace_existing=True)
        scheduler.start()
        logger.info(f"Heartbeat scheduler started: interval={interval_min}min target=/{base}/health")
    except Exception as e:
        logger.error(f"Heartbeat scheduler setup failed: {e}")
    finally:
        # Ensure sentinel cleanup on process exit
        def _cleanup():
            try:
                if scheduler:
                    scheduler.shutdown(wait=False)
            except Exception:
                pass
            try:
                os.remove(sentinel)
            except Exception:
                pass

        import atexit
        atexit.register(_cleanup)

def create_app() -> falcon.App:
    """
    Falcon application factory. Registers:
      - /<base>          -> TORRAPI
      - /<base>/health   -> HealthResource
    """
    app = falcon.App(middleware=[RequestContextMiddleware()])
    base = _resolve_base_path()
    app.add_route(f'/{base}', TORRAPI())
    app.add_route(f'/{base}/health', HealthResource())
    logger.info(f"Routes registered: /{base} and /{base}/health")
    _maybe_start_heartbeat(base, int(os.getenv('TORR_API_PORT', '9092')))
    return app


if __name__ == '__main__':
    # Local debug runner (not production). Use: python app.py
    from wsgiref.simple_server import make_server
    port = int(os.getenv('TORR_API_PORT', '9092'))
    app = create_app()
    logger.info(f"Debug server running on 0.0.0.0:{port}")
    with make_server('', port, app) as server:
        server.serve_forever()