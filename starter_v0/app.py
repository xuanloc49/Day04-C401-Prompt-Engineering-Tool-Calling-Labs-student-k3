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

st.set_page_config(page_title="chaotic — Research Agent", layout="wide", page_icon="🟣")


# ==================================================================
# BRAND — "chaotic":
# Mark: 6 cánh gradient tím xoay quanh lõi trắng, gợi ống kính/aperture.
# ==================================================================
LOGO_MARK_SVG = """
<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">
  <defs>
    <linearGradient id="chaoticGrad{uid}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#A78BFA"/>
      <stop offset="55%" stop-color="#7C3AED"/>
      <stop offset="100%" stop-color="#5B21B6"/>
    </linearGradient>
  </defs>
  <g fill="url(#chaoticGrad{uid})">
    <g transform="translate(32,32)">
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5"/>
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5" transform="rotate(60)"/>
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5" transform="rotate(120)"/>
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5" transform="rotate(180)"/>
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5" transform="rotate(240)"/>
      <ellipse cx="0" cy="-13.5" rx="7.2" ry="13.5" transform="rotate(300)"/>
    </g>
  </g>
  <circle cx="32" cy="32" r="9.5" fill="#FFFFFF"/>
  <circle cx="32" cy="32" r="9.5" fill="none" stroke="url(#chaoticGrad{uid})" stroke-width="2"/>
</svg>
"""


def logo_mark(size: int = 40, uid: str = "a") -> str:
    return LOGO_MARK_SVG.format(size=size, uid=uid)


# ==================================================================
# DESIGN SYSTEM — nền trắng / tím, gradient nhẹ ở card (kiểu answer-engine
# / dev-platform chuyên nghiệp: You.com, Perplexity, Linear). Tiêu đề vẫn
# giữ serif biên tập để giữ cảm giác "nghiên cứu", accent chuyển sang tím
# thương hiệu "chaotic".
# ==================================================================
TOKENS = {
    "bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "sidebar_bg": "#FBFAFE",
    "border": "#E7E3F6",
    "text": "#1A1523",
    "text_muted": "#6B647A",
    "accent": "#7C3AED",
    "accent_dark": "#5B21B6",
    "accent_soft": "#F1EDFE",
    "gradient_start": "#EDE9FE",
    "gradient_end": "#F5F3FF",
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
        background: {TOKENS["sidebar_bg"]};
        border-right: 1px solid {TOKENS["border"]};
    }}
    #MainMenu, footer {{ display: none; }}
    button[kind="header"] {{ visibility: visible; }}

    .rt-brand {{
        display: flex;
        align-items: center;
        gap: 0.55rem;
        padding: 0.2rem 0 1rem 0;
    }}
    .rt-brand-name {{
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.3rem;
        letter-spacing: -0.02em;
        color: {TOKENS["text"]};
    }}
    .rt-brand-tagline {{
        font-size: 0.72rem;
        color: {TOKENS["text_muted"]};
        margin-top: -0.15rem;
    }}

    .rt-hero {{
        text-align: center;
        padding: 7vh 0 3rem 0;
    }}
    .rt-hero-mark {{
        display: flex;
        justify-content: center;
        margin-bottom: 1.1rem;
    }}
    .rt-hero h1 {{
        font-family: 'Source Serif 4', serif;
        font-weight: 600;
        font-size: 2.6rem;
        letter-spacing: -0.01em;
        margin-bottom: 0.4rem;
        background: linear-gradient(90deg, {TOKENS["text"]} 0%, {TOKENS["accent"]} 120%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
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
        background: linear-gradient(160deg, {TOKENS["gradient_start"]} 0%, {TOKENS["surface"]} 55%);
        border: 1px solid {TOKENS["border"]};
        border-radius: 12px;
        padding: 0.75rem 0.9rem;
        height: 100%;
        transition: border-color 0.15s ease, transform 0.15s ease;
    }}
    .rt-card:hover {{
        border-color: {TOKENS["accent"]};
        transform: translateY(-1px);
    }}
    .rt-card-badge {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px; height: 18px;
        border-radius: 50%;
        background: {TOKENS["accent"]};
        color: #FFFFFF;
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
        box-shadow: 0 1px 3px rgba(124, 58, 237, 0.06);
    }}
    div[data-testid="stChatInput"]:focus-within {{
        border-color: {TOKENS["accent"]} !important;
        box-shadow: 0 0 0 3px {TOKENS["accent_soft"]} !important;
    }}

    .stButton button[kind="secondary"], .stButton button {{
        border-radius: 10px;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        background: {TOKENS["accent"]} !important;
        color: #FFFFFF !important;
        border: none !important;
    }}
    section[data-testid="stSidebar"] .stButton button:hover {{
        background: {TOKENS["accent_dark"]} !important;
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
# Sidebar — brand + cấu hình + evidence kỹ thuật (vẫn giữ đủ cho eval/demo)
# ------------------------------------------------------------------
st.sidebar.markdown("### 🟣 chaotic")
st.sidebar.caption("research, in focus")

st.sidebar.markdown("##### ⚙️ Cấu hình phiên")

provider_name = st.sidebar.selectbox(
    "Provider", ["openrouter", "openai", "anthropic", "gemini"], index=0
)
model_override = st.sidebar.text_input("Model override", value="", placeholder="để trống = default")
version_label = st.sidebar.text_input("Version label", value="v3")
history_window = st.sidebar.slider("History window", 0, 10, 5)
max_tool_rounds = st.sidebar.slider("Max tool rounds", 1, 8, 4)

system_prompt_path = ARTIFACTS_DIR / "system_prompt.md"
tools_path = ARTIFACTS_DIR / "tools.yaml"

if st.sidebar.button("🔄 Bắt đầu phiên mới"):
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
    st.caption("Nguồn")
    cols = st.columns(min(4, len(sources)))
    for idx, src in enumerate(sources):
        with cols[idx % len(cols)]:
            title = (src["title"] or "")[:90]
            container = st.container(border=True)
            with container:
                st.markdown(f"**{idx + 1}. {src['source']}**")
                if src.get("url"):
                    st.link_button("Xem nguồn", src["url"])
                else:
                    st.write(title)


def collect_tool_errors(round_records: list[dict]) -> list[str]:
    """README: 'tool_results có error phải được review thủ công; PASS routing
    không có nghĩa tool chạy đúng.' Banner này bắt buộc phải hiện ngay, không
    được giấu trong expander, để không ai bỏ sót lỗi thực thi tool."""
    errors: list[str] = []
    for rr in round_records:
        for event in rr.get("tool_results", []):
            result = event.get("result") or {}
            if isinstance(result, dict) and result.get("error"):
                errors.append(f"`{event.get('tool')}` → {result.get('error')}: {result.get('message', '')}")
    return errors


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
    with st.chat_message("user"):
        st.markdown(turn.get("user") or "")

    sources = collect_sources(turn.get("rounds", []))
    if sources:
        render_source_cards(sources)

    with st.chat_message("assistant"):
        st.markdown(turn.get("assistant_text") or "")

    tool_errors = collect_tool_errors(turn.get("rounds", []))
    if tool_errors:
        st.warning("Tool routing đúng nhưng thực thi lỗi — cần review thủ công")
        for err in tool_errors:
            st.caption(f"🔴 {err}")

    status = turn.get("status")
    if status == "waiting_for_user":
        st.info("⏸️ Đang chờ bạn bổ sung thông tin")
    elif status == "provider_error":
        st.error(f"❌ Provider error: {turn.get('error')}")
    elif status == "max_tool_rounds":
        st.info("⏹️ Dừng vì chạm giới hạn tool rounds")

    render_technical_panel(turn)

    cols = st.columns(len(FOLLOWUPS))
    for i, suggestion in enumerate(FOLLOWUPS):
        with cols[i]:
            if st.button(suggestion, key=f"{key_prefix}-fu-{i}"):
                st.session_state.pending_prompt = suggestion
                st.rerun()

    st.markdown("---")


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
            f"""
            <div class="rt-hero">
                <div class="rt-hero-mark">{logo_mark(56, uid="hero")}</div>
                <h1>Hỏi bất cứ điều gì</h1>
                <p>chaotic tra cứu web, mạng xã hội và tài liệu để trả lời có nguồn trích dẫn rõ ràng.</p>
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
