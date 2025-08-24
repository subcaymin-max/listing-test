import re
import httpx
from typing import Dict, List, Optional, Tuple
from lxml import html
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

class FetchError(Exception):
    pass

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4),
       retry=retry_if_exception_type(FetchError))
def fetch(url: str, timeout: int = 20) -> str:
    try:
        with httpx.Client(follow_redirects=True, headers=HEADERS, timeout=timeout) as client:
            r = client.get(url)
            if r.status_code >= 400:
                raise FetchError(f"HTTP {r.status_code}")
            return r.text
    except httpx.HTTPError as e:
        raise FetchError(str(e))

def _textify(el) -> str:
    if el is None:
        return ""
    if isinstance(el, str):
        return " ".join(el.split())
    return " ".join(el.text_content().split())

def _first(items: List) -> Optional:
    return items[0] if items else None

def extract_with_xpath(doc: html.HtmlElement, xpath_expr: str) -> Tuple[str, Optional[str]]:
    """
    Returns (text, href) for the FIRST matching node.
    If the node is an <a>, extract both its text and href.
    If the node contains a descendant <a>, take the first descendant <a>.
    Else, return node's text and None for href.
    """
    try:
        nodes = doc.xpath(xpath_expr)
    except Exception:
        return ("", None)

    n = _first(nodes)
    if n is None:
        return ("", None)

    if hasattr(n, "tag"):  # element
        # If it's an anchor
        if getattr(n, "tag", "").lower() == "a":
            txt = _textify(n)
            href = n.get("href")
            return (txt, href)
        # Else if it has a descendant anchor
        anchors = n.xpath(".//a")
        if anchors:
            a = anchors[0]
            return (_textify(a), a.get("href"))
        # Else just text
        return (_textify(n), None)
    else:
        # It's likely an attribute or string result
        return (_textify(n), None)

def canonicalize_site_href(site: str, href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    try:
        if site == "yelp" and "biz_redir" in href:
            # Yelp wraps external links via biz_redir; extract true 'url=' param
            q = parse_qs(urlparse(href).query)
            target = q.get("url", [None])[0]
            if target:
                return unquote(target)
        return href
    except Exception:
        return href

def normalize(field: str, value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if field == "phone":
        digits = re.sub(r"\D+", "", s)
        return digits[-10:] if len(digits) >= 10 else digits
    if field in ("entity_name", "address", "hours", "website_anchor"):
        return re.sub(r"\s+", " ", s).strip().upper()
    if field == "website_url":
        # strip tracking params, lowercase host, no trailing slash
        try:
            p = urlparse(s)
            netloc = p.netloc.lower()
            path = p.path.rstrip("/")
            return f"{p.scheme}://{netloc}{path}" if p.scheme else f"https://{netloc}{path}"
        except Exception:
            return s.strip().lower()
    return s

def scrape_fields(site: str, url: str, xpaths_for_site: Dict) -> Dict[str, str]:
    """Given a site key and URL and a dict of XPaths, fetch and extract fields."""
    html_text = fetch(url)
    doc = html.fromstring(html_text)

    # Yelp special-case for two layouts
    layout = None
    if site == "yelp":
        detector = xpaths_for_site.get("detector_xpath")
        if detector:
            txt, _ = extract_with_xpath(doc, detector)
            layout = "type1" if txt or _ else "type2"
        else:
            layout = "type1"
        site_xp = xpaths_for_site.get(layout, {})
    else:
        site_xp = xpaths_for_site

    results = {
        "entity_name": "",
        "address": "",
        "phone": "",
        "website_url": "",
        "website_anchor": "",
        "hours": ""
    }

    # Helper to get text/href by field key
    def pull(field_key: str):
        xp = site_xp.get(field_key) if site != "yelp" else site_xp.get(field_key)
        if not xp:
            return ("", None)
        return extract_with_xpath(doc, xp)

    # Name
    txt, _ = pull("entity_name"); results["entity_name"] = txt
    # Address
    txt, _ = pull("address"); results["address"] = txt
    # Phone (allow tel: href or visible)
    txt, href = pull("phone")
    if href and href.startswith("tel:"):
        results["phone"] = href.replace("tel:", "")
    else:
        results["phone"] = txt
    # Website
    txt, href = pull("website_link_anchor")
    href = canonicalize_site_href(site, href)
    results["website_anchor"] = txt
    results["website_url"] = href or ""
    # Hours
    txt, _ = pull("hours"); results["hours"] = txt

    return results
