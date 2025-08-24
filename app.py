import json
import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
from storage import init_db, add_client, update_client, fetch_clients, get_client, delete_client, add_xpath, list_xpaths, toggle_xpath_active, delete_xpath
from scrapers import scrape_fields, normalize

st.set_page_config(page_title="Listings Consistency Agent", layout="wide")

@st.cache_data
def load_default_xpaths() -> Dict:
    with open("default_xpaths.json","r") as f:
        return json.load(f)

DEFAULT_XPATHS = load_default_xpaths()

SITES = ["google", "apple", "bing", "yelp", "yahoo"]
FIELDS = ["entity_name","address","phone","website_link_anchor","hours"]

def site_label(s: str) -> str:
    return {
        "google":"Google Business Profile",
        "apple":"Apple Maps",
        "bing":"Bing Maps",
        "yelp":"Yelp",
        "yahoo":"Yahoo Local"
    }.get(s, s)

def init():
    init_db()

init()

st.title("Listings Consistency Agent")
st.caption("Scrape live listing pages with XPaths (no schema), compare to SSOT, and highlight discrepancies.")

tabs = st.tabs(["📊 Dashboard","👥 Client Manager","🧭 XPath Manager & Tester","ℹ️ Help"])

# ----------------- Dashboard -----------------
with tabs[0]:
    st.subheader("Client Snapshot & Consistency Check")
    clients = fetch_clients()
    if not clients:
        st.info("No clients yet. Add one in the Client Manager tab.")
    else:
        options = {f"[{c['id']}] {c['name']}": c["id"] for c in clients}
        selected = st.selectbox("Select client", list(options.keys()))
        client_id = options[selected]
        client = get_client(client_id)
        assert client is not None

        ssot = {
            "entity_name": client["ssot_name"] or "",
            "address": client["ssot_address"] or "",
            "phone": client["ssot_phone"] or "",
            "website_url": client["ssot_website_url"] or "",
            "website_anchor": client["ssot_website_anchor"] or "",
            "hours": client["ssot_hours"] or ""
        }

        st.markdown("**SSOT (Single Source of Truth)**")
        st.write(ssot)

        urls = {
            "google": client["url_google"],
            "apple": client["url_apple"],
            "bing": client["url_bing"],
            "yelp": client["url_yelp"],
            "yahoo": client["url_yahoo"]
        }

        run = st.button("Scan all 5 listings now")
        if run:
            rows = []
            for site, url in urls.items():
                if not url:
                    rows.append({
                        "Site": site_label(site),
                        "URL": "",
                        "Entity Name": "",
                        "Address": "",
                        "Phone": "",
                        "Website URL": "",
                        "Website Anchor": "",
                        "Hours": "",
                        "Match (overall)": False,
                        "Notes": "No URL provided"
                    })
                    continue
                try:
                    site_xp = DEFAULT_XPATHS.get(site, {})
                    data = scrape_fields(site, url, site_xp)
                    # Normalize for comparison
                    matches = {}
                    for fld, ssot_val in ssot.items():
                        norm_scraped = normalize(fld.replace("website_url","website_url"), data.get(fld,""))
                        norm_ssot = normalize(fld, ssot_val)
                        matches[fld] = (norm_scraped == norm_ssot) if (norm_scraped or norm_ssot) else True
                    overall = all(matches.values()) if any((data.get(k) for k in data)) else False

                    rows.append({
                        "Site": site_label(site),
                        "URL": url,
                        "Entity Name": data.get("entity_name",""),
                        "Address": data.get("address",""),
                        "Phone": data.get("phone",""),
                        "Website URL": data.get("website_url",""),
                        "Website Anchor": data.get("website_anchor",""),
                        "Hours": data.get("hours",""),
                        "Match (overall)": overall,
                        "Notes": "; ".join([k for k,v in matches.items() if not v]) if not overall else ""
                    })
                except Exception as e:
                    rows.append({
                        "Site": site_label(site),
                        "URL": url,
                        "Entity Name": "",
                        "Address": "",
                        "Phone": "",
                        "Website URL": "",
                        "Website Anchor": "",
                        "Hours": "",
                        "Match (overall)": False,
                        "Notes": f"Error: {e}"
                    })

            df = pd.DataFrame(rows, columns=["Site","URL","Entity Name","Address","Phone","Website URL","Website Anchor","Hours","Match (overall)","Notes"])
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download results as CSV", data=csv, file_name=f"consistency_{client['name']}.csv", mime="text/csv")

# ----------------- Client Manager -----------------
with tabs[1]:
    st.subheader("Add / Edit Clients & SSOT")
    with st.form("new_client"):
        st.markdown("**Add a new client**")
        name = st.text_input("Client Name*", placeholder="Acme Dermatology – Encinitas")
        col1, col2 = st.columns(2)
        with col1:
            ssot_name = st.text_input("SSOT: Entity Name")
            ssot_address = st.text_area("SSOT: Address")
            ssot_phone = st.text_input("SSOT: Phone")
        with col2:
            ssot_website_url = st.text_input("SSOT: Website URL")
            ssot_website_anchor = st.text_input("SSOT: Website Anchor Text")
            ssot_hours = st.text_area("SSOT: Hours (text)")
        st.markdown("**Listing URLs**")
        c1, c2, c3 = st.columns(3)
        with c1:
            url_google = st.text_input("Google Business Profile URL")
            url_bing = st.text_input("Bing Maps URL")
        with c2:
            url_yelp = st.text_input("Yelp URL")
            url_yahoo = st.text_input("Yahoo Local URL")
        with c3:
            url_apple = st.text_input("Apple Maps URL")
        submitted = st.form_submit_button("Save Client")
        if submitted:
            if not name:
                st.error("Client Name is required.")
            else:
                cid = add_client({
                    "name": name,
                    "ssot_name": ssot_name,
                    "ssot_address": ssot_address,
                    "ssot_phone": ssot_phone,
                    "ssot_website_url": ssot_website_url,
                    "ssot_website_anchor": ssot_website_anchor,
                    "ssot_hours": ssot_hours,
                    "url_google": url_google,
                    "url_apple": url_apple,
                    "url_bing": url_bing,
                    "url_yelp": url_yelp,
                    "url_yahoo": url_yahoo
                })
                st.success(f"Client saved (id={cid}). Refresh the Dashboard to scan.")

    if clients:
        st.markdown("---")
        st.markdown("**Existing Clients**")
        for c in clients:
            with st.expander(f"[{c['id']}] {c['name']}"):
                with st.form(f"edit_{c['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        name = st.text_input("Client Name*", value=c["name"])
                        ssot_name = st.text_input("SSOT: Entity Name", value=c["ssot_name"] or "")
                        ssot_address = st.text_area("SSOT: Address", value=c["ssot_address"] or "")
                        ssot_phone = st.text_input("SSOT: Phone", value=c["ssot_phone"] or "")
                    with col2:
                        ssot_website_url = st.text_input("SSOT: Website URL", value=c["ssot_website_url"] or "")
                        ssot_website_anchor = st.text_input("SSOT: Website Anchor Text", value=c["ssot_website_anchor"] or "")
                        ssot_hours = st.text_area("SSOT: Hours", value=c["ssot_hours"] or "")

                    st.markdown("**Listing URLs**")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        url_google = st.text_input("Google Business Profile URL", value=c["url_google"] or "")
                        url_bing   = st.text_input("Bing Maps URL", value=c["url_bing"] or "")
                    with c2:
                        url_yelp   = st.text_input("Yelp URL", value=c["url_yelp"] or "")
                        url_yahoo  = st.text_input("Yahoo Local URL", value=c["url_yahoo"] or "")
                    with c3:
                        url_apple  = st.text_input("Apple Maps URL", value=c["url_apple"] or "")

                    save = st.form_submit_button("Update Client")
                    if save:
                        update_client(c["id"], {
                            "name": name,
                            "ssot_name": ssot_name,
                            "ssot_address": ssot_address,
                            "ssot_phone": ssot_phone,
                            "ssot_website_url": ssot_website_url,
                            "ssot_website_anchor": ssot_website_anchor,
                            "ssot_hours": ssot_hours,
                            "url_google": url_google,
                            "url_apple": url_apple,
                            "url_bing": url_bing,
                            "url_yelp": url_yelp,
                            "url_yahoo": url_yahoo
                        })
                        st.success("Client updated.")

# ----------------- XPath Manager & Tester -----------------
with tabs[2]:
    st.subheader("Manage XPaths per Site & Field")
    st.markdown("You can store multiple XPaths per field with priorities (lower = tried first). Yelp supports two layouts (`type1` / `type2`).")

    with st.form("add_xpath_form"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            site = st.selectbox("Site", SITES, index=3)  # default Yelp
        with c2:
            layout = st.selectbox("Layout (Yelp only)", ["", "type1", "type2"])
        with c3:
            field = st.selectbox("Field", FIELDS)
        with c4:
            priority = st.number_input("Priority", min_value=1, value=1, step=1)
        xpath_val = st.text_input("XPath", placeholder="//h1 | //a[contains(@href,'tel:')]")
        add_btn = st.form_submit_button("Add XPath")
        if add_btn:
            if not xpath_val.strip():
                st.error("XPath cannot be empty.")
            else:
                add_xpath(site, field, xpath_val.strip(), layout if layout else None, int(priority), True)
                st.success("XPath added.")

    st.markdown("---")
    st.markdown("**Current XPaths**")
    for s in SITES:
        xrows = list_xpaths(site=s)
        if not xrows and s != "yelp":
            continue
        with st.expander(f"{site_label(s)}"):
            if s == "yelp":
                st.caption("Detector XPath is set in default_xpaths.json. You may override name/address/phone/website/hours via entries below.")
            if xrows:
                df = pd.DataFrame([{**dict(r)} for r in xrows])
                st.dataframe(df, use_container_width=True)
            else:
                st.write("No custom XPaths stored for this site yet.")

    st.markdown("---")
    st.subheader("Test an XPath quickly (no save)")
    test_url = st.text_input("Test URL")
    test_site = st.selectbox("Test Site", SITES, index=3, key="t_site")
    test_xpath = st.text_input("XPath to run on the URL", key="t_xp")
    if st.button("Run Test"):
        if not (test_url and test_xpath):
            st.error("Provide both a URL and an XPath.")
        else:
            from lxml import html
            from scrapers import fetch, extract_with_xpath, canonicalize_site_href
            try:
                html_text = fetch(test_url)
                doc = html.fromstring(html_text)
                txt, href = extract_with_xpath(doc, test_xpath)
                href = canonicalize_site_href(test_site, href)
                st.write({"text": txt, "href": href})
            except Exception as e:
                st.error(f"Error: {e}")

# ----------------- Help -----------------
with tabs[3]:
    st.subheader("How it works")
    st.markdown("""
    **Core idea:** this tool fetches the live HTML of each listing URL and extracts fields using **XPaths you configure**, not schema.
    - **Dashboard**: pick a client, click *Scan*, and you’ll see the scraped values per site vs your SSOT (Single Source of Truth). The **Match** column flags discrepancies.
    - **Client Manager**: add/edit clients, store SSOT values and the 5 listing URLs.
    - **XPath Manager & Tester**: add multiple XPaths per field and site (with priorities), and try ad‑hoc XPaths against a URL.
    - **Yelp layouts**: a detector XPath picks layout `type1` or `type2` automatically. You can customize the field XPaths per layout.
    - **Website link + anchor**: supply one XPath that returns an `<a>` element (or an element containing one). The app will extract both link `href` and visible anchor text.
    
    **Notes & Tips**
    - Page structures change often. Keep your XPaths robust and store backups with lower priority.
    - Some sites are highly dynamic and may require a headless browser for reliability. If a page renders empty HTML, consider fetching via Playwright in your environment.
    - Respect each website’s Terms of Service and robots.txt, and throttle your scans.
    """)
