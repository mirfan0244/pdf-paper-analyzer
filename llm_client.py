from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()


def get_client(provider="Gemini"):
    provider = provider.lower()

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        return OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        ), os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    elif provider == "ollama":
        return OpenAI(
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        ), os.getenv("OLLAMA_MODEL", "llama3.2")

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        return OpenAI(api_key=api_key), os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    else:
        raise ValueError(f"Unsupported provider: {provider}")


def extract_metadata(client, model, raw_text, prompt):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a precise metadata extractor."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096,
    )
    return response.choices[0].message.content


def chat_with_data(client, model, context, user_message, history):
    system_msg = f"""You are a research data analyst.
Use the paper metadata below to answer questions.
Cite paper titles when possible.

# Paper Data
{context}"""

    messages = [{"role": "system", "content": system_msg}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    return client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True
    )