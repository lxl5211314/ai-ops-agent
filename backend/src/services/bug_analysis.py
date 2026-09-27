import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from llm.client import LLMClient
from models.analysis import (
    FAILED,
    GENERATING,
    LOCATING,
    SUCCEEDED,
    VALIDATING,
    BugAnalysis,
)
from rag.chunking import extract_keywords
from services.patch_validator import validate_patch

MAX_CANDIDATES = 20
MAX_CONTEXT_CHARS = 60000

GENERATE_PROMPT = """你是资深运维/研发排障专家。基于 Bug 描述与候选代码，只输出 JSON：
{{
  "locations": [{{"file": "相对路径", "line_start": 1, "line_end": 10, "snippet": "关键片段"}}],
  "root_cause": "根因解析：为什么会产生该现象，机理与触发条件",
  "fix_suggestion": "修复建议：怎么改、为什么这样改",
  "patch": "unified diff 补丁（含 a/ b/ 前缀与 @@ 行），无法给出可靠补丁时为空字符串"
}}
规则：patch 必须能用 git apply 应用（路径以 a/ b/ 开头）；不确定时 patch 置空而不是编造。

Bug 描述：
{description}

候选文件：
{context}"""


def _read(path: Path, limit: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


CODE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".sh", ".sql", ".vue", ".kt", ".swift", ".scala",
}


def locate(project_dir: Path, description: str) -> list[dict]:
    keywords = extract_keywords(description, limit=20)
    if not keywords:
        return []
    scored: list[tuple[float, int, str, str]] = []
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(project_dir).as_posix()
        except ValueError:
            continue
        skip_dirs = {".git", "node_modules", "__pycache__", "dist", "build"}
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        content = _read(path, limit=200_000)
        score = 0.0
        low_rel = rel.lower()
        low_content = content.lower()
        for kw in keywords:
            k = kw.lower()
            if k in low_rel:
                score += 3.0
            score += min(low_content.count(k), 10) * 1.0
        if score > 0:
            is_code = 1 if path.suffix.lower() in CODE_EXTS else 0
            scored.append((score, is_code, rel, content))
    scored.sort(key=lambda item: (-item[1], -item[0]))
    out = []
    for score, _code, rel, content in scored[:MAX_CANDIDATES]:
        out.append({"file": rel, "score": score, "content": content})
    return out


def _build_context(candidates: list[dict]) -> str:
    parts = []
    budget = MAX_CONTEXT_CHARS
    for cand in candidates:
        block = f"### 文件: {cand['file']}\n{cand['content']}"
        if budget - len(block) <= 0:
            break
        parts.append(block)
        budget -= len(block)
    return "\n\n".join(parts)


def _normalize_patch(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if not text.endswith("\n"):
        text += "\n"
    return text


def _parse_locations(raw) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "file": str(item.get("file", "")),
                "line_start": int(item.get("line_start") or 0),
                "line_end": int(item.get("line_end") or 0),
                "snippet": str(item.get("snippet", ""))[:2000],
            }
        )
    return out


def _set(analysis_id: uuid.UUID, **fields) -> None:
    from core.db import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(BugAnalysis, analysis_id)
        if row is None:
            return
        for k, v in fields.items():
            setattr(row, k, v)
        db.commit()
    finally:
        db.close()


def _get(analysis_id: uuid.UUID) -> tuple[str, str] | None:
    from core.db import SessionLocal

    db = SessionLocal()
    try:
        row = db.get(BugAnalysis, analysis_id)
        if row is None:
            return None
        project_dir = row.project.storage_dir if row.project else ""
        return row.bug_description, project_dir
    finally:
        db.close()


async def run_analysis(analysis_id: uuid.UUID, llm: LLMClient) -> None:
    from api.streams import publish

    sid = str(analysis_id)
    loaded = _get(analysis_id)
    if loaded is None:
        return
    description, project_dir = loaded
    project_path = Path(project_dir)

    try:
        _set(analysis_id, status=LOCATING)
        publish(sid, "stage", {"stage": "locating"})
        await asyncio.sleep(0)
        candidates = locate(project_path, description)
        located = [
            {
                "file": c["file"],
                "line_start": 1,
                "line_end": min(200, c["content"].count("\n") + 1),
                "snippet": c["content"][:400],
            }
            for c in candidates[:10]
        ]
        _set(analysis_id, located_files=located)
        publish(sid, "located", {"files": located})

        if not candidates:
            raise RuntimeError("未能在项目中找到与描述相关的代码，请补充更多关键词或报错信息")

        _set(analysis_id, status=GENERATING)
        publish(sid, "stage", {"stage": "generating"})
        prompt = GENERATE_PROMPT.format(
            description=description, context=_build_context(candidates)
        )
        result = await llm.chat_json([{"role": "user", "content": prompt}])
        patch_text = _normalize_patch(str(result.get("patch") or ""))
        root_cause = str(result.get("root_cause") or "").strip()
        fix_suggestion = str(result.get("fix_suggestion") or "").strip()
        locations = _parse_locations(result.get("locations"))
        if locations:
            _set(analysis_id, located_files=locations)
            publish(sid, "located", {"files": locations})
        if not root_cause and not patch_text:
            raise RuntimeError("模型未能给出有效的分析结果，请补充复现步骤或报错日志")

        _set(
            analysis_id,
            root_cause=root_cause,
            fix_suggestion=fix_suggestion,
            patch_text=patch_text or None,
        )

        _set(analysis_id, status=VALIDATING)
        publish(sid, "stage", {"stage": "validating"})
        applicable, log = False, "未生成补丁，无需应用校验"
        if patch_text:
            applicable, log = validate_patch(project_path, patch_text)
            if not applicable:
                retry_prompt = (
                    prompt
                    + "\n\n上次补丁无法应用，错误信息：\n"
                    + log
                    + "\n请修正 patch 后重新输出完整 JSON。"
                )
                try:
                    result = await llm.chat_json([{"role": "user", "content": retry_prompt}])
                    patch_text = _normalize_patch(str(result.get("patch") or ""))
                    if patch_text:
                        _set(analysis_id, patch_text=patch_text)
                        applicable, log = validate_patch(project_path, patch_text)
                except Exception as retry_exc:  # noqa: BLE001
                    log = f"{log}\n重试失败: {retry_exc}"

        _set(
            analysis_id,
            status=SUCCEEDED,
            patch_applicable=applicable,
            validation_log=log,
            finished_at=datetime.now(UTC).replace(tzinfo=None),
        )
        publish(
            sid,
            "done",
            {"analysis_id": sid, "status": "succeeded", "patch_applicable": applicable},
        )
    except Exception as exc:  # noqa: BLE001
        _set(
            analysis_id,
            status=FAILED,
            error_message=str(exc)[:1000],
            finished_at=datetime.now(UTC).replace(tzinfo=None),
        )
        publish(
            sid,
            "error",
            {
                "code": "INTERNAL",
                "message": str(exc)[:500],
                "hint": "可补充：更精确的报错文本、复现步骤、涉及模块名",
            },
        )
        publish(sid, "done", {"analysis_id": sid, "status": "failed"})


def start_analysis(analysis_id: uuid.UUID, llm: LLMClient) -> None:
    asyncio.create_task(run_analysis(analysis_id, llm))
