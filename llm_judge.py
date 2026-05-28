import json
from dataclasses import dataclass
from openai import OpenAI
from config import MODEL, JUDGE_PASS_THRESHOLD, JUDGE_SYSTEM_TEMPLATE



@dataclass
class JudgeVerdict:
    age_appropriateness: int
    safety_score: int
    story_quality: int
    calming_effect: int
    verdict: str          
    feedback: str         
    flags: list[str]      
    attempts_used: int = 0

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

    @property
    def average_score(self) -> float:
        scores = [
            self.age_appropriateness,
            self.safety_score,
            self.story_quality,
            self.calming_effect,
        ]
        return round(sum(scores) / len(scores), 1)

    @property
    def scores_dict(self) -> dict[str, int]:
        return {
            "Age Fit": self.age_appropriateness,
            "Safety": self.safety_score,
            "Story Quality": self.story_quality,
            "Calming Effect": self.calming_effect,
        }


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    return json.loads(text)


def judge_story(client: OpenAI, story: str, age: int, name: str) -> JudgeVerdict:

    system_prompt = JUDGE_SYSTEM_TEMPLATE.format(age=age)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Evaluate this bedtime story for {name} (age {age}):\n\n{story}"},
        ],
        temperature=0.1,  
        max_tokens=320,
    )
    raw = response.choices[0].message.content
    try:
        data = _parse_json(raw)
        scores = [
            int(data.get("age_appropriateness", 0)),
            int(data.get("safety_score", 0)),
            int(data.get("story_quality", 0)),
            int(data.get("calming_effect", 0)),
        ]
        
        all_pass = all(s >= JUDGE_PASS_THRESHOLD for s in scores)
        verdict = "PASS" if all_pass else "FAIL"

        return JudgeVerdict(
            age_appropriateness=scores[0],
            safety_score=scores[1],
            story_quality=scores[2],
            calming_effect=scores[3],
            verdict=verdict,
            feedback=data.get("feedback", ""),
            flags=data.get("flags", []),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        
        return JudgeVerdict(
            age_appropriateness=0,
            safety_score=0,
            story_quality=0,
            calming_effect=0,
            verdict="FAIL",
            feedback="Judge could not parse the story. Please regenerate.",
            flags=["parse_error"],
        )
