import streamlit as st
import openai
from docx import Document
from docx.shared import Pt
from typing import Dict, List
import os

# Set up OpenAI client
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# Playbook sections to generate
SECTION_TITLES = [
    "Company Overview",
    "Value Propositions",
    "Customer Benefits",
    "Target Audience",
    "Needs Assessment Questions",
    "Demo Customer Personas",
    "Closing Questions",
    "Lead Generation Channels & Next Steps"
]

# Generate one section via GPT
def generate_section_content(section: str, info: Dict, personas: List[Dict]) -> str:
    persona_text = "\n".join([
        f"- {p['industry']} {p['persona']}, Pain Points: {', '.join(p['pain_points'])}"
        for p in personas
    ]) if personas else "N/A"

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
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a B2B sales strategist writing sales playbooks based on company profiles."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

# Build .docx file from section data
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

# Main Streamlit UI flow
def render_playbook_builder(info: Dict, personas: List[Dict]):
    st.markdown("## 📘 Build Your Custom B2B Sales Playbook")

    if "playbook_sections" not in st.session_state:
        st.session_state.playbook_sections = {}
        with st.spinner("🧠 Generating initial content using GPT..."):
            for section in SECTION_TITLES:
                content = generate_section_content(section, info, personas)
                st.session_state.playbook_sections[section] = content

    edited_sections = {}

    for section in SECTION_TITLES:
        st.markdown(f"### ✏️ {section}")
        edited = st.text_area(
            f"Edit '{section}' content below:",
            value=st.session_state.playbook_sections[section],
            height=250
        )
        edited_sections[section] = edited

    if st.button("📥 Export as Word Document"):
        doc = build_word_doc(info["company_name"], edited_sections)
        file_name = f"{info['company_name'].replace(' ', '_')}_Sales_Playbook.docx"
        doc.save(file_name)
        with open(file_name, "rb") as f:
            st.download_button("Download Playbook", f, file_name=file_name)
