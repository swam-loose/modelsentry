from app.providers.mock import MockModelProvider


def test_mock_provider_is_deterministic() -> None:
    provider = MockModelProvider("deterministic-v1")
    arguments = {
        "rendered_system_prompt": "Answer accurately.",
        "rendered_user_prompt": "Question: Where is Paris?",
        "case_input": {"question": "Where is Paris?"},
    }

    first = provider.generate(**arguments)
    second = provider.generate(**arguments)

    assert first == second
    assert first.output_text == "[deterministic-v1] Question: Where is Paris?"
    assert 5 <= first.latency_ms <= 50


def test_mock_provider_supports_explicit_synthetic_response() -> None:
    response = MockModelProvider("deterministic-v1").generate(
        rendered_system_prompt=None,
        rendered_user_prompt="Question: Where is Paris?",
        case_input={
            "question": "Where is Paris?",
            "mock_response": "Paris is in France.",
        },
    )

    assert response.output_text == "Paris is in France."
