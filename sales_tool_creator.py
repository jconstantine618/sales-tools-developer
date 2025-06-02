import streamlit as st
from typing import Dict, List, Tuple
from openai import OpenAI
from docx import Document
from docx.shared import Pt
import requests, json, re, bs4
from urllib.parse import urljoin, urlparse

# ────────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ────────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="B2B Sales Playbook Builder", page_icon="📘", layout="wide"
)

# ────────────────────────────────────────────────────────────────────────────────
# OPENAI CLIENT (cached per session)
# ────────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def get_openai() -> OpenAI:
    return OpenAI(api_key=st.secrets["openai_api_key"])

client: OpenAI = get_openai()

# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

SECTION_TITLES: List[str] = [
    "Company Overview",
    "Value Propositions",
    "Customer Benefits",
    "Target Audience",
    "Needs Assessment Questions",
    "Demo Customer Personas",
    "Closing Questions",
    "Lead Generation Channels & Next Steps",
]

MAX_SITE_PAGES = 10  # safety‑limit for crawler
MAX_SITE_CHARS = 5000  # send a sane chunk to GPT

# ────────────────────────────────────────────────────────────────────────────────
# WEBSITE SCRAPER
# ────────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="🌐 Gathering website copy …")
def scrape_public_site(root_url: str, max_pages: int = MAX_SITE_PAGES) -> str:
    """Grab visible text from up to *max_pages* internal URLs (DFS crawl)."""

    domain = urlparse(root_url).netloc
    seen, to_visit = set(), [root_url]
    texts: List[str] = []

    while to_visit and len(seen) < max_pages:
        url = to_visit.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, timeout=6)
            if not r.ok or "text/html" not in r.headers.get("Content-Type", ""):
                continue
        except Exception:
            continue

        soup = bs4.BeautifulSoup(r.text, "html.parser")
        # Collect visible strings (skip <script>, <style>, etc.)
        for s in soup(["script", "style", "noscript"]):
            s.extract()
        page_text = " ".join(t.strip() for t in soup.stripped_strings)
        texts.append(page_text)

        # enqueue internal links
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            if urlparse(link).netloc == domain and link not in seen and link not in to_visit:
                to_visit.append(link)

    return " \n".join(texts)[:MAX_SITE_CHARS]

# ────────────────────────────────────────────────────────────────────────────────
# GPT‑4o SECTION GENERATION
# ────────────────────────────────────────────────────────────────────────────────

def _persona_bullets(personas: List[Dict]) -> str:
    if not personas:
        return "N/A"
    return "\n".join(
        [f"- {p['industry']} {p['persona']}: {p['relation']}" for p in personas]
    )


def generate_section_content(section: str, info: Dict, personas: List[Dict]) -> str:
    base = f"""
Company Name: {info['company_name']}
Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems: {info['top_problems']}
Unique Value Proposition: {info['value_prop']}
Website Copy Excerpt: {info['website_text'][:1500]}
Personas:\n{_persona_bullets(personas)}
Tone: {info['tone']}
"""
    prompt = f"""{base}

Write the **{section}** section of a B2B Sales Playbook. Adopt a professional yet conversational tone influenced by Dale Carnegie, Challenger, and Sandler methodologies. Use clear sub‑headers and bullet points where useful."""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a B2B sales strategist writing sales playbooks based on company profiles."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return resp.choices[0].message.content.strip()

@st.cache_data(show_spinner="🧠 Generating playbook with GPT …")
def generate_all_sections(info: Dict, personas: List[Dict]) -> Dict[str, str]:
    return {
        sec: generate_section_content(sec, info, personas) for sec in SECTION_TITLES
    }

# ────────────────────────────────────────────────────────────────────────────────
# WORD EXPORT
# ────────────────────────────────────────────────────────────────────────────────

def build_word_doc(company_name: str, section_texts: Dict[str, str]) -> Document:
    doc = Document()
    doc.add_heading(f"{company_name} B2B Sales Playbook", 0)
    for title, body in section_texts.items():
        doc.add_heading(title, level=1)
        for para in body.split("\n"):
            if para.strip():
                p = doc.add_paragraph(para.strip())
                p.style.font.size = Pt(11)
    return doc

# ────────────────────────────────────────────────────────────────────────────────
# SIDEBAR INPUTS (NO RAW JSON ‑ user‑friendly persona builder)
# ────────────────────────────────────────────────────────────────────────────────

def sidebar_inputs() -> Tuple[Dict, List[Dict]]:
    with st.sidebar:
        st.header("Company Info")
        company_name = st.text_input("Company Name")
        products_services = st.text_area("Products / Services")
        target_audience = st.text_input("Target Audience")
        top_problems = st.text_area("Top Problems")
        value_prop = st.text_area("Unique Value Proposition")
        website_url = st.text_input("Company Website URL (https://…)")
        tone = st.selectbox(
            "Writing Tone",
            ["Professional", "Friendly", "Conversational", "Challenger"],
            index=0,
        )

        # Crawl website when URL entered
        if website_url and "website_text" not in st.session_state:
            try:
                st.session_state.website_text = scrape_public_site(website_url)
            except Exception as e:
                st.warning(f"Could not scrape site: {e}")
                st.session_state.website_text = ""

        st.divider()
        st.header("Prospect Types (max 5)")
        if "num_personas" not in st.session_state:
            st.session_state.num_personas = 1
        # Add button (disabled at 5)
        if st.button("➕ Add another prospect type", disabled=st.session_state.num_personas >= 5):
            st.session_state.num_personas += 1

        personas: List[Dict] = []
        for i in range(st.session_state.num_personas):
            with st.expander(f"Prospect {i+1}", expanded=True):
                industry = st.text_input("Company / Industry", key=f"ind_{i}")
                role = st.text_input("Role / Title", key=f"role_{i}")
                relation = st.text_area(
                    "Why this role cares about your service", key=f"rel_{i}", height=60
                )
                # Only append if at least one field filled
                if industry or role or relation:
                    personas.append({
                        "industry": industry or "",
                        "persona": role or "",
                        "relation": relation or "",
                    })

    info = {
        "company_name": company_name,
        "products_services": products_services,
        "target_audience": target_audience,
        "top_problems": top_problems,
        "value_prop": value_prop,
        "website_text": st.session_state.get("website_text", ""),
        "tone": tone,
    }
    return info, personas

# ────────────────────────────────────────────────────────────────────────────────
# MAIN RENDERER
# ────────────────────────────────────────────────────────────────────────────────

def render_playbook_builder(info: Dict, personas: List[Dict]):
    st.markdown("## 📘 Build Your Custom B2B Sales Playbook")

    if (
        "playbook_sections" not in st.session_state
        and info["company_name"]
        and info["website_text"]
    ):
        st.session_state.playbook_sections = generate_all_sections(info, personas)

    if "playbook_sections" in st.session_state:
        edited: Dict[str, str] = {}
        for sec in SECTION_TITLES:
            st.markdown(f"### ✏️ {sec}")
            edited[sec] = st.text_area(
                f"Edit “{sec}” content below:",
                value=st.session_state.playbook_sections[sec],
                height=250,
                key=f"ta_{sec}",
            )

        st.divider()
        if st.button("📥 Export as Word Document"):
            doc = build_word_doc(info["company_name"], edited)
            filename = f"{re.sub(r'[^A-Za-z0-9]+', '_', info['company_name'])}_Sales_Playbook.docx"
            doc.save(filename)
            with open(filename, "rb") as f:
                st.download_button(
                    "⬇️ Download Playbook",
                    f,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
    else:
        st.info("👈 Fill in the sidebar (including website URL) to generate your playbook.")

# ────────────────────────────────────────────────────────────────────────────────
# ENTRY
# ────────────────────────────────────────────────────────────────────────────────

def main():
    info, personas = sidebar_inputs()
    render_playbook_builder(info, personas)

if __name__ == "__main__":
    main()
