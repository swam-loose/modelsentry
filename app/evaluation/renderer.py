import json
import re
from collections.abc import Mapping, Sequence

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class PromptRenderingError(Exception):
    """Raised when an evaluation case cannot satisfy a prompt contract."""


class PromptRenderer:
    """Render declared prompt variables without executing arbitrary templates."""

    @classmethod
    def render(
        cls,
        template: str,
        *,
        variables: Sequence[str],
        values: Mapping[str, object],
    ) -> str:
        declared = set(variables)
        missing = [name for name in variables if name not in values]
        if missing:
            joined = ", ".join(sorted(missing))
            raise PromptRenderingError(f"Missing prompt variables: {joined}.")

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in declared:
                raise PromptRenderingError(
                    f"Template variable '{name}' is not declared."
                )
            return cls._stringify(values[name])

        return PLACEHOLDER_PATTERN.sub(replace, template)

    @staticmethod
    def _stringify(value: object) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
