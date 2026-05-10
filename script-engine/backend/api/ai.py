import json
import uuid
import re
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.task_dispatcher import cancel_task as cancel_dispatched_task, enqueue_task
from services.project_runtime import load_project_runtime
from services.llm_prompts import (
    build_world_gen_prompt, build_character_gen_prompt,
    build_chapter_outline_prompt, build_wow_plan_prompt,
    build_relation_network_prompt, build_foreshadow_design_prompt,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentTaskResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    estimated_time: str


class WorldGenResponse(BaseModel):
    proposals: list[str]


class CharacterGenRequest(BaseModel):
    project_name: str = ""
    genre: str = ""
    target_words: int = 500000
    existing_count: int = 0
    existing_names: str = ""
    script_context: str = ""


class CharacterGenResponse(BaseModel):
    proposals: list[dict]


class RelationNetworkResponse(BaseModel):
    relations: list[dict]


class ForeshadowHealthResponse(BaseModel):
    total: int
    normal: int
    warning: int
    danger: int
    suggestions: list[str]


class ForeshadowReactionResponse(BaseModel):
    suggestions: list[str]


class WowPlanResponse(BaseModel):
    plans: list[dict]


class SceneDispatchRequest(BaseModel):
    requirements: str = ""


WORLD_CONFIG_META = {
    "core_contradiction": {"label": "核心矛盾", "desc": "世界运行的终极矛盾，驱动所有剧情发展的核心动力"},
    "social_structure": {"label": "社会结构", "desc": "权力分布、阶层划分、组织关系"},
    "tech_magic": {"label": "科技/魔法体系", "desc": "能力上限、代价、规则、稀有度"},
    "geography": {"label": "地理环境", "desc": "世界地图、重要地标、气候特征"},
    "history": {"label": "历史背景", "desc": "重大历史事件、传说、被掩盖的真相"},
    "culture": {"label": "文化习俗", "desc": "信仰、节日、禁忌、性别观、道德观"},
    "constraints": {"label": "约束条件", "desc": "人物行为在剧情中的硬性限制"},
    "impossible": {"label": "不可能事项", "desc": "这个世界绝对不可能发生的事"},
}


def _extract_json_block(text: str) -> str:
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        return match.group(1).strip()
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if match:
        return match.group(0)
    match = re.search(r'\[[^\[\]]*(?:\{[^{}]*\}[^\[\]]*)*\]', text)
    if match:
        return match.group(0)
    return text


async def _call_agent(intent: str, system_prompt: str, user_prompt: str,
                      temperature: float = 0.7, max_tokens: int = 8192,
                      cost_profile: str = "balanced") -> str:
    from core.gateway.client import get_gateway

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        gateway = get_gateway()
        result = await gateway.invoke(
            intent=intent,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            cost_profile=cost_profile,
        )
        content = result.content
        if not content:
            raise ValueError("LLM returned empty response")
        return content
    except Exception as e:
        logger.error("LLM call failed for intent=%s: %s", intent, str(e))
        raise HTTPException(status_code=502, detail=f"AI 服务暂时不可用: {str(e)}")


def _salvage_content(content: str) -> dict:
    result = {"raw": content[:8000], "narration": "", "dialogue": [], "emotion_level": 5}
    parts = re.split(r'(?:旁白|叙述|场景描述)[：:]', content, maxsplit=1)
    if len(parts) > 1:
        result["narration"] = parts[1].strip()[:8000]
    else:
        result["narration"] = content.strip()[:8000]
    dialogue_matches = re.findall(r'(?:[（(]([^）)]+)[）)])?\s*["""]([^"""]+)["""]', content)
    if dialogue_matches:
        result["dialogue"] = [{"speaker": m[0] or "角色", "text": m[1]} for m in dialogue_matches]
    emo_match = re.search(r'情绪[^：:]*[：:]\s*(\d+)', content)
    if emo_match:
        result["emotion_level"] = min(10, max(1, int(emo_match.group(1))))
    return result


async def _call_and_parse_json(intent: str, system_prompt: str, user_prompt: str,
                               temperature: float = 0.7, max_tokens: int = 8192,
                               cost_profile: str = "balanced",
                               allow_salvage: bool = True) -> dict | list:
    content = await _call_agent(intent, system_prompt, user_prompt, temperature, max_tokens, cost_profile)
    try:
        json_block = _extract_json_block(content)
        return json.loads(json_block)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from LLM response, raw content: %s", content[:500])
        if not allow_salvage:
            raise
        return _salvage_content(content)

# ============================================================================
#  上下文收集助手：确保每个AI调用都能获取完整的项目上下文
# ============================================================================

async def _gather_world_context(db: AsyncSession, project_id: uuid.UUID) -> dict:
    """收集项目世界观设定作为上下文"""
    from models.project_config import ProjectConfig

    result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        return {}

    world = {}
    if config.genre and config.genre.strip():
        world["体裁"] = config.genre[:500]
    if config.sub_genre and config.sub_genre.strip():
        world["子类型"] = config.sub_genre[:500]
    if config.core_contradiction and config.core_contradiction.strip():
        world["核心矛盾"] = config.core_contradiction[:1200]
    if config.theme and config.theme.strip():
        world["主题思想"] = config.theme[:800]
    if config.tone and config.tone.strip():
        world["基调"] = config.tone[:500]
    if config.writing_style and config.writing_style.strip():
        world["写作风格"] = config.writing_style[:500]
    if config.narrative_pov and config.narrative_pov.strip():
        world["叙事视角"] = config.narrative_pov[:500]
    if config.language_complexity and config.language_complexity.strip():
        world["语言复杂度"] = config.language_complexity[:500]
    if config.target_audience and config.target_audience.strip():
        world["目标人群"] = config.target_audience[:500]
    if config.commercial_fit and config.commercial_fit.strip():
        world["目标平台"] = config.commercial_fit[:500]

    custom_rules = dict(config.custom_checker_rules or {})
    world_settings = custom_rules.get("world_settings", {})
    if isinstance(world_settings, dict):
        settings_labels = {
            "social_structure": "社会结构",
            "tech_magic": "科技/魔法体系",
            "geography": "地理环境",
            "history": "历史背景",
            "culture": "文化习俗",
            "constraints": "约束条件",
            "impossible": "不可能事项",
        }
        for key, label in settings_labels.items():
            value = world_settings.get(key, "")
            if value and isinstance(value, str) and value.strip():
                world[label] = value[:2000]

    return world


async def _gather_character_context(db: AsyncSession, project_id: uuid.UUID,
                                     character_refs: list | None = None) -> str:
    """收集角色上下文供提示词使用"""
    from models.character import Character

    query = select(Character).where(Character.project_id == project_id)
    if character_refs:
        character_ids = []
        character_names = []
        for ref in character_refs:
            if not isinstance(ref, str):
                continue
            value = ref.strip()
            if not value:
                continue
            try:
                character_ids.append(uuid.UUID(value))
            except ValueError:
                character_names.append(value)

        filters = []
        if character_ids:
            filters.append(Character.id.in_(character_ids))
        if character_names:
            filters.append(Character.name.in_(character_names))
        if filters:
            query = query.where(or_(*filters))
    result = await db.execute(query)
    chars = result.scalars().all()

    if not chars:
        return ""

    lines = []
    for c in chars:
        char_block = f"""【{c.name}】({c.role_type or '未指定角色类型'})
  核心动机：{c.core_goal or '未设定'}
  核心恐惧：{c.core_fear or '未设定'}
  表层印象：{c.surface_image or '未设定'}
  真实自我：{c.true_self or '未设定'}
  语言风格：{c.language_style or '未设定'}
  {f'口头禅：{c.catchphrase}' if c.catchphrase else ''}
  成长弧线：{c.arc_description or '未设定'}
  背景：{c.background or '未设定'}"""

        if c.behavior_inevitable and isinstance(c.behavior_inevitable, list) and c.behavior_inevitable:
            char_block += f"\n  必定会做的事：{', '.join(str(b) for b in c.behavior_inevitable)}"
        if c.behavior_never and isinstance(c.behavior_never, list) and c.behavior_never:
            char_block += f"\n  绝对不会做的事：{', '.join(str(b) for b in c.behavior_never)}"
        if c.behavior_conditional and isinstance(c.behavior_conditional, list) and c.behavior_conditional:
            char_block += f"\n  条件行为：{', '.join(str(b) for b in c.behavior_conditional)}"

        lines.append(char_block)

    return "\n\n".join(lines)

async def _gather_foreshadow_context(db: AsyncSession, project_id: uuid.UUID) -> str:
    """收集待处理的伏笔任务"""
    from models.foreshadow import Foreshadow

    result = await db.execute(
        select(Foreshadow).where(
            Foreshadow.project_id == project_id,
            Foreshadow.current_status.in_(["active", "planted"])
        ).order_by(Foreshadow.created_at)
    )
    fss = result.scalars().all()

    if not fss:
        return ""

    lines = []
    for f in fss:
        fs_block = f"""【伏笔：{f.name}】({f.foreshadow_tier or f.fs_type or '未分类'})
  表层设定：{f.surface_layer or '未设定'}
  深层线索：{f.deep_layer or '未设定'}
  真相层：{f.truth_layer or '未设定'}
  当前状态：{f.current_status or 'unknown'}（已强化{f.reinforce_count or 0}次）
  埋设位置：{f.plant_location or '未设定'}
  揭露位置：{f.reveal_location or '未设定'}
  回收状态：{f.reclaim_status or 'unplanted'}
  需要在此场景中：{'植入线索' if f.current_status == 'active' else '适度提示/强化'}"""
        lines.append(fs_block)

    return "\n\n".join(lines)

# ==================== Agent Task Dispatch ====================

@router.post("/ai/projects/{project_id}/scenes/{scene_id}/generate", response_model=AgentTaskResponse)
async def dispatch_scene_generate(project_id: uuid.UUID, scene_id: uuid.UUID,
                                  body: SceneDispatchRequest | None = None,
                                  db: AsyncSession = Depends(get_db)):
    response = await enqueue_task(
        db,
        project_id=str(project_id),
        task_type="scene_generation",
        payload={"scene_id": str(scene_id), "requirements": (body.requirements or "").strip() if body else ""},
        task_kwargs={
            "project_id": str(project_id),
            "scene_id": str(scene_id),
            "requirements": {"user_requirements": (body.requirements or "").strip() if body else ""},
        },
    )
    return AgentTaskResponse(**response)


@router.post("/ai/projects/{project_id}/scenes/{scene_id}/audit", response_model=AgentTaskResponse)
async def dispatch_scene_audit(project_id: uuid.UUID, scene_id: uuid.UUID,
                                db: AsyncSession = Depends(get_db)):
    response = await enqueue_task(
        db,
        project_id=str(project_id),
        task_type="scene_audit",
        payload={"scene_id": str(scene_id)},
        task_kwargs={
            "project_id": str(project_id),
            "scene_id": str(scene_id),
            "requirements": {},
        },
    )
    return AgentTaskResponse(**response)


@router.post("/ai/projects/{project_id}/foreshadows/generate", response_model=AgentTaskResponse)
async def dispatch_foreshadow_generate(project_id: uuid.UUID,
                                        db: AsyncSession = Depends(get_db)):
    runtime = await load_project_runtime(db, project_id)
    core_truth = runtime.core_truth

    world = await _gather_world_context(db, project_id)
    world_settings = {}
    settings_mapping = {
        "核心矛盾": "core_contradiction",
        "社会结构": "social_structure",
        "科技/魔法体系": "tech_magic",
        "地理环境": "geography",
        "历史背景": "history",
        "文化习俗": "culture",
        "约束条件": "constraints",
        "不可能事项": "impossible",
    }
    for cn_label, config_key in settings_mapping.items():
        val = world.get(cn_label, "")
        if val and isinstance(val, str) and val.strip():
            world_settings[config_key] = val

    core_contradiction = world_settings.get("core_contradiction", "")

    character_ids: list[str] = []
    characters: list[dict] = []
    try:
        from models.character import Character
        chars_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        chars = chars_result.scalars().all()
        character_ids = [str(c.id) for c in chars]
        for c in chars:
            char_info = {"name": c.name, "role_type": c.role_type or "未设定"}
            if c.core_goal:
                char_info["core_goal"] = c.core_goal
            if c.core_fear:
                char_info["core_fear"] = c.core_fear
            if c.surface_image:
                char_info["surface_image"] = c.surface_image
            if c.true_self:
                char_info["true_self"] = c.true_self
            if c.dark_secret:
                char_info["dark_secret"] = c.dark_secret
            characters.append(char_info)
    except Exception:
        pass

    chapter_outlines: list[dict] = []
    chapter_count = 20
    try:
        from models.chapter import Chapter as ChapterModel
        from models.project_config import ProjectConfig
        config_result = await db.execute(
            select(ProjectConfig).where(ProjectConfig.project_id == project_id)
        )
        config = config_result.scalar_one_or_none()
        if config and config.chapter_count:
            chapter_count = config.chapter_count

        chapters_result = await db.execute(
            select(ChapterModel).where(ChapterModel.project_id == project_id)
            .order_by(ChapterModel.chapter_number)
        )
        for ch in chapters_result.scalars().all():
            ch_info = {"chapter_number": ch.chapter_number, "title": ch.title or ""}
            if ch.summary:
                ch_info["summary"] = ch.summary
            if hasattr(ch, 'core_conflict') and ch.core_conflict:
                ch_info["core_conflict"] = ch.core_conflict
            chapter_outlines.append(ch_info)
    except Exception:
        pass

    response = await enqueue_task(
        db,
        project_id=str(project_id),
        task_type="foreshadow_design",
        payload={
            "core_truth": core_truth,
            "core_contradiction": core_contradiction,
            "character_ids": character_ids,
            "world_settings": world_settings,
            "characters": characters,
            "chapter_outlines": chapter_outlines,
            "chapter_count": chapter_count,
        },
        task_kwargs={
            "project_id": str(project_id),
            "core_truth": core_truth,
            "core_contradiction": core_contradiction,
            "character_ids": character_ids,
            "world_settings": world_settings,
            "characters": characters,
            "chapter_outlines": chapter_outlines,
            "chapter_count": chapter_count,
        },
    )
    return AgentTaskResponse(**response)


class ForeshadowDesignResponse(BaseModel):
    design_philosophy: str = ""
    revelation_path: list[dict] = []
    foreshadows: list[dict] = []
    stats: dict = {}
    issues: list[str] = []


@router.post("/ai/foreshadow-design/{project_id}", response_model=ForeshadowDesignResponse)
async def generate_foreshadow_design(project_id: uuid.UUID,
                                      db: AsyncSession = Depends(get_db)):
    runtime = await load_project_runtime(db, project_id)
    core_truth = runtime.core_truth

    world = await _gather_world_context(db, project_id)
    world_settings = {}
    settings_mapping = {
        "核心矛盾": "core_contradiction",
        "社会结构": "social_structure",
        "科技/魔法体系": "tech_magic",
        "地理环境": "geography",
        "历史背景": "history",
        "文化习俗": "culture",
        "约束条件": "constraints",
        "不可能事项": "impossible",
    }
    for cn_label, config_key in settings_mapping.items():
        val = world.get(cn_label, "")
        if val and isinstance(val, str) and val.strip():
            world_settings[config_key] = val

    core_contradiction = world_settings.get("core_contradiction", "")

    characters: list[dict] = []
    try:
        from models.character import Character
        chars_result = await db.execute(
            select(Character).where(Character.project_id == project_id)
        )
        for c in chars_result.scalars().all():
            char_info = {"name": c.name, "role_type": c.role_type or "未设定"}
            if c.core_goal:
                char_info["core_goal"] = c.core_goal
            if c.core_fear:
                char_info["core_fear"] = c.core_fear
            if c.surface_image:
                char_info["surface_image"] = c.surface_image
            if c.true_self:
                char_info["true_self"] = c.true_self
            if c.dark_secret:
                char_info["dark_secret"] = c.dark_secret
            characters.append(char_info)
    except Exception:
        pass

    chapter_outlines: list[dict] = []
    chapter_count = 20
    try:
        from models.chapter import Chapter as ChapterModel
        from models.project_config import ProjectConfig
        config_result = await db.execute(
            select(ProjectConfig).where(ProjectConfig.project_id == project_id)
        )
        config = config_result.scalar_one_or_none()
        if config and config.chapter_count:
            chapter_count = config.chapter_count

        chapters_result = await db.execute(
            select(ChapterModel).where(ChapterModel.project_id == project_id)
            .order_by(ChapterModel.chapter_number)
        )
        for ch in chapters_result.scalars().all():
            ch_info = {"chapter_number": ch.chapter_number, "title": ch.title or ""}
            if ch.summary:
                ch_info["summary"] = ch.summary
            if hasattr(ch, 'core_conflict') and ch.core_conflict:
                ch_info["core_conflict"] = ch.core_conflict
            chapter_outlines.append(ch_info)
    except Exception:
        pass

    system_prompt, user_prompt = build_foreshadow_design_prompt(
        core_truth=core_truth,
        core_contradiction=core_contradiction,
        world_settings=world_settings,
        characters=characters,
        chapter_outlines=chapter_outlines,
        chapter_count=chapter_count,
    )

    try:
        result = await _call_and_parse_json(
            "write.outline", system_prompt, user_prompt,
            temperature=0.85, max_tokens=32768, cost_profile="quality",
            allow_salvage=False,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Foreshadow design failed for project %s: %s", project_id, str(e))
        return ForeshadowDesignResponse(
            issues=["AI 服务暂时不可用，请稍后重试"],
        )

    if not isinstance(result, dict):
        return ForeshadowDesignResponse(
            issues=["AI 返回格式异常，请重试"],
        )

    foreshadows = result.get("foreshadows", [])
    design_philosophy = result.get("design_philosophy", "")
    revelation_path = result.get("revelation_path", [])
    stats = result.get("stats", {})
    issues = result.get("issues", [])

    global_count = stats.get("global_count", 0)
    chapter_count_found = stats.get("chapter_count", 0)
    scene_count = stats.get("scene_count", 0)

    if global_count == 0 and chapter_count_found == 0 and scene_count == 0:
        for fs in foreshadows:
            tier = fs.get("foreshadow_tier", "chapter")
            if tier == "global":
                global_count += 1
            elif tier == "chapter":
                chapter_count_found += 1
            else:
                scene_count += 1
        stats["global_count"] = global_count
        stats["chapter_count"] = chapter_count_found
        stats["scene_count"] = scene_count
        stats["total_count"] = global_count + chapter_count_found + scene_count

    core_total = global_count + chapter_count_found
    if core_total > 0:
        reclaimed = sum(
            1 for fs in foreshadows
            if fs.get("foreshadow_tier", "chapter") in ("global", "chapter")
            and fs.get("reveal_location") and fs.get("plant_location")
        )
        reclaim_rate = round(reclaimed / core_total * 100, 1)
        stats["reclaim_rate"] = f"{reclaim_rate}%"

        if reclaim_rate < 80:
            issues.append(f"核心伏笔回收率{reclaim_rate}%，低于80%目标，建议补充回收路径")

    if global_count < 5:
        issues.append(f"全剧级伏笔数量不足：当前{global_count}条，建议5-8条")
    if chapter_count_found < 20:
        issues.append(f"章节级伏笔数量不足：当前{chapter_count_found}条，建议20-30条")

    for fs in foreshadows:
        if not fs.get("worldview_refs"):
            issues.append(f"伏笔「{fs.get('name', '?')}」缺少世界观关联(worldview_refs)")
            break
        if not fs.get("character_refs"):
            issues.append(f"伏笔「{fs.get('name', '?')}」缺少角色关联(character_refs)")
            break

    return ForeshadowDesignResponse(
        design_philosophy=design_philosophy,
        revelation_path=revelation_path,
        foreshadows=foreshadows,
        stats=stats,
        issues=issues,
    )


@router.post("/ai/projects/{project_id}/foreshadows/{foreshadow_id}/wow-plans",
             response_model=AgentTaskResponse)
async def dispatch_wow_plans(project_id: uuid.UUID, foreshadow_id: uuid.UUID,
                              db: AsyncSession = Depends(get_db)):
    from models.foreshadow import Foreshadow

    fs_result = await db.execute(
        select(Foreshadow).where(
            Foreshadow.id == foreshadow_id,
            Foreshadow.project_id == project_id,
        )
    )
    foreshadow = fs_result.scalar_one_or_none()

    if not foreshadow:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    core_truth = ""
    try:
        runtime = await load_project_runtime(db, project_id)
        core_truth = runtime.core_truth or ""
    except Exception:
        pass

    if not core_truth:
        core_truth = foreshadow.truth_layer or foreshadow.surface_layer or ""

    response = await enqueue_task(
        db,
        project_id=str(project_id),
        task_type="foreshadow_design",
        payload={
            "core_truth": core_truth,
            "character_ids": [],
            "foreshadow_id": str(foreshadow_id),
            "foreshadow_name": foreshadow.name,
            "foreshadow_tier": foreshadow.foreshadow_tier or foreshadow.fs_type or "",
            "foreshadow_surface": foreshadow.surface_layer or "",
            "foreshadow_deep": foreshadow.deep_layer or "",
            "foreshadow_truth": foreshadow.truth_layer or "",
        },
        task_kwargs={
            "project_id": str(project_id),
            "core_truth": core_truth,
            "character_ids": [],
            "foreshadow_id": str(foreshadow_id),
        },
    )
    return AgentTaskResponse(**response)


@router.get("/ai/tasks/{task_id}")
async def get_task_progress(task_id: str):
    try:
        from tasks import get_progress
        progress = get_progress(task_id)
        return {
            "task_id": task_id,
            "status": progress["status"],
            "progress": progress["progress"],
            "estimated_time": "预计 3 秒",
        }
    except Exception:
        return {
            "task_id": task_id,
            "status": "unknown",
            "progress": 0,
            "estimated_time": "任务未找到",
        }


@router.post("/ai/cancel/{task_id}")
async def cancel_task(task_id: str, db: AsyncSession = Depends(get_db)):
    return await cancel_dispatched_task(db, task_id)


@router.post("/ai/projects/{project_id}/full-audit", response_model=AgentTaskResponse)
async def dispatch_full_audit(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    response = await enqueue_task(
        db,
        project_id=str(project_id),
        task_type="full_audit",
        payload={},
        task_kwargs={"project_id": str(project_id)},
    )
    return AgentTaskResponse(**response)


# ==================== World Gen ====================

@router.post("/ai/world-gen/{project_id}/{config_key}", response_model=WorldGenResponse)
async def generate_world_config(project_id: uuid.UUID, config_key: str,
                                 db: AsyncSession = Depends(get_db)):
    meta = WORLD_CONFIG_META.get(config_key, {"label": config_key, "desc": "世界观配置"})
    existing_world = await _gather_world_context(db, project_id)

    current_value = ""
    try:
        from models.project_config import ProjectConfig as PCModel
        from api.projects import _get_world_config_value
        config_result = await db.execute(
            select(PCModel).where(PCModel.project_id == project_id)
        )
        config = config_result.scalar_one_or_none()
        if config:
            val = _get_world_config_value(config, config_key)
            if val and isinstance(val, str) and val.strip():
                current_value = val
    except Exception:
        pass

    system_prompt, user_prompt = build_world_gen_prompt(
        config_key, meta["label"], meta["desc"], existing_world, current_value
    )

    try:
        result = await _call_and_parse_json("write.creative", system_prompt, user_prompt,
                                            temperature=0.85, max_tokens=16384, cost_profile="quality")
        if isinstance(result, list) and len(result) >= 1:
            proposals = result[:3] if len(result) >= 3 else result
        elif isinstance(result, dict) and "raw" in result:
            raw = result["raw"]
            lines = [l.strip() for l in raw.split("\n") if l.strip() and len(l.strip()) > 20]
            proposals = lines[:3] if len(lines) >= 3 else lines + ["（AI生成内容较少，建议重试）"] * (3 - len(lines))
        else:
            proposals = ["AI 返回格式异常，请重试"] * 3
    except HTTPException:
        raise
    except Exception as e:
        logger.error("World gen failed for %s: %s", config_key, str(e))
        proposals = ["AI 服务暂时不可用，请稍后重试"] * 3

    return WorldGenResponse(proposals=proposals)


# ==================== Character Gen ====================

@router.post("/ai/character-gen/{project_id}", response_model=CharacterGenResponse)
async def generate_characters(project_id: uuid.UUID,
                               body: CharacterGenRequest | None = None,
                               db: AsyncSession = Depends(get_db)):
    from models.project import Project
    from models.project_config import ProjectConfig
    from models.character import Character

    project_result = await db.execute(select(Project).where(Project.id == project_id))
    project = project_result.scalar_one_or_none()

    config_result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()
    genre = (body.genre if body and body.genre else config.genre) if config else (body.genre if body else "")

    world = await _gather_world_context(db, project_id)
    world_context = "\n".join(f"{k}: {v[:500]}" for k, v in list(world.items())[:10])

    world_core_contradiction = world.get("核心矛盾", "")
    world_constraints = world.get("约束条件", "")
    world_impossible = world.get("不可能事项", "")

    existing = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    existing_chars = []
    for c in existing.scalars().all():
        char_dict = {"name": c.name, "role_type": c.role_type, "core_goal": c.core_goal or ""}
        if c.core_fear:
            char_dict["core_fear"] = c.core_fear
        if c.background:
            char_dict["background"] = c.background
        if c.surface_image:
            char_dict["surface_image"] = c.surface_image
        if c.true_self:
            char_dict["true_self"] = c.true_self
        if c.dark_secret:
            char_dict["dark_secret"] = c.dark_secret
        if c.arc_description:
            char_dict["arc_description"] = c.arc_description
        if c.language_style:
            char_dict["language_style"] = c.language_style
        if c.catchphrase:
            char_dict["catchphrase"] = c.catchphrase
        if c.behavior_inevitable and isinstance(c.behavior_inevitable, list):
            char_dict["behavior_inevitable"] = c.behavior_inevitable
        if c.behavior_never and isinstance(c.behavior_never, list):
            char_dict["behavior_never"] = c.behavior_never
        existing_chars.append(char_dict)

    character_count = 15
    if config and config.target_word_count:
        word_count = config.target_word_count or 500000
        if word_count <= 50000:
            character_count = 15
        elif word_count <= 100000:
            character_count = 20
        elif word_count <= 200000:
            character_count = 28
        elif word_count <= 500000:
            character_count = 40
        elif word_count <= 1000000:
            character_count = 55
        else:
            character_count = 70

    script_context = ""
    if body and body.script_context:
        script_context = f"\n\n【剧本上下文（已有场景内容摘要）】\n{body.script_context[:8000]}"

    system_prompt, user_prompt = build_character_gen_prompt(
        world_context, genre, existing_chars, character_count,
        world_core_contradiction=world_core_contradiction,
        world_constraints=world_constraints,
        world_impossible=world_impossible,
    )

    if script_context:
        user_prompt += script_context

    try:
        result = await _call_and_parse_json("write.creative", system_prompt, user_prompt,
                                            temperature=0.85, max_tokens=32768, cost_profile="quality",
                                            allow_salvage=False)
        if isinstance(result, list) and len(result) >= 1:
            proposals = result[:character_count]
        else:
            proposals = []
    except HTTPException:
        raise
    except Exception:
        proposals = []

    return CharacterGenResponse(proposals=proposals)


# ==================== Relation Network Gen ====================

@router.post("/ai/relation-network-gen/{project_id}", response_model=RelationNetworkResponse)
async def generate_relation_network(project_id: uuid.UUID,
                                     db: AsyncSession = Depends(get_db)):
    from models.character import Character
    from models.project_config import ProjectConfig

    config_result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()
    genre = config.genre if config else ""

    world = await _gather_world_context(db, project_id)
    world_context = "\n".join(f"{k}: {v[:500]}" for k, v in list(world.items())[:10])

    world_core_contradiction = world.get("核心矛盾", "")
    world_constraints = world.get("约束条件", "")
    world_impossible = world.get("不可能事项", "")

    existing = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    characters = []
    for c in existing.scalars().all():
        characters.append({
            "name": c.name,
            "role_type": c.role_type,
            "core_goal": c.core_goal,
            "core_fear": c.core_fear,
            "surface_image": c.surface_image,
            "true_self": c.true_self,
            "dark_secret": c.dark_secret,
        })

    if len(characters) < 2:
        return RelationNetworkResponse(relations=[])

    system_prompt, user_prompt = build_relation_network_prompt(
        world_context, genre, characters,
        world_core_contradiction=world_core_contradiction,
        world_constraints=world_constraints,
        world_impossible=world_impossible,
    )

    try:
        result = await _call_and_parse_json("write.creative", system_prompt, user_prompt,
                                            temperature=0.85, max_tokens=32768, cost_profile="quality",
                                            allow_salvage=False)
        if isinstance(result, list) and len(result) >= 1:
            relations = result
        else:
            relations = []
    except HTTPException:
        raise
    except Exception:
        relations = []

    n = len(characters)
    max_possible = n * (n - 1) // 2
    min_required = max(n * 2, int(max_possible * 0.6))
    if len(relations) < min_required:
        logger.warning(
            "Relation network density below 60%%: got %d relations, need %d (max_possible=%d, n=%d)",
            len(relations), min_required, max_possible, n
        )

    for rel in relations:
        if not isinstance(rel, dict):
            continue
        info_asym = rel.get("info_asymmetry")
        if info_asym and isinstance(info_asym, dict):
            if not rel.get("info_known_a_about_b"):
                a_knows = info_asym.get("a_knows_about_b", "")
                rel["info_known_a_about_b"] = [a_knows] if a_knows else []
            if not rel.get("info_known_b_about_a"):
                b_knows = info_asym.get("b_knows_about_a", "")
                rel["info_known_b_about_a"] = [b_knows] if b_knows else []
        if "is_hidden" not in rel:
            hidden_types = {"secret_ally", "hidden_enemy", "blackmailer", "informant"}
            rel["is_hidden"] = rel.get("relation_type", "") in hidden_types
        if "arc_direction" not in rel:
            rel["arc_direction"] = "stable"
        if "arc_milestones" not in rel:
            rel["arc_milestones"] = []

    return RelationNetworkResponse(relations=relations)


# ==================== Scene Gen ====================
# ==================== Foreshadow Health ====================

@router.post("/ai/foreshadow-health/{project_id}", response_model=ForeshadowHealthResponse)
async def check_foreshadow_health(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from models.foreshadow import Foreshadow

    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    foreshadows = fs_result.scalars().all()

    fs_data = []
    for f in foreshadows:
        fs_item = {
            "fs_code": f.fs_code,
            "name": f.name,
            "type": f.fs_type,
            "foreshadow_tier": f.foreshadow_tier or f.fs_type or "chapter",
            "health": f.health or "normal",
            "current_status": f.current_status or "active",
            "reinforce_count": f.reinforce_count or 0,
            "surface_layer": f.surface_layer or "",
            "deep_layer": f.deep_layer or "",
            "truth_layer": f.truth_layer or "",
            "has_plant": bool(f.plant_scene_id) or bool(f.plant_location),
            "has_reveal": bool(f.reveal_scene_id) or bool(f.reveal_location),
            "plant_location": f.plant_location or "",
            "reveal_location": f.reveal_location or "",
            "reclaim_status": f.reclaim_status or "unplanted",
            "has_worldview_refs": bool(f.worldview_refs and len(f.worldview_refs) > 0),
            "has_character_refs": bool(f.character_refs and len(f.character_refs) > 0),
            "has_foreshadow_links": bool(f.foreshadow_links and len(f.foreshadow_links) > 0),
        }
        fs_data.append(fs_item)

    if not fs_data:
        return ForeshadowHealthResponse(
            total=0, normal=0, warning=0, danger=0,
            suggestions=["项目尚无伏笔数据，建议先通过AI生成伏笔设计"]
        )

    health_counts = {"normal": 0, "warning": 0, "danger": 0}
    issues_found = []
    for f in fs_data:
        h = f.get("health", "normal")
        health_counts[h] = health_counts.get(h, 0) + 1
        if not f.get("has_plant"):
            issues_found.append(f"伏笔「{f['name']}」缺乏植入场景/位置")
        if not f.get("has_reveal") and f.get("current_status") != "design":
            issues_found.append(f"伏笔「{f['name']}」缺乏回收计划/位置")
        if not f.get("has_worldview_refs"):
            issues_found.append(f"伏笔「{f['name']}」缺少世界观关联")
        if not f.get("has_character_refs"):
            issues_found.append(f"伏笔「{f['name']}」缺少角色关联")
        if not f.get("has_foreshadow_links") and f.get("foreshadow_tier") in ("global", "chapter"):
            issues_found.append(f"核心伏笔「{f['name']}」缺少伏笔间关联")

    system_prompt = """你是伏笔网络分析专家，负责评估互动影游剧本中伏笔系统的健康状况。
分析维度：覆盖率、回收率、强化密度、三层结构完整性、跨伏笔关联度。
以2-4条具体可操作的建议开始。"""

    user_prompt = f"""请分析以下伏笔网络健康状况并给出具体建议：

伏笔列表（{len(fs_data)}个）：
{json.dumps([{"name": f['name'], "type": f['type'], "status": f['current_status'], "has_plant": f['has_plant'], "has_reveal": f['has_reveal'], "reinforce_count": f['reinforce_count']} for f in fs_data], ensure_ascii=False, indent=2)}

已知问题：
{chr(10).join('- ' + i for i in issues_found) if issues_found else '无显著问题'}

请以JSON格式返回建议。格式：{{"suggestions": ["建议1", "建议2", ...]}}"""

    try:
        result = await _call_and_parse_json("analyze.structure", system_prompt, user_prompt,
                                            temperature=0.7, max_tokens=4096)
        suggestions = result.get("suggestions", []) if isinstance(result, dict) else []
        if isinstance(result, list):
            suggestions = [str(s) for s in result[:5]]
    except HTTPException:
        raise
    except Exception:
        suggestions = []

    if not suggestions:
        suggestions = [
            f"全局：累计{len(fs_data)}个伏笔需要定期检查健康状态",
            "建议确保每个伏笔都有明确的植入场景（plant_scene）和回收计划（reveal_scene）",
            "建议检查伏笔依赖链是否完整（BFS可达性），避免断开引用",
        ]

    return ForeshadowHealthResponse(
        total=len(fs_data),
        normal=health_counts["normal"],
        warning=health_counts["warning"],
        danger=health_counts["danger"],
        suggestions=suggestions,
    )


# ==================== Foreshadow Reaction ====================

@router.post("/ai/foreshadow-reaction/{project_id}",
             response_model=ForeshadowReactionResponse)
async def analyze_foreshadow_reaction(project_id: uuid.UUID,
                                       db: AsyncSession = Depends(get_db)):
    from models.foreshadow import Foreshadow, ForeshadowRelation

    fs_result = await db.execute(
        select(Foreshadow).where(Foreshadow.project_id == project_id)
    )
    foreshadows = fs_result.scalars().all()

    rel_result = await db.execute(
        select(ForeshadowRelation).where(ForeshadowRelation.project_id == project_id)
    )
    relations = rel_result.scalars().all()

    fs_map = {str(f.id): f for f in foreshadows}
    rel_data = []
    for r in relations:
        from_name = fs_map.get(str(r.from_fs_id), None)
        to_name = fs_map.get(str(r.to_fs_id), None)
        rel_data.append({
            "from": from_name.name if from_name else str(r.from_fs_id),
            "to": to_name.name if to_name else str(r.to_fs_id),
            "type": r.relation_type,
        })

    system_prompt = """你是伏笔化学反应分析师，擅长发现不同伏笔之间潜在的关联和协同效应。
你的回答必须是JSON数组，每项是一个发现，格式如：{"from": "伏笔A", "to": "伏笔B", "reaction": "潜在关联描述"}"""

    user_prompt = f"""请分析以下伏笔之间的潜在化学反应：

伏笔列表：
{json.dumps([{"name": f.name, "type": f.fs_type, "surface": (f.surface_layer or ""), "deep": (f.deep_layer or "")} for f in foreshadows], ensure_ascii=False, indent=2)}

已有关系：
{json.dumps(rel_data, ensure_ascii=False, indent=2)}

请找出3-5个尚未建立关系但可能产生有趣化学反应的伏笔对。"""

    try:
        result = await _call_and_parse_json("analyze.creative", system_prompt, user_prompt,
                                            temperature=0.8, max_tokens=4096)
        if isinstance(result, list):
            suggestions = [
                f"发现潜在关联：{item.get('from', '?')} + {item.get('to', '?')} -> {item.get('reaction', '可能存在关联')}"
                for item in result[:5]
            ]
        else:
            suggestions = ["未检测到新的伏笔化学反应"]
    except HTTPException:
        raise
    except Exception:
        suggestions = ["AI 分析服务暂时不可用"]

    return ForeshadowReactionResponse(suggestions=suggestions)


# ==================== Wow Plans ====================

@router.post("/ai/foreshadow-wow-gen/{foreshadow_id}", response_model=WowPlanResponse)
async def generate_wow_plans(foreshadow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from models.foreshadow import Foreshadow

    fs_result = await db.execute(select(Foreshadow).where(Foreshadow.id == foreshadow_id))
    foreshadow = fs_result.scalar_one_or_none()

    if not foreshadow:
        raise HTTPException(status_code=404, detail="伏笔不存在")

    fs_context = f"""伏笔名称: {foreshadow.name}
类型: {foreshadow.foreshadow_tier or foreshadow.fs_type or '未分类'}
表层（读者初见的印象）: {foreshadow.surface_layer or '未设定'}
深层（细心读者会注意到的）: {foreshadow.deep_layer or '未设定'}
核心层（终极真相，读者要到最后才会知道）: {foreshadow.truth_layer or '未设定'}
当前状态: {foreshadow.current_status or 'unknown'}
已强化次数: {foreshadow.reinforce_count or 0}
埋设位置: {foreshadow.plant_location or '未设定'}
揭露位置: {foreshadow.reveal_location or '未设定'}"""

    character_context = ""
    if foreshadow.plant_scene_id:
        from models.scene import Scene
        scene_result = await db.execute(
            select(Scene).where(Scene.id == foreshadow.plant_scene_id)
        )
        plant_scene = scene_result.scalar_one_or_none()
        if plant_scene and plant_scene.characters_involved:
            char_refs = [ref for ref in plant_scene.characters_involved if isinstance(ref, str)]
            character_context = await _gather_character_context(db, foreshadow.project_id, char_refs)

    if not character_context:
        character_context = await _gather_character_context(db, foreshadow.project_id)

    core_truth = ""
    try:
        runtime = await load_project_runtime(db, foreshadow.project_id)
        core_truth = runtime.core_truth or ""
    except Exception:
        pass

    worldview_context = ""
    try:
        world = await _gather_world_context(db, foreshadow.project_id)
        world_lines = []
        for key in ["核心矛盾", "社会结构", "科技/魔法体系", "约束条件", "不可能事项", "历史背景"]:
            val = world.get(key, "")
            if val and isinstance(val, str) and val.strip():
                world_lines.append(f"  ▸ {key}：{val[:500]}")
        if world_lines:
            worldview_context = "\n".join(world_lines)
    except Exception:
        pass

    system_prompt, user_prompt = build_wow_plan_prompt(
        fs_context, character_context,
        core_truth=core_truth, worldview_context=worldview_context,
    )

    try:
        result = await _call_and_parse_json("write.creative", system_prompt, user_prompt,
                                            temperature=0.92, max_tokens=16384, cost_profile="quality")
        if isinstance(result, list) and len(result) >= 1:
            plans = result[:3]
        else:
            plans = []
    except HTTPException:
        raise
    except Exception:
        plans = []

    VALID_CREATIVE_TYPES = {"reversal", "info_gap", "character_arc", "worldview_shatter", "emotion_bomb"}
    SCORE_CONSTRAINTS = {
        "predictability": (3, 7),
        "emotional_impact": (8, 10),
        "logical_coherence": (8, 10),
        "retrospective_value": (7, 10),
    }

    validated_plans = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue

        creative_type = plan.get("creative_type", "")
        if creative_type not in VALID_CREATIVE_TYPES:
            type_mapping = {
                "身份反转": "reversal", "信息反转": "info_gap", "情境反转": "reversal",
                "情感爆发": "emotion_bomb", "多线交汇": "info_gap", "真相揭露": "worldview_shatter",
            }
            old_type = plan.get("type", "")
            creative_type = type_mapping.get(old_type, "reversal")
            plan["creative_type"] = creative_type
            plan.setdefault("creative_type_label", {
                "reversal": "反转", "info_gap": "信息差", "character_arc": "角色弧光",
                "worldview_shatter": "世界观颠覆", "emotion_bomb": "情感核弹",
            }.get(creative_type, "反转"))

        if not plan.get("truth_connection_path") and core_truth:
            plan["truth_connection_path"] = f"本方案与核心真相「{core_truth[:50]}」存在深层关联，具体路径需进一步设计"

        if not plan.get("retrospective_clues"):
            plan["retrospective_clues"] = ["回望线索待补充：需在前文中设计具体暗示"]

        scores = plan.get("scores", {})
        if not isinstance(scores, dict):
            scores = {}

        for dim, (min_val, max_val) in SCORE_CONSTRAINTS.items():
            raw = scores.get(dim)
            if raw is None:
                scores[dim] = min_val
            else:
                try:
                    val = int(raw)
                    scores[dim] = max(min_val, min(max_val, val))
                except (ValueError, TypeError):
                    scores[dim] = min_val

        plan["scores"] = scores

        if "overall_score" not in plan or not isinstance(plan.get("overall_score"), (int, float)):
            p = scores.get("predictability", 5)
            e = scores.get("emotional_impact", 8)
            l = scores.get("logical_coherence", 8)
            r = scores.get("retrospective_value", 7)
            plan["overall_score"] = round(
                (7 - abs(p - 5.5)) * 10 + e * 4 + l * 3 + r * 3
            )

        if "emotional_impact" in plan and "emotional_impact_desc" not in plan:
            plan["emotional_impact_desc"] = plan.pop("emotional_impact", "")

        validated_plans.append(plan)

    if not validated_plans:
        validated_plans = [
            {
                "creative_type": "reversal",
                "creative_type_label": "反转",
                "title": "AI服务暂不可用",
                "summary": "请检查API密钥配置后重试",
                "truth_connection_path": "",
                "retrospective_clues": [],
                "scores": {"predictability": 5, "emotional_impact": 8, "logical_coherence": 8, "retrospective_value": 7},
                "overall_score": 0,
            },
        ]

    return WowPlanResponse(plans=validated_plans)


# ==================== Timeline ====================

@router.get("/projects/{project_id}/timeline")
async def get_project_timeline(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from models.scene import Scene

    result = await db.execute(
        select(Scene)
        .where(Scene.project_id == project_id)
        .order_by(Scene.scene_code)
    )
    scenes = result.scalars().all()

    timeline = []
    for s in scenes:
        timeline.append({
            "id": str(s.id),
            "scene_code": s.scene_code,
            "location": s.location,
            "time_start": s.time_start,
            "time_end": s.time_end,
            "weather": s.weather,
            "emotion_level": s.emotion_level,
            "status": s.status,
            "is_wow_moment": s.is_wow_moment,
            "wow_type": s.wow_type,
            "narration_preview": (s.narration or ""),
            "characters_involved": s.characters_involved,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })

    return {
        "project_id": str(project_id),
        "scene_count": len(timeline),
        "timeline": timeline,
    }


# ==================== Chapter Outline AI ====================

@router.post("/ai/chapter-outline/{project_id}")
async def generate_chapter_outline(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from models.chapter import Chapter as ChapterModel, ChapterSection as ChapterSectionModel
    from models.project_config import ProjectConfig

    runtime = await load_project_runtime(db, project_id)

    config_result = await db.execute(
        select(ProjectConfig).where(ProjectConfig.project_id == project_id)
    )
    config = config_result.scalar_one_or_none()

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.project_id == project_id)
        .order_by(ChapterModel.chapter_number)
    )
    existing = chapters_result.scalars().all()
    existing_info = []
    for ch in existing:
        ch_dict = {
            "chapter_number": ch.chapter_number,
            "title": ch.title or "",
            "emotion_target": ch.emotion_target,
        }
        if ch.summary:
            ch_dict["summary"] = ch.summary
        if hasattr(ch, 'core_conflict') and ch.core_conflict:
            ch_dict["core_conflict"] = ch.core_conflict
        if hasattr(ch, 'key_turning_points') and ch.key_turning_points:
            ch_dict["key_turning_points"] = ch.key_turning_points if isinstance(ch.key_turning_points, list) else []
        if ch.foreshadow_tasks:
            ch_dict["foreshadow_tasks"] = ch.foreshadow_tasks if isinstance(ch.foreshadow_tasks, list) else []
        if hasattr(ch, 'focus_characters') and ch.focus_characters:
            ch_dict["focus_characters"] = ch.focus_characters if isinstance(ch.focus_characters, list) else []
        if hasattr(ch, 'worldview_refs') and ch.worldview_refs:
            ch_dict["worldview_refs"] = ch.worldview_refs if isinstance(ch.worldview_refs, list) else []
        if hasattr(ch, 'sections') and ch.sections:
            section_summaries = []
            for sec in ch.sections:
                sec_info = {
                    "section_number": sec.section_number,
                    "title": sec.title or "",
                    "branch_type": sec.branch_type or "exploration",
                }
                if sec.summary:
                    sec_info["summary"] = sec.summary
                section_summaries.append(sec_info)
            ch_dict["sections"] = section_summaries
        existing_info.append(ch_dict)

    world = await _gather_world_context(db, project_id)
    world_lines = [f"• {k}: {v[:500]}" for k, v in list(world.items())[:10]]
    world_context = "已设定世界观：\n" + "\n".join(world_lines) if world_lines else "世界观尚未设定"

    character_context = await _gather_character_context(db, project_id)

    foreshadow_context = await _gather_foreshadow_context(db, project_id)

    world_config_items = {}
    settings_mapping = {
        "核心矛盾": "core_contradiction",
        "社会结构": "social_structure",
        "科技/魔法体系": "tech_magic",
        "地理环境": "geography",
        "历史背景": "history",
        "文化习俗": "culture",
        "约束条件": "constraints",
        "不可能事项": "impossible",
    }
    for cn_label, config_key in settings_mapping.items():
        val = world.get(cn_label, "")
        if val and isinstance(val, str) and val.strip():
            world_config_items[config_key] = val

    target_chapters = config.chapter_count if config else 10
    target_words = config.target_word_count if config and config.target_word_count else 500000

    system_prompt, user_prompt = build_chapter_outline_prompt(
        runtime.name,
        runtime.genre or "",
        config.tone if config else "neutral",
        target_chapters,
        existing_info,
        world_context,
        character_context,
        target_words=target_words,
        foreshadow_context=foreshadow_context,
        world_config_items=world_config_items,
    )

    try:
        result = await _call_and_parse_json("write.outline", system_prompt, user_prompt,
                                            temperature=0.85, max_tokens=32768, cost_profile="quality")
        outline = result.get("outline", []) if isinstance(result, dict) else []
    except HTTPException:
        raise
    except Exception:
        outline = []

    if not outline:
        outline = [{"title": "AI 服务暂不可用，请稍后重试", "emotion_target": 5}]

    for ch_data in outline:
        if not isinstance(ch_data, dict):
            continue

        ch_number = ch_data.get("chapter_number")
        if ch_number is None:
            continue

        existing_ch = None
        for ech in existing:
            if ech.chapter_number == ch_number:
                existing_ch = ech
                break

        if existing_ch:
            chapter_obj = existing_ch
        else:
            chapter_obj = ChapterModel(
                id=uuid.uuid4(),
                project_id=project_id,
                chapter_number=ch_number,
                title=ch_data.get("title", ""),
                summary=ch_data.get("summary", ""),
                core_conflict=ch_data.get("core_conflict", ""),
                emotion_target=ch_data.get("emotion_target", 5),
                key_turning_points=ch_data.get("turning_points", []),
                foreshadow_tasks=ch_data.get("foreshadow_tasks", []),
                focus_characters=ch_data.get("focus_characters", []),
                worldview_refs=ch_data.get("worldview_refs", []),
                status="draft",
            )
            db.add(chapter_obj)
            await db.flush()

        sections_data = ch_data.get("sections", [])
        if sections_data and isinstance(sections_data, list):
            existing_sections_result = await db.execute(
                select(ChapterSectionModel).where(
                    ChapterSectionModel.chapter_id == chapter_obj.id
                )
            )
            existing_sections = {s.section_number: s for s in existing_sections_result.scalars().all()}

            for sec_data in sections_data:
                if not isinstance(sec_data, dict):
                    continue
                sec_number = sec_data.get("section_number")
                if sec_number is None:
                    continue

                focus_chars = sec_data.get("focus_characters", [])
                if isinstance(focus_chars, list):
                    normalized_focus = []
                    for fc in focus_chars:
                        if isinstance(fc, str):
                            normalized_focus.append(fc)
                        elif isinstance(fc, dict):
                            normalized_focus.append(fc.get("name", str(fc)))
                    focus_chars = normalized_focus

                foreshadow_tasks = sec_data.get("foreshadow_tasks", [])
                if not isinstance(foreshadow_tasks, list):
                    foreshadow_tasks = []

                choices = sec_data.get("choices", [])
                if not isinstance(choices, list):
                    choices = []

                branch_type = sec_data.get("branch_type", "exploration")
                if branch_type not in ("exploration", "decision", "convergence"):
                    branch_type = "exploration"

                if sec_number in existing_sections:
                    sec_obj = existing_sections[sec_number]
                    sec_obj.title = sec_data.get("title", sec_obj.title)
                    sec_obj.word_target = sec_data.get("word_target", sec_obj.word_target)
                    sec_obj.emotion_target = sec_data.get("emotion_target", sec_obj.emotion_target)
                    sec_obj.focus_characters = focus_chars
                    sec_obj.foreshadow_tasks = foreshadow_tasks
                    sec_obj.choices = choices
                    sec_obj.branch_type = branch_type
                    sec_obj.summary = sec_data.get("summary", sec_obj.summary)
                else:
                    sec_obj = ChapterSectionModel(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        chapter_id=chapter_obj.id,
                        section_number=sec_number,
                        title=sec_data.get("title", ""),
                        word_target=sec_data.get("word_target", 1000),
                        emotion_target=sec_data.get("emotion_target", 5),
                        focus_characters=focus_chars,
                        foreshadow_tasks=foreshadow_tasks,
                        choices=choices,
                        branch_type=branch_type,
                        summary=sec_data.get("summary", ""),
                        status="draft",
                    )
                    db.add(sec_obj)

    try:
        await db.commit()
    except Exception as e:
        logger.error("Failed to save chapter sections: %s", str(e))
        await db.rollback()

    return {"outline": outline}


# ==================== Emotion Curve Design ====================

@router.post("/ai/emotion-curve-design/{project_id}")
async def design_emotion_curve(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from models.chapter import Chapter as ChapterModel

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.project_id == project_id)
        .order_by(ChapterModel.chapter_number)
    )
    existing = chapters_result.scalars().all()

    chapters_info = [
        {"number": ch.chapter_number, "title": ch.title or "",
         "emotion_target": ch.emotion_target}
        for ch in existing
    ]

    system_prompt = """你是情感曲线设计专家，擅长优化互动影游剧本的情感节奏。
分析维度：情感起伏、节奏密度、哇塞时刻分布、玩家情绪耗竭曲线。"""

    user_prompt = f"""请分析并优化以下章节的情感分配：

{json.dumps(chapters_info, ensure_ascii=False, indent=2)}

请从全局视野出发，调整各章的情感目标值（0-10），确保：
1. 总体呈波浪式上升
2. 避免连续3章以上高强度
3. 每章之间有合理的落差（1-4点）
4. 结局章为情感巅峰

以JSON格式返回优化后的情感分配方案。"""

    try:
        result = await _call_and_parse_json("analyze.structure", system_prompt, user_prompt,
                                            temperature=0.8, max_tokens=4096)
    except Exception:
        result = []

    optimized = []
    if isinstance(result, dict):
        optimized = result.get("chapters") or result.get("outline") or result.get("emotion_curve") or []
    elif isinstance(result, list):
        optimized = result

    if not optimized and existing:
        fallback_values = []
        chapter_count = len(existing)
        for index, ch in enumerate(existing):
            if chapter_count == 1:
                target_value = 8
            elif index == 0:
                target_value = 4
            elif index == chapter_count - 1:
                target_value = 9
            else:
                target_value = min(8, 5 + index)
            fallback_values.append({
                "chapter_number": ch.chapter_number,
                "emotion_target": target_value,
            })
        optimized = fallback_values

    chapter_by_number = {ch.chapter_number: ch for ch in existing}
    updated = []
    for item in optimized:
        if not isinstance(item, dict):
            continue
        chapter_number = item.get("chapter_number") or item.get("number")
        emotion_target = item.get("emotion_target") or item.get("target_emotion") or item.get("emotion")
        if chapter_number not in chapter_by_number or emotion_target is None:
            continue
        try:
            target_value = max(0, min(10, round(float(emotion_target))))
        except (TypeError, ValueError):
            continue
        chapter = chapter_by_number[chapter_number]
        chapter.emotion_target = target_value
        updated.append({
            "chapter_number": chapter_number,
            "title": chapter.title or f"第{chapter_number}章",
            "emotion_target": target_value,
        })

    if updated:
        await db.commit()
        return {"status": "ok", "message": "情感曲线优化完成", "chapters": updated}

    return {"status": "error", "message": "AI 未返回可应用的情感曲线方案"}


# ==================== Wow Distribution ====================

@router.post("/ai/wow-distribution/{project_id}")
async def optimize_wow_distribution(project_id: uuid.UUID,
                                     db: AsyncSession = Depends(get_db)):
    from models.scene import Scene

    scenes_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_code)
    )
    scenes = scenes_result.scalars().all()

    wow_scenes = [s for s in scenes if s.is_wow_moment]
    total = len(scenes)

    system_prompt = """你是哇塞时刻分布优化专家，擅长在剧本中合理安排反转点和高潮点。
分析维度：反转密度的均匀性、类型多样化、情感梯度的合理性。"""

    user_prompt = f"""请分析以下项目的哇塞时刻分布：

总场景数: {total}
哇塞时刻数: {len(wow_scenes)}
哇塞时刻场景: {json.dumps([{"code": s.scene_code, "type": s.wow_type, "emotion": s.emotion_level} for s in wow_scenes], ensure_ascii=False)}

请提供3-5条优化建议，以JSON数组格式返回。"""

    try:
        result = await _call_and_parse_json("analyze.structure", system_prompt, user_prompt,
                                            temperature=0.8, max_tokens=4096)
        suggestions = []
        if isinstance(result, dict):
            suggestions = result.get("suggestions", result.get("优化建议", []))
            if isinstance(suggestions, str):
                suggestions = [suggestions]
        elif isinstance(result, list):
            suggestions = [str(s) if not isinstance(s, str) else s for s in result[:5]]
        return {"status": "ok", "message": "哇塞时刻分布优化完成", "suggestions": suggestions}
    except HTTPException:
        raise
    except Exception:
        return {"status": "error", "message": "AI 服务暂不可用"}


# ==================== Rhythm Check ====================

@router.post("/ai/rhythm-check/{project_id}")
async def rhythm_check(project_id: uuid.UUID,
                       db: AsyncSession = Depends(get_db)):
    from models.scene import Scene

    scenes_result = await db.execute(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_code)
    )
    scenes = scenes_result.scalars().all()

    if not scenes:
        return {"status": "ok", "rhythm_status": "no_data", "issues": [], "suggestions": []}

    emotion_values = []
    for s in scenes:
        if s.emotion_level is not None:
            try:
                emotion_values.append(int(s.emotion_level))
            except (ValueError, TypeError):
                emotion_values.append(5)

    if not emotion_values:
        return {"status": "ok", "rhythm_status": "no_data", "issues": [], "suggestions": []}

    issues = []
    suggestions = []

    consecutive_high = 0
    for i, e in enumerate(emotion_values):
        if e >= 8:
            consecutive_high += 1
            if consecutive_high >= 2:
                issues.append(f"连续{consecutive_high}个高紧张场景(≥8)，位置: 场景{scenes[i].scene_code if i < len(scenes) else '?'}")
                suggestions.append(f"在场景{scenes[i].scene_code}后插入缓冲场景(情感值≈5)")
        else:
            consecutive_high = 0

    consecutive_low = 0
    for i, e in enumerate(emotion_values):
        if e <= 3:
            consecutive_low += 1
            if consecutive_low >= 3:
                issues.append(f"连续{consecutive_low}个低情感场景(≤3)，位置: 场景{scenes[i].scene_code if i < len(scenes) else '?'}")
                suggestions.append(f"在场景{scenes[i].scene_code}后安排引爆点(情感值≥9)")
        else:
            consecutive_low = 0

    avg_emotion = sum(emotion_values) / len(emotion_values)
    emotion_range = max(emotion_values) - min(emotion_values)

    if not issues:
        rhythm_status = "healthy"
    elif any("高紧张" in i for i in issues):
        rhythm_status = "tension_overload"
    else:
        rhythm_status = "pacing_slow"

    violations = []
    for issue in issues:
        violations.append({
            "chapter": None,
            "type": rhythm_status,
            "detail": issue,
        })

    overall_score = max(0, 100 - len(issues) * 12 - max(0, 6 - int(avg_emotion)) * 2)

    return {
        "status": "ok",
        "rhythm_status": rhythm_status,
        "issues": issues,
        "violations": violations,
        "warnings": [],
        "overall_score": overall_score,
        "suggestions": suggestions,
        "stats": {
            "avg_emotion": round(avg_emotion, 1),
            "emotion_range": emotion_range,
            "scene_count": len(emotion_values),
        },
    }
