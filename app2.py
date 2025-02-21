import streamlit as st
from google import genai
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import logging
from concurrent.futures import ThreadPoolExecutor
import random
import os

# Set up Google Gemini API Key
# Ensure your environment variable is set
GENAI_API_KEY = os.getenv("GENAI_API_KEY")

# List of common User-Agent strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:40.0) Gecko/20100101 Firefox/40.0",
]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Function to perform DuckDuckGo search and extract URLs


def ddg_search(query):
    results = DDGS().text(query, max_results=5)
    urls = [result['href'] for result in results]

    if not urls:
        logging.warning("No URLs returned by DuckDuckGo.")
        return []

    logging.info(f"URLs fetched: {urls}")
    return get_page(urls)

# Function to scrape web pages and extract text


def get_page(urls):
    content = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(scrape_url, urls)

    for url, result in zip(urls, results):
        if result:
            content.append(result)
            logging.info(f"\n===== Scraped Content from {url} =====\n")
            logging.info(result[:1000])
            logging.info("\n====================================\n")

    return content

# Function to scrape a single URL with a User-Agent header


def scrape_url(url):
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.error(
                f"Failed to load page: {url} (Status Code: {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        if not paragraphs:
            logging.warning(f"No <p> tags found in page: {url}")
            return None

        page_text = "\n".join([para.get_text() for para in paragraphs])
        return truncate(page_text)
    except Exception as e:
        logging.error(f"Error during scraping {url}: {e}")
        return None

# Function to truncate text (Limits to 400 words)


def truncate(text):
    words = text.split()
    return " ".join(words[:4000])

# Function to create a prompt for Gemini


def create_prompt_gemini(llm_query, search_results):
    if not search_results:
        return "No search results available. Please refine your query."

    content = (
        "Based on the context below, answer the question in detail. If necessary, provide examples, explanations, or references.\n\n"
        "Context:\n"
        + "\n\n---\n\n".join(search_results)
        + f"\n\nQuestion: {llm_query}\nAnswer:"
    )
    return content

# Function to get response from Gemini (Updated for correct API usage)


def get_gemini_response(prompt):
    try:
        # Initialize Google Gemini API client
        client = genai.Client(api_key=GENAI_API_KEY)

        # Use the correct method for text generation
        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=prompt
        )

        return response.text
    except Exception as e:
        logging.error(f"Error generating response from Gemini: {e}")
        return f"Error generating response from Gemini: {e}"


# Streamlit UI
with st.form("prompt_form"):
    search_query = st.text_area("DuckDuckGo search:", "")
    llm_query = st.text_area("LLM prompt:", "")
    submitted = st.form_submit_button("Send")

    if submitted:
        with st.spinner("Searching the web..."):
            search_results = ddg_search(search_query)
        st.success("Web Scraping Complete!")

        if search_results:
            with st.spinner("Sending data to Gemini..."):
                prompt = create_prompt_gemini(llm_query, search_results)
                result = get_gemini_response(prompt)
            st.success("Response Generated!")
        else:
            result = "Unable to generate a response due to lack of context."

        e = st.expander("LLM prompt created:")
        e.write(prompt)
        st.write(result)
