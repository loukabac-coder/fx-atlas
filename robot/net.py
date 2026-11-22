"""Téléchargement HTTP avec nouvelles tentatives et délai maximal."""
import time

import requests

UA = "fx-atlas-robot/1.0 (+https://github.com/loukabac-coder/fx-atlas)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class FetchError(Exception):
    pass


def get(url, *, params=None, timeout=40, tries=3, browser=False, headers=None):
    h = {"User-Agent": BROWSER_UA if browser else UA,
         "Accept-Language": "en-US,en;q=0.8"}
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=h, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code in (400, 401, 403, 404):
                break  # inutile de réessayer
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (i + 1))
    raise FetchError(f"{url} -> {last}")
