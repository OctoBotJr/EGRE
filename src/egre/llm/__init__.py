"""Provider-neutral LLM clients for the prototype agent."""

from egre.llm.base import LLMClient, Message
from egre.llm.fake import FakeLLM
from egre.llm.openai import OpenAIAdapter, OpenAIClient

__all__ = ["FakeLLM", "LLMClient", "Message", "OpenAIAdapter", "OpenAIClient"]
