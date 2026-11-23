"""Téléchargement HTTP avec nouvelles tentatives et délai maximal TOTAL par requête
(un serveur qui envoie les octets au compte-gouttes ne peut pas bloquer le robot)."""
import time

import requests

UA = "fx-atlas-robot/1.0 (+https://github.com/loukabac-coder/fx-atlas)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MAX_BYTES = 15_000_000


class FetchError(Exception):
    pass


class Resp:
    def __init__(self, r, content):
        self.status_code = r.status_code
        self.headers = r.headers
        self.url = r.url
        self.content = content
        self.encoding = r.encoding or "utf-8"

    @property
    def text(self):
        try:
            return self.content.decode(self.encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self):
        import json
        return json.loads(self.content.decode("utf-8", errors="replace"))


def _once(url, params, headers, timeout):
    deadline = time.monotonic() + timeout
    with requests.get(url, params=params, headers=headers, timeout=(10, 20), stream=True) as r:
        chunks, size = [], 0
        for ch in r.iter_content(65536):
            chunks.append(ch)
            size += len(ch)
            if time.monotonic() > deadline:
                raise requests.Timeout(f"délai total de {timeout}s dépassé")
            if size > MAX_BYTES:
                raise requests.RequestException("réponse trop volumineuse")
        return Resp(r, b"".join(chunks))


def get(url, *, params=None, timeout=45, tries=3, browser=False, headers=None):
    h = {"User-Agent": BROWSER_UA if browser else UA,
         "Accept-Language": "en-US,en;q=0.8"}
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            r = _once(url, params, h, timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code in (400, 401, 403, 404, 410):
                break
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {str(e)[:150]}"
        if i < tries - 1:
            time.sleep(2 * (i + 1))
    raise FetchError(f"{url} -> {last}")
