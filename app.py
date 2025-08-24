import json
import streamlit as st
import pandas as pd
from storage import init_db, add_client, update_client, fetch_clients, get_client, add_xpath, list_xpaths
from scrapers import scrape_fields, normalize

st.set_page_config(page_title="Listings Consistency Agent", layout="wide")

@st.cache_data
def load_default_xpaths():
    with open("default_xpaths.json","r") as f:
        return json.load(f)

DEFAULT_XPATHS = load_default_xpaths()
SITES = ["google", "apple", "bing", "yelp", "yahoo"]
FIELDS = ["entity_name","address","phone","website_link_anchor","hours"]

def site_label(s):
    return {"google":"Google Business Profile","apple":"Apple Maps","bing":"Bing Maps","yelp":"Yelp","yahoo":"Yahoo Local"}.get(s, s)

init_db()

st.title("Listings Consistency Agent")
st.caption("XPath-only scraping. Compare to SSOT and flag mismatches.")

tabs = st.tabs(["📊 Dashboard","👥 Client Manager","🧭 XPath Manager & Tester","ℹ️ Help"])

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

        ssot = {"entity_name": client["ssot_name"] or "","address": client["ssot_address"] or "","phone": client["ssot_phone"] or "",
                "website_url": client["ssot_website_url"] or "","website_anchor": client["ssot_website_anchor"] or "","hours": client["ssot_hours"] or ""}

        st.markdown("**SSOT (Single Source of Truth)**")
        st.write(ssot)

        urls = {"google": client["url_google"], "apple": client["url_apple"], "bing": client["url_bing"], "yelp": client["url_yelp"], "yahoo": client["url_yahoo"]}

        if st.button("Scan all 5 listings now"):
            rows = []
            for site, url in urls.items():
                if not url:
                    rows.append({"Site": site_label(site),"URL": "","Entity Name": "","Address": "","Phone": "","Website URL": "","Website Anchor": "","Hours": "","Match (overall)": False,"Notes": "No URL provided"})
                    continue
                try:
                    site_xp = DEFAULT_XPATHS.get(site, {})
                    data = scrape_fields(site, url, site_xp)
                    matches = {}
                    for fld, ssot_val in ssot.items():
                        norm_scraped = normalize(fld, data.get(fld,""))
                        norm_ssot = normalize(fld, ssot_val)
                        matches[fld] = (norm_scraped == norm_ssot) if (norm_scraped or norm_ssot) else True
                    overall = all(matches.values()) if any((data.get(k) for k in data)) else False
                    rows.append({"Site": site_label(site),"URL": url,"Entity Name": data.get("entity_name",""),"Address": data.get("address",""),
                                 "Phone": data.get("phone",""),"Website URL": data.get("website_url",""),"Website Anchor": data.get("website_anchor",""),
                                 "Hours": data.get("hours",""),"Match (overall)": overall,"Notes": "; ".join([k for k,v in matches.items() if not v]) if not overall else ""})
                except Exception as e:
                    rows.append({"Site": site_label(site),"URL": url,"Entity Name": "","Address": "","Phone": "","Website URL": "","Website Anchor": "","Hours": "",
                                 "Match (overall)": False,"Notes": f"Error: {e}"})
            df = pd.DataFrame(rows, columns=["Site","URL","Entity Name","Address","Phone","Website URL","Website Anchor","Hours","Match (overall)","Notes"])
            st.dataframe(df, use_container_width=True)
            st.download_button("Download results as CSV", data=df.to_csv(index=False), file_name=f"consistency_{client['name']}.csv", mime="text/csv")

with tabs[1]:
    st.subheader("Add / Edit Clients & SSOT")
    with st.form("new_client"):
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
                from storage import add_client
                cid = add_client({"name": name,"ssot_name": ssot_name,"ssot_address": ssot_address,"ssot_phone": ssot_phone,
                                  "ssot_website_url": ssot_website_url,"ssot_website_anchor": ssot_website_anchor,"ssot_hours": ssot_hours,
                                  "url_google": url_google,"url_apple": url_apple,"url_bing": url_bing,"url_yelp": url_yelp,"url_yahoo": url_yahoo})
                st.success(f"Client saved (id={cid}).")

    for c in fetch_clients():
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
                if st.form_submit_button("Update Client"):
                    update_client(c["id"], {"name": name,"ssot_name": ssot_name,"ssot_address": ssot_address,"ssot_phone": ssot_phone,
                                            "ssot_website_url": ssot_website_url,"ssot_website_anchor": ssot_website_anchor,"ssot_hours": ssot_hours,
                                            "url_google": url_google,"url_apple": url_apple,"url_bing": url_bing,"url_yelp": url_yelp,"url_yahoo": url_yahoo})
                    st.success("Client updated.")

with tabs[2]:
    st.subheader("Manage XPaths per Site & Field")
    st.caption("Store multiple XPaths per field. Yelp supports type1/type2 via a detector in default_xpaths.json.")
    with st.form("add_xpath_form"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: site = st.selectbox("Site", SITES, index=3)
        with c2: layout = st.selectbox("Layout (Yelp only)", ["", "type1", "type2"])
        with c3: field = st.selectbox("Field", FIELDS)
        with c4: priority = st.number_input("Priority", min_value=1, value=1, step=1)
        xpath_val = st.text_input("XPath", placeholder="//h1 | //a[contains(@href,'tel:')]")
        if st.form_submit_button("Add XPath"):
            if not xpath_val.strip():
                st.error("XPath cannot be empty.")
            else:
                add_xpath(site, field, xpath_val.strip(), layout if layout else None, int(priority), True)
                st.success("XPath added.")

    st.markdown("---")
    st.subheader("Test an XPath quickly")
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

with tabs[3]:
    st.subheader("How it works")
    st.markdown("""
- **Dashboard**: scan each listing URL with XPaths and compare to SSOT. 
- **Client Manager**: store SSOT + URLs.
- **XPath Manager**: save multiple XPaths per field + test ad-hoc XPaths.
- **Yelp layouts**: detector chooses `type1` or `type2` automatically.
- **Link+Anchor**: one XPath extracting an `<a>` returns both `href` and anchor text.
    """)
