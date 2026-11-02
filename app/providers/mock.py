import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class MockProviderResponse:
    """Deterministic provider output and synthetic latency."""

    output_text: str
    latency_ms: int


class MockModelProvider:
    """Local deterministic provider used for reproducible evaluation tests."""

    def __init__(self, model_identifier: str) -> None:
        self.model_identifier = model_identifier

    def generate(
        self,
        *,
        rendered_system_prompt: str | None,
        rendered_user_prompt: str,
        case_input: dict[str, Any],
    ) -> MockProviderResponse:
        explicit_response = case_input.get("mock_response")
        if isinstance(explicit_response, str):
            output_text = explicit_response
        else:
            output_text = f"[{self.model_identifier}] {rendered_user_prompt}"

        fingerprint_payload = json.dumps(
            {
                "model_identifier": self.model_identifier,
                "system_prompt": rendered_system_prompt,
                "user_prompt": rendered_user_prompt,
                "input": case_input,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = sha256(fingerprint_payload).digest()
        latency_ms = 5 + int.from_bytes(digest[:2], "big") % 46
        return MockProviderResponse(
            output_text=output_text,
            latency_ms=latency_ms,
        )
