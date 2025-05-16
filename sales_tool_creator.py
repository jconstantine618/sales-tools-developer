import streamlit as st
import openai
import json
import requests
import pdfkit
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Initialize OpenAI client
client = openai.OpenAI(api_key=st.secrets["openai_api_key"])

# Crawl and extract up to 10 internal pages
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

    return "\n\n".join(all_text)[:10000]  # trimmed for GPT token limits

# Input form for company info
def get_company_info():
    st.header("🚀 Sales Script & Tools Generator")

    company_name = st.text_input("Company Name")
    website = st.text_input("Company Website (https://...)")
    products_services = st.text_area("Describe your Products or Services")
    target_audience = st.text_input("Who is your target audience?")
    top_problems = st.text_area("What top 3 problems do you solve?")
    value_prop = st.text_area("What is your unique value proposition?")
    tone = st.selectbox("What tone fits your brand?", ["Friendly", "Formal", "Bold", "Consultative"])

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
                "tone": tone
            }
        else:
            st.warning("Please complete all fields.")
            return None
    return None

# Load personas
def load_personas():
    if os.path.exists("prospects.json"):
        with open("prospects.json") as f:
            return json.load(f)
    else:
        return []

# GPT content generator
def generate_content(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a B2B sales expert trained in Dale Carnegie, Sandler, and Challenger frameworks."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

# Construct GPT prompt
def create_deliverables(info, personas):
    persona_summary = "\n".join(
        [f"- {p['industry']} {p['persona']} with pain points: {', '.join(p['pain_points'])}" for p in personas]
    ) if personas else "No personas provided."

    prompt = f"""
Use the following company information to generate:

1. Cold call script
2. Warm intro script
3. Discovery call script
4. Prospecting email sequence (intro, follow-up, breakup)
5. 2 elevator pitch versions (short and descriptive)
6. 5-7 needs assessment questions

Use Dale Carnegie, Sandler, and Challenger selling principles.
Tone: {info['tone']}

Company Name: {info['company_name']}
Website URL: {info['website']}
Extracted Website Content:
{info['website_text'][:2000]}...

Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems Solved: {info['top_problems']}
Value Proposition: {info['value_prop']}

Customer personas to target:
{persona_summary}
"""
    return generate_content(prompt)

# Save text output to PDF
def save_to_pdf(content, filename="sales_tools.pdf"):
    html_content = f"<pre>{content}</pre>"
    pdfkit.from_string(html_content, filename)
    return filename

# Main app
def main():
    info = get_company_info()
    if info:
        st.info("Generating sales tools with ChatGPT... ⏳")
        personas = load_personas()
        deliverables = create_deliverables(info, personas)
        st.success("✅ Sales tools generated!")
        st.text_area("Generated Sales Tools", deliverables, height=500)

        if st.button("Download as PDF"):
            filename = save_to_pdf(deliverables)
            with open(filename, "rb") as f:
                st.download_button("📥 Download PDF", f, file_name="sales_tools.pdf")

if __name__ == "__main__":
    main()
