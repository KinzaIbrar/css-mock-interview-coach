"""Test doubles for the LLM layer. No test ever contacts the real Gemini API."""

import re

from app.agents.schemas import EvaluationLLMOutput, FeedbackLLMOutput


def eval_output(score: float = 8.0, follow_up: str = "", **overrides) -> EvaluationLLMOutput:
    data = dict(
        relevance=score, subject_knowledge=score, accuracy=score, reasoning=score, structure=score, clarity=score,
        strengths=["Covers the main idea clearly"], weaknesses=["Could add a concrete example"],
        missing_info=["A specific date"], follow_up_question=follow_up,
    )
    data.update(overrides)
    return EvaluationLLMOutput(**data)


def feedback_output(prompt: str = "", **overrides) -> FeedbackLLMOutput:
    m = re.search(r"TOPICS \(use only these for revision_topics\): (.*)", prompt)
    topics = [t.strip() for t in m.group(1).split(",")][:1] if m else []
    data = dict(
        summary="You gave solid answers overall; focus next on adding concrete examples.",
        improvements=["Add one concrete example to every answer", "Revise key dates"],
        revision_topics=topics,
    )
    data.update(overrides)
    return FeedbackLLMOutput(**data)


class FakeProvider:
    """Scriptable LLMProvider. `script` items are consumed one per call:
    an Exception (raised), a pydantic model (returned), or a callable(schema, prompt) -> model.
    When the script is exhausted a sensible default is returned."""

    name = "fake"

    def __init__(self, script=None, model: str = "fake-model-1", default_score: float = 8.0):
        self.model = model
        self.script = list(script or [])
        self.default_score = default_score
        self.calls: list[dict] = []

    def generate_json(self, *, system, prompt, schema):
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item(schema, prompt) if callable(item) else item
        if schema is EvaluationLLMOutput:
            return eval_output(self.default_score)
        return feedback_output(prompt)

    @property
    def eval_calls(self):
        return [c for c in self.calls if c["schema"] is EvaluationLLMOutput]

    @property
    def feedback_calls(self):
        return [c for c in self.calls if c["schema"] is FeedbackLLMOutput]


class FakeApiError(Exception):
    """Looks like google.genai.errors.APIError (has .code / .message)."""

    def __init__(self, code: int, message: str = "boom"):
        super().__init__(message)
        self.code = code
        self.message = message


class FakeResponse:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, owner):
        self.owner = owner

    def generate_content(self, *, model, contents, config):
        self.owner.calls.append({"model": model, "contents": contents, "config": config})
        item = self.owner.script.pop(0) if self.owner.script else FakeResponse(eval_output().model_dump_json())
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    """Stands in for google.genai.Client; `script` items are Exceptions or FakeResponse objects."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls: list[dict] = []
        self.models = _Models(self)


class Clock:
    """Manual clock + sleep recorder so retry/cooldown tests run instantly."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds
