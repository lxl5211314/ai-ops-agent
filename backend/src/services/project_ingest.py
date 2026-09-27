import os
import shutil
import tarfile
import uuid
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from core.config import get_settings
from core.errors import UNPROCESSABLE, VALIDATION, AppError
from models.project import (
    STATUS_FAILED,
    STATUS_READY,
    Folder,
    Project,
    SourceFile,
)

TEXT_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cc", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".sh", ".bat", ".sql", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml", ".md", ".txt",
    ".vue", ".svelte", ".kt", ".swift", ".scala", ".gradle", ".properties", ".env",
}

MAX_FILES = 5000
MAX_UNCOMPRESSED = 500 * 1024 * 1024


def create_folder(db: Session, name: str) -> Folder:
    name = (name or "").strip()
    if not name:
        raise AppError(VALIDATION, "文件夹名称不能为空")
    if len(name) > 80:
        raise AppError(VALIDATION, "文件夹名称不能超过 80 个字符")
    existing = db.query(Folder).filter(Folder.name == name).first()
    if existing:
        raise AppError("CONFLICT", "文件夹已存在", {"name": name})
    folder = Folder(name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def validate_path(source_path: str) -> str:
    settings = get_settings()
    raw = (source_path or "").strip()
    if not raw:
        raise AppError(VALIDATION, "源码路径不能为空")
    path = Path(raw).expanduser().resolve()
    roots = settings.allowed_roots
    if not roots:
        raise AppError(
            VALIDATION, "服务端未配置允许的源码根目录（INGEST_ALLOWED_ROOTS），路径接入已禁用"
        )
    if not any(str(path).startswith(root + os.sep) or str(path) == root for root in roots):
        raise AppError(
            VALIDATION, "路径不在允许的目录范围内", {"path": str(path), "allowed_roots": roots}
        )
    if not path.exists():
        raise AppError(VALIDATION, "路径不存在", {"path": str(path)})
    if not path.is_dir():
        raise AppError(VALIDATION, "路径不是目录", {"path": str(path)})
    if not os.access(path, os.R_OK):
        raise AppError(VALIDATION, "路径不可读", {"path": str(path)})
    return str(path)


def storage_dir_for(project_id: uuid.UUID) -> Path:
    base = Path(get_settings().data_dir).expanduser().resolve() / "projects" / str(project_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _scan_tree(db: Session, project: Project, root: Path) -> None:
    count = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        count += 1
        if count > MAX_FILES:
            raise AppError(VALIDATION, f"项目文件数超过上限 {MAX_FILES}")
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        is_text = suffix in TEXT_EXTS or suffix == ""
        if is_text:
            try:
                path.read_text(encoding="utf-8")[:1]
            except (UnicodeDecodeError, OSError):
                is_text = False
        db.add(
            SourceFile(
                project_id=project.id,
                rel_path=rel,
                size_bytes=path.stat().st_size,
                is_text=is_text,
            )
        )
    project.file_count = count


def _extract_archive(archive: Path, dest: Path) -> None:
    total = 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                target = (dest / info.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise AppError(UNPROCESSABLE, "压缩包包含非法路径（zip-slip），已拒绝")
                total += info.file_size
                if total > MAX_UNCOMPRESSED:
                    raise AppError(UNPROCESSABLE, "压缩包解压后体积超过上限")
            zf.extractall(dest)
        return
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                target = (dest / member.name).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise AppError(UNPROCESSABLE, "压缩包包含非法路径，已拒绝")
                total += member.size
                if total > MAX_UNCOMPRESSED:
                    raise AppError(UNPROCESSABLE, "压缩包解压后体积超过上限")
            tf.extractall(dest)
        return
    raise AppError(UNPROCESSABLE, "不支持的压缩包格式（支持 zip / tar.gz）")


def _looks_archive(filename: str) -> bool:
    name = filename.lower()
    return name.endswith((".zip", ".tar.gz", ".tgz", ".tar"))


def ingest_path(db: Session, folder_id: uuid.UUID, name: str, source_path: str) -> Project:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise AppError(VALIDATION, "文件夹不存在")
    resolved = validate_path(source_path)
    dup = db.query(Project).filter(Project.source_path == resolved).first()
    if dup:
        raise AppError("CONFLICT", "该源码路径已接入过", {"project_id": str(dup.id)})
    name = (name or "").strip() or Path(resolved).name
    project = Project(
        folder_id=folder.id,
        name=name,
        source_type="path",
        source_path=resolved,
        storage_dir="",
        status="INGESTING",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    _finalize(db, project, Path(resolved))
    return project


def ingest_upload(
    db: Session, folder_id: uuid.UUID, name: str, files: list[tuple[str, bytes]]
) -> Project:
    folder = db.get(Folder, folder_id)
    if folder is None:
        raise AppError(VALIDATION, "文件夹不存在")
    if not files:
        raise AppError(VALIDATION, "请至少上传一个文件")
    name = (name or "").strip() or (files[0][0] if files else "uploaded")
    project = Project(
        folder_id=folder.id,
        name=name,
        source_type="upload",
        source_path=None,
        storage_dir="",
        status="INGESTING",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    dest = storage_dir_for(project.id)
    try:
        archives = [(fn, data) for fn, data in files if _looks_archive(fn)]
        plain = [(fn, data) for fn, data in files if not _looks_archive(fn)]
        for fn, data in archives:
            tmp = dest / f"__archive_{uuid.uuid4().hex}_{fn}"
            tmp.write_bytes(data)
            try:
                _extract_archive(tmp, dest)
            finally:
                tmp.unlink(missing_ok=True)
        for fn, data in plain:
            target = dest / Path(fn).name
            target.write_bytes(data)
        if not any(p.is_file() for p in dest.rglob("*")):
            raise AppError(UNPROCESSABLE, "压缩包损坏或不包含任何文件")
        _finalize(db, project, dest)
    except AppError as exc:
        db.rollback()
        proj = db.get(Project, project.id)
        proj.status = STATUS_FAILED
        proj.error_message = exc.message
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        proj = db.get(Project, project.id)
        proj.status = STATUS_FAILED
        proj.error_message = f"解压/扫描失败：{exc}"[:500]
        db.commit()
        raise AppError(
            UNPROCESSABLE, "压缩包损坏或不包含有效文件", {"detail": str(exc)}
        ) from exc
    return project


def _finalize(db: Session, project: Project, root: Path) -> None:
    try:
        if project.source_type == "path":
            link = storage_dir_for(project.id)
            if link.exists() and not any(link.iterdir()):
                link.rmdir()
            if not link.exists():
                try:
                    link.symlink_to(root, target_is_directory=True)
                except OSError:
                    shutil.copytree(root, link, dirs_exist_ok=True)
                root = link
        project.storage_dir = str(root)
        db.query(SourceFile).filter(SourceFile.project_id == project.id).delete()
        _scan_tree(db, project, Path(project.storage_dir))
        project.status = STATUS_READY
        project.error_message = None
        db.commit()
    except AppError as exc:
        db.rollback()
        project = db.get(Project, project.id)
        project.status = STATUS_FAILED
        project.error_message = exc.message
        db.commit()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        project = db.get(Project, project.id)
        project.status = STATUS_FAILED
        project.error_message = f"源码扫描失败：{exc}"[:500]
        db.commit()
        raise AppError(VALIDATION, project.error_message) from exc
