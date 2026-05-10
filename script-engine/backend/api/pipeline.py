"""
Pipeline API 路由: 流程状态查询、自动运行与模板查询。
使用全局ModelGateway单例，复用连接池。
"""

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, async_session_factory
from core.pipeline.state_machine import PipelineStateMachine, PipelineStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/pipeline")
public_router = APIRouter(prefix="/pipeline")


async def _get_executor(project_id: str, db: AsyncSession, target_phases: list[str] | None = None):
    from core.gateway.client import get_gateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.pipeline.executor import PipelineExecutor

    gateway = get_gateway()
    rag = RAGRetriever(db)
    storage = StorageService(db)
    return PipelineExecutor(db, gateway, rag, storage, target_phases=target_phases)


@router.get("/status")
async def get_pipeline_status(project_id: str, db: AsyncSession = Depends(get_db)):
    sm = PipelineStateMachine(db)
    state = await sm.get_state(project_id)
    if not state:
        return {"status": "not_initialized"}
    return {
        "status": state.status.value,
        "current_phase": state.current_phase_index,
        "current_step": state.current_step_index,
        "template": state.template_name,
        "error_message": state.error_message,
        "task_results": state.task_results[-10:] if state.task_results else [],
    }


@router.post("/advance")
async def advance_pipeline(project_id: str, db: AsyncSession = Depends(get_db)):
    executor = await _get_executor(project_id, db)
    return await executor.advance(project_id)


@router.post("/auto-run")
async def auto_run_pipeline(project_id: str, background_tasks: BackgroundTasks,
                             db: AsyncSession = Depends(get_db)):
    from core.pipeline.template_loader import get_template, list_templates
    from core.pipeline.state_machine import PipelineStatus

    sm = PipelineStateMachine(db)
    state = await sm.get_state(project_id)

    # 如果流水线正在运行中，拒绝重复启动
    if state and state.status == PipelineStatus.RUNNING:
        raise HTTPException(status_code=409, detail="流水线正在运行中，请勿重复启动")

    if state and state.status in (PipelineStatus.FAILED, PipelineStatus.COMPLETED, PipelineStatus.CANCELLED):
        await sm.reset(project_id)
        state = None

    if not state:
        templates = list_templates()
        if not templates:
            raise HTTPException(status_code=400, detail="没有可用的流水线模板")

        default_template = templates[0]["name"]
        template = get_template(default_template)
        await sm.init(project_id, default_template)

        config_data = {}
        try:
            from core.storage.service import StorageService
            storage = StorageService(db)
            config = await storage.get_project_config(project_id)
            if config:
                def _s(key, default=""):
                    v = config.get(key, default)
                    return v if v is not None else default
                config_data = {
                    "genre": _s("genre"),
                    "style": _s("style") or _s("writing_style"),
                    "core_contradiction": _s("core_contradiction"),
                    "target_word_count": _s("target_word_count", 50000),
                    "chapter_count": _s("chapter_count", 10),
                    "world_building_depth": _s("world_building_depth", 5),
                    "character_depth_target": _s("character_depth_target", 5),
                    "character_count": _s("character_count", 6),
                    "character_dynamic_count": max(15, min(70, int(_s("target_word_count", 50000)) / 5000)),
                    "plot_complexity": _s("plot_complexity", 5),
                    "min_words_per_chapter": _s("min_words_per_chapter", 2000),
                    "max_words_per_chapter": _s("max_words_per_chapter", 8000),
                    "scenes_per_chapter_min": _s("scenes_per_chapter_min", 3),
                    "scenes_per_chapter_max": _s("scenes_per_chapter_max", 6),
                    "core_truth": _s("core_contradiction"),
                    "theme": _s("theme"),
                    "tone": _s("tone", "neutral"),
                    "user_requirements": _s("description"),
                }
                for key, val in config_data.items():
                    await sm.update_result_data(project_id, key, val)
        except Exception as e:
            logger.warning("注入项目配置到流水线失败: %s", e)

        await sm.transition(project_id, PipelineStatus.RUNNING)

        from websocket.manager import ws_manager
        await ws_manager.broadcast_to_project(project_id, {
            "type": "pipeline_progress",
            "phase": "初始化",
            "phase_index": 0,
            "step_index": 0,
            "total_steps": sum(len(p.steps) for p in template.phases),
            "agent": "系统",
            "skill": "init",
            "status": "running",
            "message": f"流水线初始化完成，共{len(template.phases)}个阶段",
            "progress": 0,
            "phases": [{"name": p.name, "steps": len(p.steps), "human_gate": p.human_gate} for p in template.phases],
            "total_phases": len(template.phases),
        })

    async def _run():
        async with async_session_factory() as task_db:
            executor = await _get_executor(project_id, task_db)
            await executor.auto_run(project_id)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "流水线自动运行已启动，请关注顶部进度条"}


@router.post("/cancel")
async def cancel_pipeline(project_id: str, db: AsyncSession = Depends(get_db)):
    executor = await _get_executor(project_id, db)
    await executor.cancel(project_id)
    return {"status": "cancelled", "message": "流水线已取消"}


@router.post("/approve")
async def approve_phase(project_id: str, db: AsyncSession = Depends(get_db)):
    sm = PipelineStateMachine(db)
    await sm.approve(project_id)
    return {"status": "approved"}


@router.post("/reject")
async def reject_phase(project_id: str, payload: dict | None = Body(default=None), db: AsyncSession = Depends(get_db)):
    payload = payload or {}
    reason = payload.get("reason", "")
    sm = PipelineStateMachine(db)
    state = await sm.get_state(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline未初始化")
    task_key = f"{state.current_phase_index}-{state.current_step_index}"
    await sm.handle_rejection(project_id, task_key, reason=reason)
    return {"status": "rejected", "reason": reason}


@router.post("/retry")
async def retry_pipeline(project_id: str, db: AsyncSession = Depends(get_db)):
    sm = PipelineStateMachine(db)
    state = await sm.get_state(project_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline未初始化")
    if state.status.value != "failed":
        raise HTTPException(status_code=400, detail="只能重试处于失败状态的流水线")
    try:
        await sm.retry(project_id)
        return {"status": "retrying", "message": "已从失败步骤重新开始"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume")
async def resume_pipeline(project_id: str, background_tasks: BackgroundTasks,
                           db: AsyncSession = Depends(get_db)):
    """从失败处继续运行流水线，保留已完成的步骤结果"""
    try:
        sm = PipelineStateMachine(db)
        state = await sm.get_state(project_id)

        if not state:
            raise HTTPException(status_code=404, detail="Pipeline未初始化，请先启动流水线")

        if state.status == PipelineStatus.RUNNING:
            raise HTTPException(status_code=409, detail="流水线正在运行中，请勿重复启动")

        if state.status not in (PipelineStatus.FAILED, PipelineStatus.CANCELLED):
            raise HTTPException(status_code=400, detail=f"只能从失败/取消状态恢复，当前状态: {state.status.value}")

        state.status = PipelineStatus.RUNNING
        state.error_message = ""
        results = list(state.task_results)
        current_key = f"{state.current_phase_index}-{state.current_step_index}"
        for i, tr in enumerate(results):
            if tr.get("key") == current_key and tr.get("status") in ("failed", "cancelled"):
                from datetime import datetime, timezone
                results[i] = {**tr, "status": "retrying", "retried_at": datetime.now(timezone.utc).isoformat()}
                break
        state.task_results = results
        await sm._save(state)

        async def _run():
            async with async_session_factory() as task_db:
                executor = await _get_executor(project_id, task_db)
                await executor.auto_run(project_id)

        background_tasks.add_task(_run)
        return {
            "status": "resumed",
            "message": f"流水线已从失败处恢复（阶段{state.current_phase_index}，步骤{state.current_step_index}）",
            "current_phase": state.current_phase_index,
            "current_step": state.current_step_index,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Resume pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"恢复流水线失败: {str(e)[:200]}")


@public_router.get("/templates")
async def list_pipeline_templates():
    from core.pipeline.template_loader import list_templates as _list
    return {"templates": _list()}


@router.post("/generate-script")
async def generate_script(project_id: str, payload: dict | None = Body(default=None), db: AsyncSession = Depends(get_db)):
    """
    一键生成完整剧本的统一入口。
    严格按照依赖顺序执行: 世界观 -> 角色 -> 关系网 -> 伏笔 -> 大纲 -> 场景
    """
    from core.pipeline.state_machine import PipelineStateMachine, PipelineStatus
    from core.pipeline.template_loader import get_template
    from core.gateway.client import get_gateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.pipeline.executor import PipelineExecutor

    sm = PipelineStateMachine(db)
    state = await sm.get_state(project_id)

    if state and state.status == PipelineStatus.RUNNING:
        raise HTTPException(status_code=400, detail="流水线正在运行中，请等待完成或取消后重试")

    await sm.reset(project_id)

    template = get_template("interactive_drama")
    await sm.init(project_id, "interactive_drama")

    config_data = {}
    try:
        storage = StorageService(db)
        config = await storage.get_project_config(project_id)
        if config:
            def _s(key, default=""):
                v = config.get(key, default)
                return v if v is not None else default
            config_data = {
                "genre": _s("genre"),
                "style": _s("style") or _s("writing_style"),
                "core_contradiction": _s("core_contradiction"),
                "target_word_count": _s("target_word_count", 50000),
                "chapter_count": _s("chapter_count", 10),
                "world_building_depth": _s("world_building_depth", 5),
                "character_depth_target": _s("character_depth_target", 5),
                "character_count": _s("character_count", 6),
                "character_dynamic_count": max(15, min(70, int(_s("target_word_count", 50000)) / 5000)),
                "plot_complexity": _s("plot_complexity", 5),
                "min_words_per_chapter": _s("min_words_per_chapter", 2000),
                "max_words_per_chapter": _s("max_words_per_chapter", 8000),
                "scenes_per_chapter_min": _s("scenes_per_chapter_min", 3),
                "scenes_per_chapter_max": _s("scenes_per_chapter_max", 6),
                "core_truth": _s("core_contradiction"),
                "theme": _s("theme"),
                "tone": _s("tone", "neutral"),
                "user_requirements": _s("description"),
            }
            for key, val in config_data.items():
                await sm.update_result_data(project_id, key, val)
    except Exception as e:
        logger.warning("注入项目配置失败: %s", e)

    await sm.transition(project_id, PipelineStatus.RUNNING)

    gateway = get_gateway()
    rag = RAGRetriever(db)
    storage = StorageService(db)
    executor = PipelineExecutor(db, gateway, rag, storage)

    payload = payload or {}
    generation_config = {
        "auto_run": payload.get("auto_run", True),
        "target_phases": payload.get("target_phases", ["设定", "大纲", "场景创作"]),
        "max_scenes": payload.get("max_scenes", None),
    }

    if generation_config["auto_run"]:
        import asyncio
        target_phases = generation_config.get("target_phases") or None
        async def _run_generation():
            async with async_session_factory() as task_db:
                gw = get_gateway()
                r = RAGRetriever(task_db)
                s = StorageService(task_db)
                exec_obj = PipelineExecutor(task_db, gw, r, s, target_phases=target_phases)
                await exec_obj.auto_run(project_id)

        asyncio.create_task(_run_generation())
        return {
            "status": "started",
            "message": "剧本生成已启动，系统将按顺序生成: 世界观 -> 角色 -> 关系网 -> 伏笔 -> 大纲 -> 场景",
            "project_id": project_id,
            "phases": [{"name": p.name, "steps": len(p.steps)} for p in template.phases],
        }
    else:
        return {
            "status": "initialized",
            "message": "剧本生成流水线已初始化，请调用 /advance 逐步执行",
            "project_id": project_id,
            "next_action": "POST /api/projects/{project_id}/pipeline/advance",
        }


@router.post("/generate-full-script")
async def generate_full_script(project_id: str, db: AsyncSession = Depends(get_db)):
    """
    使用剧本生成引擎直接生成完整剧本内容。
    此接口会直接调用LLM为每个场景生成完整的narration、dialogue和actions。
    前置要求: 项目必须已有大纲(chapters)。
    """
    from core.script_generator.engine import ScriptGenerationEngine

    engine = ScriptGenerationEngine(db)

    try:
        result = await engine.generate_full_script(project_id)
        return {
            "status": "success",
            "message": f"剧本生成完成！共生成 {result['total_scenes']} 个场景，约 {result['total_words']} 字",
            "data": {
                "total_chapters": result["total_chapters"],
                "total_scenes": result["total_scenes"],
                "total_words": result["total_words"],
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("剧本生成失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"剧本生成失败: {str(e)}")
