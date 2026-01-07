from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def summarize_article(content: str):
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "You are a professional research assistant. Summarize the following text into 3-5 concise bullet points in Markdown format."},
            {"role": "user", "content": content}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content
