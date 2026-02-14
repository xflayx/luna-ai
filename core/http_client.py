import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _build_session() -> requests.Session:
    total = int(os.getenv("LUNA_HTTP_RETRY_TOTAL", "3"))
    backoff = float(os.getenv("LUNA_HTTP_RETRY_BACKOFF", "0.3"))
    status_list = os.getenv("LUNA_HTTP_RETRY_STATUS", "429,500,502,503,504")
    status_codes = [int(s.strip()) for s in status_list.split(",") if s.strip().isdigit()]

    retry = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=status_codes,
        allowed_methods=("GET", "POST", "PUT", "DELETE", "PATCH"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=20,
    )

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


SESSION = _build_session()
