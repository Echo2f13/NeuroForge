import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

endpoint = "https://models.github.ai/inference"
model = "openai/gpt-4.1-nano"
token = "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"

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

