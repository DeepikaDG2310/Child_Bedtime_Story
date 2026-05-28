import streamlit as st
import os
from openai import OpenAI, AuthenticationError

from child_profiles import ChildProfile, load_profiles, delete_profile
from config import STORY_CATEGORIES
from agent import run_story_agent
from tools import TOOL_DISPLAY
from dotenv import load_dotenv

#Load environment variables
load_dotenv()
#os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
api_key = os.getenv("OPENAI_API_KEY")



st.set_page_config(
    page_title="Bedtime Story Magic",
    page_icon="🌙",
    layout="centered",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.header("⚙️ Settings")

    st.markdown("---")
    st.header("🏗️ System Architecture")
    st.markdown(
        """
```
┌─────────────────────┐
│    Child Profile    │
│  name · age (5-10)  │◄── saved & remembered
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Orchestrator Agent │◄── OpenAI Model
│  decides tool order │    with tool calling
└──────────┬──────────┘
     calls tools dynamically:
  ┌────────┼──────────────┐
  │        │              │
┌─▼──┐ ┌───▼───┐ ┌───────▼──┐
│    │ │Classif│ │  Story   │
│Guard│ │+ Arc  │ │Generator │
│rail│ │       │ │(streaming)│
└────┘ └───────┘ └──────────┘
           │
    ┌──────▼──────┐
    │  LLM Judge  │◄── FAIL → retry (max 2x)
    │ 4 scores    │    PASS → continue
    └──────┬──────┘
           │
  ┌────────▼────────┐
  │ Output Guardrail│
  └────────┬────────┘
           │
  ┌────────▼────────┐
  │  Display Story  │
  │       🌙        │
  └─────────────────┘
```
"""
    )
    st.caption("OpenAI Model · tool calling · LLM judge · dual guardrails")



st.title("Magical Bedtime Story")
st.markdown(
    "<p style='text-align:center; opacity:0.7;'>"
    "Personalized bedtime stories just for your little kids"
    "</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

st.subheader("👶 Child Profile")

profiles = load_profiles()
profile_names = list(profiles.keys())

NEW_CHILD = "➕ New child"
selected_option = st.selectbox(
    "Select profile", [NEW_CHILD] + profile_names, label_visibility="collapsed"
)

col1, col2 = st.columns(2)
if selected_option == NEW_CHILD:
    with col1:
        child_name = st.text_input("Child's name", placeholder="e.g. Emma")
    with col2:
        child_age = st.number_input("Age", min_value=5, max_value=10, value=7, step=1)
    default_theme = "✨ Surprise me!"
else:
    profile = profiles[selected_option]
    with col1:
        child_name = st.text_input("Child's name", value=profile.name)
    with col2:
        child_age = st.number_input("Age", min_value=5, max_value=10, value=profile.age, step=1)
    default_theme = profile.last_theme
    if st.button(f"🗑️ Delete '{selected_option}' profile"):
        delete_profile(selected_option)
        st.success(f"Profile for {selected_option} deleted.")
        st.rerun()

st.markdown("---")
st.subheader("📖 Story Settings")

theme_options = ["✨ Surprise me!"] + list(STORY_CATEGORIES.keys())
default_index = theme_options.index(default_theme) if default_theme in theme_options else 0
selected_theme = st.selectbox("Story theme", options=theme_options, index=default_index)

custom_request = st.text_area(
    "You can mention more details here for the story (optional)",
    placeholder="e.g. A little dragon who is afraid of fire but discovers a special gift",
    max_chars=200,
    height=80,
)

generate_btn = st.button(
    "🌙 Story Time! ✨",
    type="primary",
    use_container_width=True,
    )


if generate_btn:
    client = OpenAI()

    theme_desc = f"the theme of {selected_theme}" if selected_theme != "✨ Surprise me!" else ""
    custom_desc = custom_request.strip()

    if theme_desc and custom_desc:
        story_request = f"Generate a bedtime story for kids using the theme :{theme_desc}: {custom_desc}"
    elif theme_desc:
        story_request = f"A bedtime story in the theme of {theme_desc}"
    elif custom_desc:
        story_request = custom_desc
    else:
        story_request = "a magical bedtime adventure"

    try:
        
        st.markdown("Agent Activity")
        activity_log = st.empty()
        tool_steps: list[str] = []

        def on_tool_start(name: str) -> None:
            label = TOOL_DISPLAY.get(name, name)
            tool_steps.append(label)
            activity_log.markdown("\n".join(f"- {s}" for s in tool_steps))

        
        st.markdown("#### 📖 Story")
        story_placeholder = st.empty()

        def stream_callback(accumulated: str) -> None:
            story_placeholder.markdown(f"> {accumulated}▌")

       #main agent call
        with st.spinner("Agent is working..."):
            result = run_story_agent(
                client=client,
                child_name=child_name,
                age=int(child_age),
                story_request=story_request,
                on_tool_start=on_tool_start,
                stream_callback=stream_callback,
            )

        
        if result.story:
            story_placeholder.markdown(f"> {result.story}")
        else:
            story_placeholder.empty()

        
        if not result.input_safe:
            st.error("⛔ Request blocked by input safety guardrail.")
            st.stop()

        if not result.story:
            st.error("The system was unable to generate a story. Please try again.")
            st.stop()

        
        st.markdown("---")
        v = result.judge_verdict

        with st.expander("📊 Quality & Safety Report", expanded=True):
            if v:
                verdict_color = "green" if v.passed else "orange"
                verdict_label = "✅ PASSED" if v.passed else "⚠️ BEST EFFORT"
                st.markdown(
                    f"**Judge Verdict:** :{verdict_color}[{verdict_label}]"
                    f"   avg **{v.average_score}/10** · {result.story_attempts} attempt(s)"
                )
                cols = st.columns(4)
                for col, (label, score) in zip(cols, v.scores_dict.items()):
                    col.metric(label=label, value=f"{score}/10",
                               delta_color="normal" if score >= 7 else "inverse")
                if v.flags:
                    st.warning(f"Flags: {', '.join(v.flags)}")
            else:
                st.info("Judge did not run.")

            if result.output_safe:
                st.success("✓ Output guardrail: no safety issues detected")
            else:
                st.error("⚠️ Output guardrail flagged content — review before sharing")

        with st.expander("🔧 Agent Tool Log", expanded=False):
            for entry in result.tool_log:
                st.markdown(f"**{TOOL_DISPLAY.get(entry['tool'], entry['tool'])}**")
                st.json({"args": entry["args"], "result": entry["result"]})

        st.markdown(
            f"<div style='text-align:center; padding:12px; font-size:1.2em;'>"
            f"🌙 Sweet dreams little, {child_name}! ✨"
            f"</div>",
            unsafe_allow_html=True,
        )

    except AuthenticationError:
        st.error("System Error. Please check contact admin and try again.")
    except Exception as exc:
        st.error(f"Something went wrong: {exc}")
