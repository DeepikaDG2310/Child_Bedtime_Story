import json
from dataclasses import dataclass, field
from openai import OpenAI

from llm_judge import JudgeVerdict
from tools import TOOL_SCHEMAS, execute_tool
from config import MODEL, AGENT_SYSTEM_PROMPT


MAX_ITERATIONS = 20   


@dataclass
class AgentResult:
    story: str = ""
    arc: str = ""
    category: str = ""
    judge_verdict: JudgeVerdict | None = None
    input_safe: bool = True
    output_safe: bool = True
    story_attempts: int = 0
    tool_log: list[dict] = field(default_factory=list) 


def run_story_agent(
    client: OpenAI,
    child_name: str,
    age: int,
    story_request: str,
    on_tool_start=None, 
    stream_callback=None,
) -> AgentResult:
    """
    Run the agentic loop until the agent signals it is done (finish_reason == "stop")
    or MAX_ITERATIONS is reached.

    The agent calls tools autonomously. Tools write their key outputs into the
    shared AgentResult object so the caller can access structured data without
    parsing the agent's prose.
    """
    result = AgentResult()

    messages: list[dict] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Child: {child_name}, age {age}\nStory request: {story_request}",
        },
    ]

    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.1,
        )

        msg = response.choices[0].message

        
        assistant_turn: dict = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            assistant_turn["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_turn)

            
        if response.choices[0].finish_reason == "stop":
            break

        
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                if on_tool_start:
                    on_tool_start(name)

                tool_result = execute_tool(
                    name,
                    args,
                    client=client,
                    agent_result=result,
                    
                    stream_callback=stream_callback if name == "generate_story" else None,
                )

                result.tool_log.append({"tool": name, "args": args, "result": tool_result})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result),
                })

    return result
