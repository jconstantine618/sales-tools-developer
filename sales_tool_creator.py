import streamlit as st
from typing import List, Dict
from openai import OpenAI
from docx import Document
from docx.shared import Pt
import json

# -----------------------------
# Configuration & Setup
# -----------------------------

st.set_page_config(page_title="B2B Sales Playbook Builder", page_icon="📘", layout="wide")

@st.cache_resource(show_spinner=False)
def get_openai_client() -> OpenAI:
    """Initialise OpenAI once per session."""
    return OpenAI(api_key=st.secrets["openai_api_key"])

client = get_openai_client()

SECTION_TITLES = [
    "Company Overview",
    "Value Propositions",
    "Customer Benefits",
    "Target Audience",
    "Needs Assessment Questions",
    "Demo Customer Personas",
    "Closing Questions",
    "Lead Generation Channels & Next Steps",
]

# -----------------------------
# GPT-4 Helper
# -----------------------------

def generate_section_content(section: str, info: Dict, personas: List[Dict]) -> str:
    """Ask GPT-4 for the copy of a single playbook section."""
    persona_text = "\n".join(
        [f"- {p['industry']} {p['persona']}, Pain Points: {', '.join(p['pain_points'])}" for p in personas]
    ) if personas else "N/A"

    base_context = f"""
Company Name: {info['company_name']}
Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems: {info['top_problems']}
Unique Value Proposition: {info['value_prop']}
Website Content: {info['website_text'][:1500]}
Personas: {persona_text}
Tone: {info['tone']}
"""

    prompt = f"""
{base_context}

Write the **{section}** section of a B2B Sales Playbook. Use a professional and conversational tone inspired by Dale Carnegie, Challenger, and Sandler sales principles. Structure it as a sales assistant would use to guide a customer conversation. Include helpful examples and bullet points where appropriate.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # cheaper & fast; adjust if you need full GPT‑4o
        messages=[
            {"role": "system", "content": "You are a B2B sales strategist writing sales playbooks based on company profiles."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

@st.cache_data(show_spinner=False)
def generate_all_sections(info: Dict, personas: List[Dict]) -> Dict[str, str]:
    """Generate the full set of playbook sections (cached so the user can edit without rerunning GPT)."""
    return {section: generate_section_content(section, info, personas) for section in SECTION_TITLES}

# -----------------------------
# Word Export Helper
# -----------------------------

def build_word_doc(company_name: str, section_texts: Dict[str, str]) -> Document:
    doc = Document()
    doc.add_heading(f"{company_name} B2B Sales Playbook", 0)

    for title, content in section_texts.items():
        doc.add_heading(title, level=1)
        for paragraph in content.split("\n"):
            if paragraph.strip():
                p = doc.add_paragraph(paragraph.strip())
                p.style.font.size = Pt(11)
    return doc

# -----------------------------
# UI Components
# -----------------------------

def sidebar_inputs() -> tuple[Dict, List[Dict]]:
    """Collect basic company info & optional personas from the sidebar."""
    with st.sidebar:
        st.header("Company Info")
        company_name = st.text_input("Company Name")
        products_services = st.text_area("Products / Services")
        target_audience = st.text_input("Target Audience")
        top_problems = st.text_area("Top Problems")
        value_prop = st.text_area("Unique Value Proposition")
        website_text = st.text_area("Website Text (paste relevant snippet)")
        tone = st.selectbox("Writing Tone", ["Professional", "Friendly", "Conversational", "Challenger"], index=0)

        st.divider()
        st.header("Personas (optional)")
        persona_json = st.text_area(
            "Paste a JSON array of personas (see help below)",
            placeholder="""[
  {"industry": "SaaS", "persona": "CTO", "pain_points": ["legacy tech", "scaling"]},
  {"industry": "Manufacturing", "persona": "Operations Manager", "pain_points": ["downtime", "safety"]}
]"""
        )
        if persona_json:
            try:
                personas = json.loads(persona_json)
                if not isinstance(personas, list):
                    raise ValueError
            except Exception:
                st.error("❌ Personas JSON is invalid. It must be a list of objects as shown in the placeholder.")
                personas = []
        else:
            personas = []

    info = {
        "company_name": company_name,
        "products_services": products_services,
        "target_audience": target_audience,
        "top_problems": top_problems,
        "value_prop": value_prop,
        "website_text": website_text,
        "tone": tone,
    }
    return info, personas


def render_playbook_builder(info: Dict, personas: List[Dict]):
    """Main playbook editing & export interface."""
    st.markdown("## 📘 Build Your Custom B2B Sales Playbook")

    # Generate once and keep in session
    if "playbook_sections" not in st.session_state and info["company_name"]:
        with st.spinner("🧠 Generating initial content with GPT‑4o…"):
            st.session_state.playbook_sections = generate_all_sections(info, personas)

    if "playbook_sections" in st.session_state:
        edited_sections = {}

        for section in SECTION_TITLES:
            st.markdown(f"### ✏️ {section}")
            edited = st.text_area(
                label=f"Edit '{section}' content below:",
                value=st.session_state.playbook_sections[section],
                height=250,
                key=f"section_{section}",
            )
            edited_sections[section] = edited

        st.divider()
        if st.button("📥 Export as Word Document"):
            doc = build_word_doc(info["company_name"], edited_sections)
            file_name = f"{info['company_name'].replace(' ', '_')}_Sales_Playbook.docx"
            doc.save(file_name)
            with open(file_name, "rb") as f:
                st.download_button("⬇️ Download Playbook", f, file_name=file_name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    else:
        st.info("👈 Enter company details in the sidebar to generate your playbook.")

# -----------------------------
# Main Entry Point
# -----------------------------

def main():
    info, personas = sidebar_inputs()
    render_playbook_builder(info, personas)

if __name__ == "__main__":
    main()
