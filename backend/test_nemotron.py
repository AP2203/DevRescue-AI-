import asyncio
import sys
from openai import AsyncOpenAI
from app.core.config import settings

async def main():
    if not settings.NVIDIA_API_KEY or not settings.NVIDIA_API_KEY.strip():
        print("Error: NVIDIA_API_KEY is not configured in backend/.env.")
        sys.exit(1)

    try:
        client = AsyncOpenAI(
            api_key=settings.NVIDIA_API_KEY,
            base_url=settings.NVIDIA_BASE_URL,
            timeout=45.0
        )
        response = await client.chat.completions.create(
            model=settings.NEMOTRON_MODEL,
            messages=[
                {"role": "system", "content": "You are a software engineering assistant."},
                {"role": "user", "content": "Explain in one paragraph why a Python dictionary lookup can raise KeyError."}
            ],
            temperature=0.2
        )
        if response.choices and response.choices[0].message.content:
            print(response.choices[0].message.content.strip())
        else:
            print("Error: Received empty response from model.")
            sys.exit(1)
    except Exception as e:
        # Sanitize any error output so API keys are never printed
        msg = str(e)
        if settings.NVIDIA_API_KEY:
            msg = msg.replace(settings.NVIDIA_API_KEY, "[REDACTED]")
        print(f"Error during Nemotron connection test: {msg}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

