import os
from openai import OpenAI

"""
Before submitting the assignment, describe here in a few sentences what you would
have built next if you spent 2 more hours on this project:

1. Voice narration — pipe the final story through OpenAI TTS with a slow,
   warm voice and a speed control slider so parents can match the pace to how
   drowsy the child already is.

2. Parent feedback loop — add a thumbs-up / thumbs-down button after each
   story and feed that signal back as few-shot examples in the judge's prompt,
   gradually calibrating its scoring weights to each family's preferences.

3. Illustrated cover — generate a single DALL-E prompt alongside the story
   and display a soft, dreamlike image as a cover illustration, making the
   experience feel like a real picture book.
"""

# ── System architecture (block diagram) ──────────────────────────────────────
#
#  ┌──────────────────────┐
#  │    Child Profile     │  name · age (5-10) · theme
#  │  (child_profiles.py) │  ← saved & remembered across sessions
#  └──────────┬───────────┘
#             │
#  ┌──────────▼───────────┐
#  │  Orchestrator Agent  │  GPT-3.5-turbo with tool calling (agent.py)
#  │                      │  Decides which tools to call and in what order.
#  │                      │  Control flow is LLM-driven, not hardcoded.
#  └──────────┬───────────┘
#             │ calls tools autonomously:
#    ┌────────┼────────────────┬──────────────────┐
#    │        │                │                  │
#  ┌─▼──┐  ┌──▼────────┐  ┌───▼──────┐  ┌───────▼──────┐
#  │    │  │ Classify  │  │  Story   │  │  LLM Judge   │
#  │Guar│  │ + Arc     │  │Generator │  │  (4 scores)  │
#  │rail│  │(story_gen)│  │(streaming│  │  FAIL→retry  │
#  └────┘  └───────────┘  └──────────┘  └──────────────┘
#             │ (after judge PASS or 2 retries exhausted)
#  ┌──────────▼───────────┐
#  │   Output Guardrail   │  Final content scan before the child sees it
#  │   (guardrails.py)    │
#  └──────────┬───────────┘
#             │ SAFE
#  ┌──────────▼───────────┐
#  │    Display Story     │  Streamlit UI with live tool log + judge scorecard
#  │       (app.py)       │  🌙 Sweet dreams!
#  └──────────────────────┘
#
# Run the full app:  streamlit run app.py
# ─────────────────────────────────────────────────────────────────────────────


def call_model(prompt: str, max_tokens: int = 3000, temperature: float = 0.1) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content


example_request = "A story about a girl named Alice and her best friend Bob, who happens to be a cat."


def main():
    user_input = input("What kind of story do you want to hear? ")
    response = call_model(user_input)
    print(response)


if __name__ == "__main__":
    main()
