import json
from typing import Generator
from openai import OpenAI
from config import (
    MODEL,
    STORY_CATEGORIES,
    SAFETY_RULES,
    get_age_profile,
    STORY_SYSTEM_TEMPLATE,
    ARC_PROMPT_TEMPLATE,
    CLASSIFY_PROMPT_TEMPLATE,
)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    return json.loads(text)


def classify_story(client: OpenAI, user_request: str) -> tuple[str, str]:
    categories_list = "\n".join(f"- {k}: {v}" for k, v in STORY_CATEGORIES.items())
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        request=user_request,
        categories=categories_list,
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=150,
    )
    try:
        data = _parse_json(response.choices[0].message.content)
        return data.get("category", "Fantasy & Magic"), data.get("refined_theme", user_request)
    except (json.JSONDecodeError, KeyError):
        return "Fantasy & Magic", user_request


def build_story_arc(client: OpenAI, name: str, age: int, category: str, theme: str) -> str:
    
    profile = get_age_profile(age)
    prompt = ARC_PROMPT_TEMPLATE.format(
        name=name,
        age=age,
        category=category,
        theme=theme,
        tension=profile["tension"],
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=220,
    )
    return response.choices[0].message.content.strip()


def _build_messages(name: str, age: int, category: str, arc: str, feedback: str) -> list[dict]:
    profile = get_age_profile(age)
    system = STORY_SYSTEM_TEMPLATE.format(
        name=name,
        age=age,
        category=category,
        arc=arc,
        vocab=profile["vocab"],
        max_words=profile["max_words"],
        tension=profile["tension"],
        elements=profile["elements"],
        ending=profile["ending"],
        safety_rules=SAFETY_RULES,
    )
    messages = [{"role": "system", "content": system}]

    if feedback:
        user_msg = (
            f"The previous story did not meet quality standards. "
            f"Please rewrite it addressing this specific feedback:\n\n{feedback}"
        )
    else:
        user_msg = f"Tell {name} their bedtime story now."

    messages.append({"role": "user", "content": user_msg})
    return messages


def generate_story_stream(
    client: OpenAI, name: str, age: int, category: str, arc: str, feedback: str = ""
) -> Generator[str, None, None]:
   
    messages = _build_messages(name, age, category, arc, feedback)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.85,
        max_tokens=900,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def generate_story_full(
    client: OpenAI, name: str, age: int, category: str, arc: str, feedback: str = ""
) -> str:
    
    return "".join(generate_story_stream(client, name, age, category, arc, feedback))
