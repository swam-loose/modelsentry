import pytest

from app.evaluation.renderer import PromptRenderer, PromptRenderingError


def test_renderer_replaces_declared_variables_deterministically() -> None:
    rendered = PromptRenderer.render(
        "Question: {{ question }} | Context: {{context}}",
        variables=["question", "context"],
        values={
            "question": "Where is Paris?",
            "context": {"country": "France", "language": "French"},
        },
    )

    assert rendered == (
        'Question: Where is Paris? | Context: {"country":"France","language":"French"}'
    )


def test_renderer_rejects_missing_declared_variable() -> None:
    with pytest.raises(PromptRenderingError, match="Missing prompt variables"):
        PromptRenderer.render(
            "Question: {{question}}",
            variables=["question"],
            values={},
        )


def test_renderer_rejects_undeclared_template_variable() -> None:
    with pytest.raises(PromptRenderingError, match="not declared"):
        PromptRenderer.render(
            "Question: {{question}}",
            variables=[],
            values={"question": "Where is Paris?"},
        )
