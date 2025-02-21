import streamlit as st
import ollama
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import logging
from concurrent.futures import ThreadPoolExecutor
import random

# List of common User-Agent strings
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
]  # Choose at random from this list kind of intelligent ik

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set log level to INFO
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraping.log"),  # Save logs to a file
        logging.StreamHandler()  # Print logs in terminal
    ]
)  # Logs all the ongoing shits occuring, gonna keep a track for random failures

# Function to perform DuckDuckGo search and extract URLs


def ddg_search(query):
    results = DDGS().text(query, max_results=5)  # Don't tweak to 10 you fool
    urls = [result['href'] for result in results]

    if not urls:
        logging.warning("No URLs returned by DuckDuckGo.")
        return []

    logging.info(f"URLs fetched: {urls}")
    return get_page(urls)

# Function to scrape web pages and extract text


def get_page(urls):
    content = []

    # change workers if you want but suggested don't go over 5 workers or your brain may crash
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(scrape_url, urls)  # Run scraping in parallel

    for url, result in zip(urls, results):
        if result:
            content.append(result)

            # Log the scraped content in the terminal
            logging.info(f"\n===== Scraped Content from {url} =====\n")
            # Logs only first 1000 characters, what will you do with the rest of the content? Huh?
            logging.info(result[:1000])
            logging.info("\n====================================\n")

    return content

# Function to scrape a single URL with a User-Agent header


def scrape_url(url):
    try:
        # Randomly select a User-Agent
        # I hope I explained this already
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.error(
                f"Failed to load page: {url} (Status Code: {response.status_code})")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        paragraphs = soup.find_all('p')
        if not paragraphs:
            # Hope the website has <p> tags or it's doomed
            logging.warning(f"No <p> tags found in page: {url}")
            return None

        page_text = "\n".join([para.get_text() for para in paragraphs])
        return truncate(page_text)
    except Exception as e:
        logging.error(f"Error during scraping {url}: {e}")
        return None

# Function to truncate text

# Don't wanna get the whole movie script so first 400 and also to feed mistral but We will need embeddings for more precise content


def truncate(text):
    words = text.split()
    return " ".join(words[:400])  # Limit to first 400 words

# Function to create a prompt for Mistral

# Prompt limit is just 2048 very painful
def create_prompt_mistral(llm_query, search_results):
    if not search_results:
        return "No search results available. Please refine your query."

    content = (
        "Answer the question using only the context below.\n\n"
        "Context:\n"
        + "\n\n---\n\n".join(search_results)
        + f"\n\nQuestion: {llm_query}\nAnswer:"
    )
    return [{'role': 'user', 'content': content}]

# Function to get response from Mistral


def get_mistral_response(prompt):
    try:
        completion = ollama.chat(model='mistral', messages=prompt)
        return completion['message']['content']
    except Exception as e:
        logging.error(f"Error generating response from Mistral: {e}")
        return f"Error generating response from Mistral: {e}"


# Streamlit UI
# I don't know how this works find on your own.
with st.form("prompt_form"):
    search_query = st.text_area("DuckDuckGo search:", "")
    llm_query = st.text_area("LLM prompt:", "")
    submitted = st.form_submit_button("Send")

    if submitted:
        with st.spinner("Searching the web..."):
            search_results = ddg_search(search_query)
        st.success("Web Scraping Complete!")

        if search_results:
            with st.spinner("Sending data to Mistral..."):
                prompt = create_prompt_mistral(llm_query, search_results)
                result = get_mistral_response(prompt)
            st.success("Response Generated!")
        else:
            result = "Unable to generate a response due to lack of context."

        e = st.expander("LLM prompt created:")
        e.write(prompt)
        st.write(result)
