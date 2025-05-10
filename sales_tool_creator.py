import streamlit as st
import openai
import json
import pdfkit

# Set your OpenAI API key here or use streamlit secrets
openai.api_key = st.secrets.get("openai_api_key", "YOUR_OPENAI_API_KEY")

# Define company input prompts
def get_company_info():
    st.header("🚀 Sales Script & Tools Generator")

    company_name = st.text_input("Company Name")
    products_services = st.text_area("Describe your Products or Services")
    target_audience = st.text_input("Who is your target audience?")
    top_problems = st.text_area("What top 3 problems do you solve?")
    value_prop = st.text_area("What is your unique value proposition?")
    tone = st.selectbox("What tone fits your brand?", ["Friendly", "Formal", "Bold", "Consultative"])

    if st.button("Generate Sales Tools"):
        if all([company_name, products_services, target_audience, top_problems, value_prop]):
            return {
                "company_name": company_name,
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

# Load persona scenarios (expand as needed)
def load_personas():
    with open("prospects.json") as f:
        return json.load(f)

# Generate content with ChatGPT
def generate_content(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a B2B sales expert trained on Dale Carnegie, Sandler, and Challenger frameworks."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response['choices'][0]['message']['content']

# Generate all deliverables
def create_deliverables(info, personas):
    prompt = f"""
Create the following based on this company:
Company Name: {info['company_name']}
Products/Services: {info['products_services']}
Target Audience: {info['target_audience']}
Top Problems: {info['top_problems']}
Value Proposition: {info['value_prop']}
Tone: {info['tone']}

1. Cold call script
2. Warm intro script
3. Discovery call script
4. Prospecting email sequence (intro, follow-up, breakup)
5. 2 elevator pitch versions (short and descriptive)
6. 5-7 needs assessment questions
7. Example customer personas with pain points

Base this on Dale Carnegie, Sandler, and Challenger principles.
"""
    result = generate_content(prompt)
    return result

# Save deliverables to PDF
def save_to_pdf(content, filename="sales_tools.pdf"):
    html_content = f"<pre>{content}</pre>"
    pdfkit.from_string(html_content, filename)
    return filename

# Main app
def main():
    info = get_company_info()
    if info:
        st.info("Generating sales tools... Please wait ⏳")
        personas = load_personas()
        deliverables = create_deliverables(info, personas)
        st.success("✅ Sales tools generated!")
        st.text_area("Generated Sales Tools", deliverables, height=400)

        if st.button("Download as PDF"):
            filename = save_to_pdf(deliverables)
            with open(filename, "rb") as f:
                st.download_button("📥 Download PDF", f, file_name="sales_tools.pdf")

if __name__ == "__main__":
    main()
