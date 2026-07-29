from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version
from chat import (
    ROOT,
    ARTIFACTS_DIR,
    run_model_tool_loop,
    trim_history,
    safe_slug,
    write_transcript,
    now_iso,
)

load_lab_env(ROOT)

TRANSCRIPTS_DIR = ROOT / "transcripts"

st.set_page_config(page_title="Nghiên Cứu — Research Agent", layout="wide", page_icon="🔎")


# ==================================================================
# DESIGN SYSTEM — lấy cảm hứng từ answer-engine UX (Perplexity-style):
# nền giấy ấm, tiêu đề serif có tính biên tập, badge trích dẫn dạng số,
# accent teal cho trạng thái "đã có nguồn / đã xác thực".
# ==================================================================
TOKENS = {
    "bg": "#FAF8F3",
    "surface": "#FFFFFF",
    "border": "#E8E3D8",
    "text": "#1F1B16",
    "text_muted": "#6B6459",
    "accent": "#1F8A82",
    "accent_soft": "#E4F3F1",
    "warn": "#B8860B",
    "error": "#B4432F",
}

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        color: {TOKENS["text"]};
    }}
    .stApp {{ background: {TOKENS["bg"]}; }}
    section[data-testid="stSidebar"] {{
        background: {TOKENS["surface"]};
        border-right: 1px solid {TOKENS["border"]};
    }}
    #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}

    .rt-hero {{
        text-align: center;
        padding: 8vh 0 3rem 0;
    }}
    .rt-hero h1 {{
        font-family: 'Source Serif 4', serif;
        font-weight: 600;
        font-size: 2.6rem;
        letter-spacing: -0.01em;
        margin-bottom: 0.4rem;
    }}
    .rt-hero p {{
        color: {TOKENS["text_muted"]};
        font-size: 1.02rem;
    }}

    .rt-query {{
        font-family: 'Source Serif 4', serif;
        font-weight: 600;
        font-size: 1.65rem;
        line-height: 1.3;
        margin: 1.6rem 0 1rem 0;
        color: {TOKENS["text"]};
    }}

    .rt-sources-label {{
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: {TOKENS["text_muted"]};
        margin-bottom: 0.5rem;
        font-weight: 500;
    }}

    .rt-card {{
        background: {TOKENS["surface"]};
        border: 1px solid {TOKENS["border"]};
        border-radius: 10px;
        padding: 0.7rem 0.85rem;
        height: 100%;
    }}
    .rt-card-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px; height: 18px;
        border-radius: 50%;
        background: {TOKENS["accent_soft"]};
        color: {TOKENS["accent"]};
        font-size: 0.68rem;
        font-weight: 600;
        margin-right: 0.4rem;
    }}
    .rt-card-domain {{
        font-size: 0.72rem;
        color: {TOKENS["text_muted"]};
    }}
    .rt-card-title {{
        font-size: 0.85rem;
        font-weight: 500;
        margin-top: 0.25rem;
        line-height: 1.3;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }}

    .rt-answer {{
        font-size: 1.02rem;
        line-height: 1.75;
        margin-top: 0.5rem;
    }}

    .rt-status-pill {{
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 500;
        padding: 0.2rem 0.6rem;
        border-radius: 999px;
        margin-top: 0.6rem;
    }}
    .rt-status-wait {{ background: #FFF4DD; color: {TOKENS["warn"]}; }}
    .rt-status-error {{ background: #FBE7E3; color: {TOKENS["error"]}; }}

    div[data-testid="stChatInput"] textarea {{
        font-family: 'Inter', sans-serif;
    }}
    div[data-testid="stChatInput"] {{
        border-radius: 14px !important;
        border: 1px solid {TOKENS["border"]} !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}

    .rt-mono, .rt-mono pre {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
    }}

    .rt-divider {{
        border: none;
        border-top: 1px solid {TOKENS["border"]};
        margin: 2rem 0;
    }}

    .rt-followup button {{
        border-radius: 999px !important;
        border: 1px solid {TOKENS["border"]} !important;
        background: {TOKENS["surface"]} !important;
        color: {TOKENS["text"]} !important;
        font-size: 0.85rem !important;
        padding: 0.3rem 0.9rem !important;
    }}
    .rt-followup button:hover {{
        border-color: {TOKENS["accent"]} !important;
        color: {TOKENS["accent"]} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Sidebar — cấu hình + evidence kỹ thuật (vẫn giữ đủ cho eval/demo)
# ------------------------------------------------------------------
st.sidebar.markdown("### ⚙️ Cấu hình phiên")

provider_name = st.sidebar.selectbox(
    "Provider", ["openrouter", "openai", "anthropic", "gemini"], index=0
)
model_override = st.sidebar.text_input("Model override", value="", placeholder="để trống = default")
version_label = st.sidebar.text_input("Version label", value="v3")
history_window = st.sidebar.slider("History window", 0, 10, 5)
max_tool_rounds = st.sidebar.slider("Max tool rounds", 1, 8, 4)

system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
tools_path = ARTIFACTS_DIR / "tools.yaml"

if st.sidebar.button("🔄 Bắt đầu phiên mới", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ UI có thể public qua tunnel — không nhập secrets vào đây.")


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------
st.session_state.setdefault("history", [])
st.session_state.setdefault("turns", [])
st.session_state.setdefault("transcript_id", None)
st.session_state.setdefault("turn_index", 0)
st.session_state.setdefault("pending_prompt", None)


@st.cache_resource(show_spinner=False)
def get_provider(name: str):
    return make_provider(name)


def load_artifacts():
    system_prompt = system_prompt_path.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(tools_path)
    openai_tools = to_openai_tools(tool_declarations)
    artifact_version = build_artifact_version(version_label, system_prompt_path, tools_path)
    return system_prompt, tool_declarations, openai_tools, artifact_version


try:
    system_prompt, tool_declarations, openai_tools, artifact_version = load_artifacts()
except Exception as exc:
    st.error(f"Không đọc được artifacts: {exc}")
    st.stop()

try:
    provider = get_provider(provider_name)
except Exception as exc:
    st.error(f"Không khởi tạo được provider '{provider_name}': {exc}")
    st.stop()

selected_model = model_override.strip() or getattr(provider, "default_model", None)

if st.session_state.transcript_id is None:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    st.session_state.transcript_id = "_".join(
        [safe_slug(version_label), safe_slug(provider_name), timestamp]
    )
transcript_path = TRANSCRIPTS_DIR / f"{st.session_state.transcript_id}.transcript.json"

with st.sidebar.expander("📎 Evidence kỹ thuật (artifact_version / hash)"):
    st.markdown(f"**artifact_version:** `{artifact_version.artifact_version}`")
    st.code(json.dumps(artifact_version_dict(artifact_version), indent=2, ensure_ascii=False), language="json")
    st.caption(f"Transcript: `{transcript_path.name}`")

with st.sidebar.expander(f"🧰 {len(tool_declarations)} tool đã khai báo"):
    for item in tool_declarations:
        st.markdown(f"- `{item['name']}` — {item.get('description', '')}")


# ------------------------------------------------------------------
# Helpers — trích "source cards" từ tool_results, giống Perplexity
# ------------------------------------------------------------------
def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "") or url
    except Exception:
        return url


def collect_sources(round_records: list[dict]) -> list[dict]:
    sources: list[dict] = []
    for rr in round_records:
        for event in rr.get("tool_results", []):
            result = event.get("result") or {}
            for item in (result.get("items") or [])[:4]:
                sources.append(
                    {
                        "title": item.get("title") or item.get("summary", "")[:60] or event.get("tool"),
                        "url": item.get("url") or "",
                        "source": item.get("source") or domain_of(item.get("url", "")) or event.get("tool"),
                    }
                )
    return sources[:8]


def render_source_cards(sources: list[dict]) -> None:
    if not sources:
        return
    st.markdown('<div class="rt-sources-label">Nguồn</div>', unsafe_allow_html=True)
    cols = st.columns(min(4, len(sources)))
    for idx, src in enumerate(sources):
        with cols[idx % len(cols)]:
            title = (src["title"] or "")[:90]
            link_open = f'<a href="{src["url"]}" target="_blank" style="text-decoration:none;color:inherit;">' if src["url"] else "<div>"
            link_close = "</a>" if src["url"] else "</div>"
            st.markdown(
                f"""
                <div class="rt-card">
                  {link_open}
                    <span class="rt-card-badge">{idx + 1}</span>
                    <span class="rt-card-domain">{src["source"]}</span>
                    <div class="rt-card-title">{title}</div>
                  {link_close}
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_technical_panel(turn: dict) -> None:
    with st.expander("🔧 Chi tiết kỹ thuật (tool calls · args · raw result) — evidence cho eval"):
        for rr in turn.get("rounds", []):
            st.markdown(f"**Round {rr['round']}**")
            for event in rr.get("tool_results", []):
                result = event.get("result", {})
                is_error = isinstance(result, dict) and result.get("error")
                icon = "❌" if is_error else "✅"
                st.markdown(f"{icon} `{event.get('tool')}`")
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("args")
                    st.json(event.get("args", {}))
                with c2:
                    st.caption("result")
                    st.json(result)


FOLLOWUPS = [
    "Tóm tắt ngắn gọn hơn giúp mình",
    "Có nguồn nào khác không?",
    "Tìm thêm tin liên quan hôm nay",
]


def render_turn(turn: dict, key_prefix: str) -> None:
    st.markdown(f'<div class="rt-query">{turn["user"]}</div>', unsafe_allow_html=True)

    sources = collect_sources(turn.get("rounds", []))
    render_source_cards(sources)

    st.markdown(f'<div class="rt-answer">{turn.get("assistant_text") or ""}</div>', unsafe_allow_html=True)

    status = turn.get("status")
    if status == "waiting_for_user":
        st.markdown('<span class="rt-status-pill rt-status-wait">⏸️ Đang chờ bạn bổ sung thông tin</span>', unsafe_allow_html=True)
    elif status == "provider_error":
        st.markdown(f'<span class="rt-status-pill rt-status-error">❌ Provider error: {turn.get("error")}</span>', unsafe_allow_html=True)
    elif status == "max_tool_rounds":
        st.markdown('<span class="rt-status-pill rt-status-wait">⏹️ Dừng vì chạm giới hạn tool rounds</span>', unsafe_allow_html=True)

    render_technical_panel(turn)

    st.markdown('<div class="rt-followup">', unsafe_allow_html=True)
    cols = st.columns(len(FOLLOWUPS))
    for i, suggestion in enumerate(FOLLOWUPS):
        with cols[i]:
            if st.button(suggestion, key=f"{key_prefix}-fu-{i}"):
                st.session_state.pending_prompt = suggestion
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<hr class="rt-divider">', unsafe_allow_html=True)


def process_turn(user_text: str) -> None:
    st.session_state.turn_index += 1
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, history_window),
        {"role": "user", "content": user_text},
    ]

    turn_record: dict = {
        "turn_index": st.session_state.turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    with st.spinner("Đang tìm và tổng hợp câu trả lời..."):
        try:
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=model_override.strip() or None,
                max_tool_rounds=max_tool_rounds,
            )
            turn_record.update(result)
            assistant_text = result["assistant_text"]
            st.session_state.history.append({"role": "user", "content": user_text})
            st.session_state.history.append({"role": "assistant", "content": assistant_text})
        except Exception as exc:
            turn_record.update({"status": "provider_error", "error": f"{type(exc).__name__}: {str(exc)}"})

    turn_record["ended_at"] = now_iso()
    st.session_state.turns.append(turn_record)

    transcript = {
        "transcript_id": st.session_state.transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": selected_model,
        "system_prompt": str(system_prompt_path),
        "tools": str(tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": st.session_state.turns[0]["started_at"],
        "turns": st.session_state.turns,
    }
    write_transcript(transcript_path, transcript)


# ------------------------------------------------------------------
# Main layout
# ------------------------------------------------------------------
main_col = st.columns([1, 6, 1])[1]

with main_col:
    if not st.session_state.turns:
        st.markdown(
            """
            <div class="rt-hero">
                <h1>🔎 Hỏi bất cứ điều gì</h1>
                <p>Research Agent tra cứu web, mạng xã hội và tài liệu để trả lời có nguồn trích dẫn.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for idx, turn in enumerate(st.session_state.turns):
            render_turn(turn, key_prefix=f"t{idx}")

    # Xử lý follow-up được bấm ở lượt trước (chạy trước khi vẽ ô input)
    if st.session_state.pending_prompt:
        prompt = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        process_turn(prompt)
        st.rerun()

    user_text = st.chat_input("Nhập câu hỏi nghiên cứu của bạn...")
    if user_text:
        process_turn(user_text)
        st.rerun()