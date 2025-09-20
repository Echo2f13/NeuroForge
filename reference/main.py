import os
from pathlib import Path
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential


try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    load_dotenv = None  # type: ignore


def _load_env_vars():
    env_path = Path(__file__).resolve().parent / ".env"
    if load_dotenv:
        load_dotenv(env_path)
        return
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")

        if not sep:
            continue
        os.environ.setdefault(key.strip(), value.strip())


_load_env_vars()

endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1-nano"
token = os.getenv("GITHUB_TOKEN")
if not token:
    raise RuntimeError("GITHUB_TOKEN must be set before calling the GitHub Models API")

client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(token),
)

response = client.complete(
    messages=[
        SystemMessage(""),
        UserMessage("Tell me everything you know about CNN"),
    ],
    temperature=1,
    top_p=1,
    model=model
)

print(response.choices[0].message.content)

