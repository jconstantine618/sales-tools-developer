import streamlit as st
import openai
import requests
import pdfkit
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List
from PyPDF2 import PdfFileReader
from docx import Document as DocxDocument
from docx.shared import Pt

client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

def extract_website_text(base_url, max_pages=10):
    visited = set()
    to_visit = [base_url]
    domain = urlparse(base_url).netloc
    all_text = []
    headers = {"User-Agent": "Mozilla/5.0"}

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        try:
            response = requests.get(url, timeout=10, headers=headers)
            soup = BeautifulSoup(response.content, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.extract()
            text = soup.get_text(separator=" ", strip=True)
            all_text.append(f"[{url}]\n{text[:3000]}")
            for link in soup.find_all("a", href=True):
                abs_url = urljoin(base_url, link["href"])
                parsed = urlparse(abs_url)
                if parsed.netloc == domain and abs_url not in visited and abs_url not in to_visit:
                    to_visit.append(abs_url)
            visited.add(url)
        except Exception as e:
            st.warning(f"Failed to fetch {url}: {e}")
            continue
    return "\n\n".join(all_text)[:10000]

def get_company_info():
    st.header("🚀 Sales Playbook Generator")
    company_name = st.text_input("Company Name")
    website = st.text_input("Company Website (https://...)")
    products_services = st.text_area("Describe your Products or Services")
    target_audience = st.text_input("Who is your target audience?")
    top_problems = st.text_area("What top 3 problems do you solve?")
    value_prop = st.text_area("What is your unique value proposition?")
    tone = st.selectbox("What tone fits your brand?", ["Friendly", "Formal", "Bold", "Consultative"])

    st.markdown("### 📎 Optional: Upload Sales Collateral")
    uploaded_files = st.file_uploader(
        "Upload brochures, PDFs, or Word docs",
        type=["pdf", "docx"],
        accept_multiple_files=True
    )

    if st.button("Generate Sales Tools"):
        if all([company_name, website, products_services, target_audience, top_problems, value_prop]):
            st.info("🔎 Crawling website and extracting content...")
            website_text = extract_website_text(website)
            return {
                "company_name": company_name,
                "website": website,
                "website_text": website_text,
                "products_services": products_services,
                "target_audience": target_audience,
                "top_problems": top_problems,
                "value_prop": value_prop,
                "tone": tone,
                "extra_notes": "",
                "uploaded_files": uploaded_files
            }
        else:
            st.warning("Please complete all fields.")
    return None

def extract_uploaded_text(files):
    content = []
    for file in files:
        if file.type == "application/pdf":
            pdf = PdfFileReader(file)
            text = "\n".join([page.extractText() for page in pdf.pages])
            content.append(text)
        elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = DocxDocument(file)
            text = "\n".join([para.text for para in doc.paragraphs])
            content.append(text)
    return "\n\n".join(content)

def get_user_defined_personas():
    st.markdown("### 👥 Add Customer Personas")
    if "personas" not in st.session_state:
        st.session_state.personas = []
    with st.form("add_persona_form"):
        col1, col2 = st.columns(2)
        with col1:
            industry = st.text_input("Industry", key="industry_input")
        with col2:
            persona = st.text_input("Persona Title", key="persona_input")
        pain_points = st.text_area("Pain Points (comma separated)", key="pain_input")
        submitted = st.form_submit_button("➕ Add Persona")
        if submitted:
            if industry and persona and pain_points:
                st.session_state.personas.append({
                    "industry": industry,
                    "persona": persona,
                    "pain_points": [p.strip() for p in pain_points.split(",") if p.strip()]
                })
                st.success(f"Added persona: {industry} - {persona}")
            else:
                st.warning("Please fill in all fields before adding.")
    if st.session_state.personas:
        st.markdown("#### Current Personas:")
        for p in st.session_state.personas:
            st.markdown(f"🔹 **{p['industry']} - {p['persona']}**  \n🧩 Pain Points: {', '.join(p['pain_points'])}")

def create_deliverables(info, personas, collateral_text=""):
    persona_summary = "\n".join(
        [f"- {p['industry']} {p['persona']} with pain points: {', '.join(p['pain_points'])}" for p in personas]
    ) if personas else "No personas provided."

    prompt = f"""
Company Name: {info['company_name']}
Website URL: {info['website']}
Website Text: {info['website_text'][:2000]}
Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems: {info['top_problems']}
Value Proposition: {info['value_prop']}
Tone: {info['tone']}

Customer personas:
{persona_summary}

User notes: {info.get('extra_notes', '')}

Uploaded collateral:
{collateral_text[:3000]}

Generate a complete B2B Sales Playbook with sections for:
- Company Overview
- Value Propositions
- Customer Benefits
- Target Audience
- Needs Assessment Questions
- Customer Personas
- Objection Handling
- Discovery Call Framework
- Sales Email & Call Sequence
- Closing Questions
- Lead Generation Channels & Next Steps
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a B2B sales strategist."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def save_to_word(content, company_name="Sales_Playbook"):
    doc = DocxDocument()
    doc.add_heading(f"{company_name} B2B Sales Playbook", 0)
    for section in content.split("### "):
        if section.strip():
            parts = section.strip().split("\n", 1)
            title = parts[0].strip()
            body = parts[1].strip() if len(parts) > 1 else ""
            doc.add_heading(title, level=1)
            for paragraph in body.split("\n"):
                if paragraph.strip():
                    p = doc.add_paragraph(paragraph.strip())
                    p.style.font.size = Pt(11)
    file_name = f"{company_name.replace(' ', '_')}_Sales_Playbook.docx"
    doc.save(file_name)
    return file_name

def main():
    st.set_page_config(layout="wide")
    st.title("🎯 B2B Sales Playbook Generator")
    if "info" not in st.session_state:
        st.session_state.info = None
    if st.session_state.info is None:
        info = get_company_info()
        if info:
            st.session_state.info = info
            st.rerun()
    else:
        get_user_defined_personas()
        collateral_text = extract_uploaded_text(st.session_state.info["uploaded_files"]) if st.session_state.info.get("uploaded_files") else ""
        personas = st.session_state.personas
        deliverables = create_deliverables(st.session_state.info, personas, collateral_text)
        st.success("✅ Custom Sales Playbook Generated!")
        st.text_area("📄 Full Playbook Preview", deliverables, height=600)

        if st.button("📥 Download as Word Document"):
            file_name = save_to_word(deliverables, st.session_state.info["company_name"])
            with open(file_name, "rb") as f:
                st.download_button("Download .docx", f, file_name=file_name)

if __name__ == "__main__":
    main()
