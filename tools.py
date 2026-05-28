import json
from openai import OpenAI

from guardrails import check_input, check_output
from story_generator import classify_story as _classify, build_story_arc as _arc
from story_generator import generate_story_stream, generate_story_full
from llm_judge import judge_story as _judge
from child_profiles import load_profiles, save_profile, ChildProfile

# Streamlit activity log
TOOL_DISPLAY = {
    "check_input_safety":  "🛡️  Checking input safety",
    "load_child_profile":  "👶  Loading child profile",
    "classify_story":      "🏷️  Classifying story theme",
    "build_story_arc":     "📋  Building story arc",
    "generate_story":      "✍️  Generating story",
    "judge_story":         "⚖️  Judging story quality",
    "check_output_safety": "🛡️  Checking output safety",
    "save_child_profile":  "💾  Saving child profile",
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "check_input_safety",
            "description": (
                "Validate that the story request contains no inappropriate content "
                "before any generation. ALWAYS call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "story_request": {"type": "string", "description": "The raw story request"},
                    "child_name":    {"type": "string", "description": "The child's name"},
                },
                "required": ["story_request", "child_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_child_profile",
            "description": "Load a saved child profile to retrieve their age and last theme preference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_name": {"type": "string"},
                },
                "required": ["child_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_story",
            "description": "Classify the request into the best story category and produce a refined theme description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "story_request": {"type": "string"},
                },
                "required": ["story_request"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_story_arc",
            "description": "Build a 3-act story arc scaffold before writing the full story. Improves narrative coherence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_name": {"type": "string"},
                    "age":        {"type": "integer", "description": "Child's age, 5-10"},
                    "category":   {"type": "string",  "description": "Category from classify_story"},
                    "theme":      {"type": "string",  "description": "Refined theme from classify_story"},
                },
                "required": ["child_name", "age", "category", "theme"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_story",
            "description": (
                "Generate the full bedtime story using the arc. "
                "On a retry after judge feedback, pass that feedback in the feedback field."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "child_name": {"type": "string"},
                    "age":        {"type": "integer"},
                    "category":   {"type": "string"},
                    "arc":        {"type": "string", "description": "3-act arc from build_story_arc"},
                    "feedback":   {"type": "string", "description": "Judge feedback for retry; empty string on first attempt"},
                },
                "required": ["child_name", "age", "category", "arc", "feedback"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "judge_story",
            "description": (
                "Evaluate the story on 4 dimensions (1-10 each): "
                "age_appropriateness, safety_score, story_quality, calming_effect. "
                "ALL must be >= 7 to pass."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "story":      {"type": "string", "description": "Full story text to evaluate"},
                    "child_name": {"type": "string"},
                    "age":        {"type": "integer"},
                },
                "required": ["story", "child_name", "age"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_output_safety",
            "description": "Final safety scan of the generated story before it is shown to the child. Always call before finishing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "story": {"type": "string"},
                },
                "required": ["story"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_child_profile",
            "description": "Persist the child's profile (name, age, theme used) so preferences are remembered next session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "child_name": {"type": "string"},
                    "age":        {"type": "integer"},
                    "last_theme": {"type": "string", "description": "The theme chosen this session"},
                },
                "required": ["child_name", "age", "last_theme"],
            },
        },
    },
]



def _tool_check_input_safety(client: OpenAI, story_request: str, child_name: str, **ctx) -> dict:
    result = check_input(client, story_request, child_name)
    if ctx.get("agent_result") is not None:
        ctx["agent_result"].input_safe = result.safe
    return {"safe": result.safe, "reason": result.reason}


def _tool_load_child_profile(client: OpenAI, child_name: str, **ctx) -> dict:
    profiles = load_profiles()
    if child_name in profiles:
        p = profiles[child_name]
        return {"found": True, "age": p.age, "last_theme": p.last_theme}
    return {"found": False}


def _tool_classify_story(client: OpenAI, story_request: str, **ctx) -> dict:
    category, refined_theme = _classify(client, story_request)
    if ctx.get("agent_result") is not None:
        ctx["agent_result"].category = category
    return {"category": category, "refined_theme": refined_theme}


def _tool_build_story_arc(
    client: OpenAI, child_name: str, age: int, category: str, theme: str, **ctx
) -> dict:
    arc = _arc(client, child_name, age, category, theme)
    if ctx.get("agent_result") is not None:
        ctx["agent_result"].arc = arc
    return {"arc": arc}


def _tool_generate_story(
    client: OpenAI,
    child_name: str,
    age: int,
    category: str,
    arc: str,
    feedback: str = "",
    **ctx,
) -> dict:
    agent_result = ctx.get("agent_result")
    stream_cb    = ctx.get("stream_callback")

    if agent_result is not None:
        agent_result.story_attempts += 1

    if stream_cb:
        
        story_text = ""
        for chunk in generate_story_stream(client, child_name, age, category, arc, feedback):
            story_text += chunk
            stream_cb(story_text)   
    else:
        story_text = generate_story_full(client, child_name, age, category, arc, feedback)

    if agent_result is not None:
        agent_result.story = story_text

    
    return {"story_length": len(story_text), "preview": story_text[:120] + "..."}


def _tool_judge_story(client: OpenAI, story: str, child_name: str, age: int, **ctx) -> dict:
    verdict = _judge(client, story, age, child_name)
    if ctx.get("agent_result") is not None:
        ctx["agent_result"].judge_verdict = verdict
    return {
        "age_appropriateness": verdict.age_appropriateness,
        "safety_score":        verdict.safety_score,
        "story_quality":       verdict.story_quality,
        "calming_effect":      verdict.calming_effect,
        "verdict":             verdict.verdict,
        "feedback":            verdict.feedback,
        "flags":               verdict.flags,
        "passed":              verdict.passed,
    }


def _tool_check_output_safety(client: OpenAI, story: str, **ctx) -> dict:
    result = check_output(client, story)
    if ctx.get("agent_result") is not None:
        ctx["agent_result"].output_safe = result.safe
    return {"safe": result.safe, "issues": result.issues}


def _tool_save_child_profile(
    client: OpenAI, child_name: str, age: int, last_theme: str, **ctx
) -> dict:
    save_profile(ChildProfile(name=child_name, age=age, last_theme=last_theme))
    return {"saved": True}



_REGISTRY = {
    "check_input_safety":  _tool_check_input_safety,
    "load_child_profile":  _tool_load_child_profile,
    "classify_story":      _tool_classify_story,
    "build_story_arc":     _tool_build_story_arc,
    "generate_story":      _tool_generate_story,
    "judge_story":         _tool_judge_story,
    "check_output_safety": _tool_check_output_safety,
    "save_child_profile":  _tool_save_child_profile,
}


def execute_tool(name: str, args: dict, client: OpenAI, **ctx) -> dict:
    """Dispatch a tool call by name. ctx is passed through to the implementation."""
    fn = _REGISTRY.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(client=client, **args, **ctx)
    except Exception as exc:
        return {"error": str(exc)}
