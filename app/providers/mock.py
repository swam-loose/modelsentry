import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class MockProviderResponse:
    """Deterministic output with synthetic latency and estimated token usage."""

    output_text: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


class MockModelProvider:
    """Local deterministic provider used for reproducible evaluation tests."""

    def __init__(self, model_identifier: str) -> None:
        self.model_identifier = model_identifier

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate tokens deterministically from UTF-8 bytes for local testing."""

        if not text:
            return 0
        return max(1, (len(text.encode("utf-8")) + 3) // 4)

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
        input_text = "\n".join(
            part
            for part in (rendered_system_prompt, rendered_user_prompt)
            if part is not None
        )
        return MockProviderResponse(
            output_text=output_text,
            latency_ms=latency_ms,
            input_tokens=self.estimate_tokens(input_text),
            output_tokens=self.estimate_tokens(output_text),
        )
