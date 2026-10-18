from urllib.parse import urlparse, urlunparse

def normalize_url(url: str) -> str:
    url = (url or "").strip()

    p = urlparse(url)
    # enlève query + fragment (utm, etc.)
    p = p._replace(query="", fragment="")

    clean = urlunparse(p)
    # enlève slash final (sauf si juste domaine)
    if clean.endswith("/") and p.path not in ("", "/"):
        clean = clean.rstrip("/")

    return clean

# ---------------------------------------------------------------------------
# Récupération « au mieux » du titre et de l'image d'un lien (balises Open Graph)
# ---------------------------------------------------------------------------
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen


def _is_public_host(host: str) -> bool:
    """Refuse les adresses locales/privées (évite qu'on fasse requêter le serveur sur son réseau interne)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


class _OGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        a = dict(attrs)
        key = a.get("property") or a.get("name")
        if key and a.get("content") and key not in self.meta:
            self.meta[key] = a["content"]


def fetch_page_meta(url: str, timeout: float = 4.0) -> dict:
    """
    Renvoie {"title": ..., "image": ...} si la page les expose, sinon {}.
    Ne lève jamais d'exception : Instagram bloque souvent ces requêtes, c'est normal.
    """
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname or not _is_public_host(p.hostname):
            return {}
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; YannickSiteBot/1.0)"})
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 (schéma vérifié ci-dessus)
            if "html" not in (resp.headers.get("Content-Type") or ""):
                return {}
            html = resp.read(300_000).decode("utf-8", errors="ignore")
        parser = _OGParser()
        parser.feed(html)
        title = (parser.meta.get("og:title") or "").strip()[:255]
        image = (parser.meta.get("og:image") or "").strip()
        if not image.startswith("https://"):
            image = ""
        return {"title": title, "image": image[:200]}
    except (URLError, OSError, ValueError):
        return {}
