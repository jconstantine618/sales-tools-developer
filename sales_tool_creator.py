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

# Crawl and extract up to 10 pages from the website
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

    return "\n\n".join(all_text)[:10000]  # limit content for GPT prompt

# Form to gather company inputs
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
                "tone": tone,
                "extra_notes": ""
            }
        else:
            st.warning("Please complete all fields.")
    return None

# Load personas from local file
def load_personas():
    if os.path.exists("prospects.json"):
        with open("prospects.json") as f:
            return json.load(f)
    else:
        return []

# Use OpenAI to generate all content
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

# Compose the full prompt to GPT
def create_deliverables(info, personas):
    persona_summary = "\n".join(
        [f"- {p['industry']} {p['persona']} with pain points: {', '.join(p['pain_points'])}" for p in personas]
    ) if personas else "No personas provided."

    prompt = f"""
Based on the following company profile, generate comprehensive B2B sales tools using Dale Carnegie, Sandler, and Challenger frameworks:

Company Name: {info['company_name']}
Website URL: {info['website']}
Website Text Extract:
{info['website_text'][:2000]}...

Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems Solved: {info['top_problems']}
Unique Value Proposition: {info['value_prop']}
Tone: {info['tone']}

Customer personas to target:
{persona_summary}

Additional context from user: {info.get("extra_notes", "")}

DELIVERABLES TO RETURN:

1. A cold call script
2. A warm intro call script
3. A discovery call script
4. An email sequence (intro, follow-up, breakup)
5. **Three different elevator pitches** for different tones/contexts
6. **5–7 needs assessment questions**
7. A **comprehensive description of ideal target prospects**, including any not explicitly listed above.
"""
    return generate_content(prompt)

# PDF conversion
def save_to_pdf(content, filename="sales_tools.pdf"):
    html_content = f"<pre>{content}</pre>"
    pdfkit.from_string(html_content, filename)
    return filename

# Main Streamlit app logic
def main():
    st.set_page_config(layout="wide")
    st.title("🎯 B2B Sales Tool Generator (GPT-Enhanced)")

    if "info" not in st.session_state:
        st.session_state.info = get_company_info()

    if st.session_state.info:
        personas = load_personas()
        deliverables = create_deliverables(st.session_state.info, personas)
        st.success("✅ Sales tools generated!")
        st.text_area("Generated Sales Tools", deliverables, height=500)

        if st.button("Download as PDF"):
            filename = save_to_pdf(deliverables)
            with open(filename, "rb") as f:
                st.download_button("📥 Download PDF", f, file_name="sales_tools.pdf")

        st.markdown("### 💬 Chat with GPT to Refine Your Tools")
        user_feedback = st.text_area(
            "Is there anything you would like to add or other thoughts that this gives you to further refine the tools provided?",
            placeholder="e.g., Add a version for government clients or adjust the tone to be more assertive."
        )

        if st.button("Regenerate with Feedback"):
            st.session_state.info["extra_notes"] = user_feedback
            updated = create_deliverables(st.session_state.info, personas)
            st.success("🎯 Tools regenerated with your input!")
            st.text_area("Updated Tools", updated, height=500)

if __name__ == "__main__":
    main()
