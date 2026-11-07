"""Provider-agnostic LLM interface. Swap Gemini for another provider by implementing this protocol."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    name: str  # e.g. "gemini"
    model: str  # model identifier stored with every AI-generated record

    def generate_json(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Return `schema` validated from the model's JSON output.

        Raises an `LLMError` subclass on any failure (never returns invented data).
        """
        ...
