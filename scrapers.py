import re
import httpx
from typing import Dict
from lxml import html
from urllib.parse import unquote, parse_qs, urlparse
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

def extract_with_xpath(doc: html.HtmlElement, xpath_expr: str):
    try:
        nodes = doc.xpath(xpath_expr)
    except Exception:
        return ("", None)
    n = nodes[0] if nodes else None
    if n is None:
        return ("", None)
    if hasattr(n, "tag"):
        if getattr(n, "tag", "").lower() == "a":
            return (_textify(n), n.get("href"))
        anchors = n.xpath(".//a")
        if anchors:
            a = anchors[0]
            return (_textify(a), a.get("href"))
        return (_textify(n), None)
    return (_textify(n), None)

def canonicalize_site_href(site: str, href: str):
    if not href:
        return None
    try:
        if site == "yelp" and "biz_redir" in href:
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
        try:
            p = urlparse(s)
            netloc = p.netloc.lower()
            path = p.path.rstrip("/")
            return f"{p.scheme}://{netloc}{path}" if p.scheme else f"https://{netloc}{path}"
        except Exception:
            return s.strip().lower()
    return s

def scrape_fields(site: str, url: str, xpaths_for_site: Dict) -> Dict[str, str]:
    html_text = fetch(url)
    doc = html.fromstring(html_text)

    if site == "yelp":
        detector = xpaths_for_site.get("detector_xpath")
        if detector:
            txt, _ = extract_with_xpath(doc, detector)
            layout = "type1" if (txt or _) else "type2"
        else:
            layout = "type1"
        site_xp = xpaths_for_site.get(layout, {})
    else:
        site_xp = xpaths_for_site

    results = {"entity_name":"", "address":"", "phone":"", "website_url":"", "website_anchor":"", "hours":""}

    def pull(key: str):
        xp = site_xp.get(key)
        if not xp:
            return ("", None)
        return extract_with_xpath(doc, xp)

    txt, _ = pull("entity_name"); results["entity_name"] = txt
    txt, _ = pull("address"); results["address"] = txt
    txt, href = pull("phone")
    results["phone"] = href.replace("tel:", "") if (href and href.startswith("tel:")) else txt
    txt, href = pull("website_link_anchor")
    href = canonicalize_site_href(site, href)
    results["website_anchor"] = txt
    results["website_url"] = href or ""
    txt, _ = pull("hours"); results["hours"] = txt
    return results
