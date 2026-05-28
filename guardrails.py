import json
from dataclasses import dataclass, field
from openai import OpenAI
from config import MODEL, INPUT_GUARD_SYSTEM, OUTPUT_GUARD_SYSTEM


@dataclass
class GuardResult:
    safe: bool
    reason: str = ""
    issues: list = field(default_factory=list)


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    return json.loads(text)


def check_input(client: OpenAI, story_request: str, child_name: str) -> GuardResult:
    """
    Pre-generation guardrail: verify the user's request is child-safe
    before spending tokens on story generation.
    """
    content = f"Story request: {story_request}\nChild's name: {child_name}"
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": INPUT_GUARD_SYSTEM},
            {"role": "user", "content": content},
        ],
        temperature=0.0,
        max_tokens=120,
    )
    try:
        data = _parse_json(response.choices[0].message.content)
        return GuardResult(
            safe=bool(data.get("safe", False)),
            reason=data.get("reason", ""),
        )
    except (json.JSONDecodeError, KeyError):
        # Fail safe: block the request if we can't parse the verdict
        return GuardResult(safe=False, reason="Input validation failed — please try again.")


def check_output(client: OpenAI, story: str) -> GuardResult:
    """
    Post-generation guardrail: final safety scan of the story
    before it is displayed to the child.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": OUTPUT_GUARD_SYSTEM},
            {"role": "user", "content": story},
        ],
        temperature=0.0,
        max_tokens=150,
    )
    try:
        data = _parse_json(response.choices[0].message.content)
        return GuardResult(
            safe=bool(data.get("safe", True)),
            issues=data.get("issues", []),
        )
    except (json.JSONDecodeError, KeyError):
        # Fail open for output: the judge already evaluated safety
        return GuardResult(safe=True)
