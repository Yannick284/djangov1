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