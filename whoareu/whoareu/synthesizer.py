"""LLM synthesis module — generates IDENTITY.md and SOUL.md sequentially."""

from __future__ import annotations

import re

import litellm

from llmkit import LLMConfig
from whoareu.models import AgentSpec, GeneratedFiles

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIELD_LABELS: dict[str, str] = {
    "name": "名字",
    "creature": "物种/类型",
    "emoji": "签名 Emoji",
    "vibe_keywords": "气质关键词",
    "personality": "性格描述",
    "communication_style": "说话风格",
    "opinionated": "是否有主见",
    "humor_style": "幽默风格",
    "group_chat_style": "群聊风格",
    "proactivity": "主动性",
    "safety_level": "安全等级",
    "heartbeat_tasks": "定时任务",
    "external_action_policy": "外部操作策略",
    "language": "主要语言",
    "reference_character": "参考角色",
    "template_base": "基础模板",
    "extra_instructions": "额外指令",
}

_CODE_FENCE_RE = re.compile(
    r"^\s*```(?:markdown|md)?\s*\n(.*?)\n\s*```\s*$",
    re.DOTALL,
)


def _strip_code_fences(content: str) -> str:
    """Remove wrapping ```markdown fences if the LLM added them."""
    match = _CODE_FENCE_RE.match(content.strip())
    if match:
        return match.group(1).strip()
    return content.strip()


def _build_spec_description(spec: AgentSpec) -> str:
    """Convert *AgentSpec* to a human-readable text block for the LLM."""
    lines: list[str] = []
    for field_name, label in _FIELD_LABELS.items():
        value = getattr(spec, field_name)
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, list):
            lines.append(f"- {label}: {', '.join(value)}")
        elif isinstance(value, bool):
            lines.append(f"- {label}: {'是' if value else '否'}")
        else:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# System prompts (Chinese, per PLAN.md)
# ---------------------------------------------------------------------------

_IDENTITY_SYSTEM = """\
你是一个 AI Agent 人格设计师。你的任务是根据用户提供的 Agent 描述，生成一份 IDENTITY.md 文件。

IDENTITY.md 定义了 Agent 的自我认知，是最简洁的身份卡片。

## 必须包含的字段（用 Markdown 标题 + 内容格式）

- **Name** — Agent 的名字
- **Creature** — 物种或类型设定（如：赛博幽灵、AI 管家、数字精灵）
- **Vibe** — 气质关键词（2-4 个词）
- **Emoji** — 签名 Emoji

## 可选字段（仅在用户描述中有相关信息时才生成）

- **Avatar** — 头像描述
- **Origin** — 来历/背景故事（一两句话）
- **Catchphrase** — 口头禅

## 要求

1. 输出纯 Markdown，不要用代码块包裹。
2. 保持简洁、有个性、不啰嗦。
3. 如果用户没有提供某个必填字段的信息，请根据整体描述合理推断。
4. 用用户指定的语言书写内容（默认中文）。
"""

_SOUL_SYSTEM = """\
你是一个 AI Agent 人格设计师。你的任务是根据用户提供的 Agent 描述和已生成的 IDENTITY.md，\
生成一份 SOUL.md 文件。

SOUL.md 定义了 Agent 的性格内核——价值观、边界、语气和持续性规则。

## 必须包含的 Section

- **Core Truths** — 核心价值观和行为原则（3-6 条）
- **Boundaries** — 绝对不做的事（安全边界 + 用户指定的禁忌）
- **Vibe** — 整体语气描述（一段话，描述说话风格和情感基调）
- **Continuity** — 记忆和持续性规则（如何保持跨会话一致性）

## 可选 Section（根据描述自主决定是否生成）

- **Language** — 语言偏好
- **Humor** — 幽默风格
- **Expertise** — 专业领域
- **Emotional Range** — 情感表达方式

## 要求

1. 输出纯 Markdown，不要用代码块包裹。
2. 性格必须与 IDENTITY.md 中的身份一致——语气、价值观要匹配。
3. Core Truths 要具体、可执行，不要空泛的口号。
4. Boundaries 要明确，包含默认安全边界（不泄露用户隐私、不执行危险操作）。
5. 用用户指定的语言书写内容（默认中文）。
"""



# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------


async def _llm_call(
    system: str,
    user: str,
    llm: LLMConfig,
) -> str:
    """Send a chat completion request and return the stripped content."""
    kwargs = llm.to_litellm_kwargs()
    kwargs.update({
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout": 120,
        "num_retries": 2,
    })
    response = await litellm.acompletion(**kwargs)
    if not response.choices:
        raise RuntimeError("LLM returned empty choices list")
    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("LLM returned None content (possibly content-filtered)")
    return _strip_code_fences(content)


# ---------------------------------------------------------------------------
# Individual generators
# ---------------------------------------------------------------------------


async def _generate_identity(spec: AgentSpec, llm: LLMConfig) -> str:
    """Generate IDENTITY.md from *spec*."""
    user_prompt = (
        "请根据以下 Agent 描述生成 IDENTITY.md：\n\n"
        f"{_build_spec_description(spec)}"
    )
    return await _llm_call(_IDENTITY_SYSTEM, user_prompt, llm)


async def _generate_soul(
    spec: AgentSpec,
    identity_md: str,
    llm: LLMConfig,
) -> str:
    """Generate SOUL.md, informed by the already-generated IDENTITY.md."""
    user_prompt = (
        "以下是已生成的 IDENTITY.md：\n\n"
        f"{identity_md}\n\n"
        "---\n\n"
        "以下是 Agent 的完整描述：\n\n"
        f"{_build_spec_description(spec)}\n\n"
        "请根据以上信息生成 SOUL.md。"
    )
    return await _llm_call(_SOUL_SYSTEM, user_prompt, llm)




# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def synthesize(
    spec: AgentSpec,
    *,
    llm: LLMConfig | None = None,
) -> GeneratedFiles:
    """Generate IDENTITY.md and SOUL.md sequentially.

    The calls are serial because SOUL.md depends on IDENTITY.md
    to maintain personality consistency.
    """
    if llm is None:
        llm = LLMConfig()

    identity_md = await _generate_identity(spec, llm)
    soul_md = await _generate_soul(spec, identity_md, llm)

    return GeneratedFiles(
        identity_md=identity_md,
        soul_md=soul_md,
    )
