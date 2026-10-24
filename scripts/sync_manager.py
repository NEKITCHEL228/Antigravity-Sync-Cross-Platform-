#!/usr/bin/env python3
"""
Antigravity Cross-Platform Sync Manager
Secure, dependency-free synchronization for Antigravity (Git, Google Drive, Projects, and Conversations).
Supports full conversation history and context continuity across macOS, Linux, and Windows.
"""

import os
import sys
import json
import shutil
import re
import fnmatch
import platform
import subprocess
import sqlite3
import urllib.parse
from datetime import datetime
from pathlib import Path

# Base Paths
PLUGIN_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PLUGIN_DIR / "config.json"
PROJECTS_FILE = PLUGIN_DIR / "projects.json"

HOME = Path.home()
GEMINI_DIR = HOME / ".gemini"
GEMINI_CONFIG = GEMINI_DIR / "config"
GEMINI_ANTIGRAVITY = GEMINI_DIR / "antigravity"
GEMINI_BRAIN = GEMINI_ANTIGRAVITY / "brain"
GEMINI_CONVERSATIONS = GEMINI_ANTIGRAVITY / "conversations"
GEMINI_ANNOTATIONS = GEMINI_ANTIGRAVITY / "annotations"
GEMINI_PRESENCE = GEMINI_ANTIGRAVITY / "presence"
GEMINI_SCRATCH = GEMINI_ANTIGRAVITY / "scratch"
DEFAULT_GIT_SYNC_DIR = HOME / ".antigravity-sync"

SYSTEM_OS = platform.system()  # 'Darwin', 'Linux', 'Windows'

# ----------------------------------------------------
# Security & Exclusion Rules
# ----------------------------------------------------
# Sensitive files that must NEVER be synced (prevent credential leakage)
SENSITIVE_EXCLUDES = [
    ".env*",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.pkcs12",
    "id_rsa*", "id_ed25519*", "id_ecdsa*", "id_dsa*",
    "*token*", "*credential*", "*secret*",
    "jetski-standalone-oauth-token",
    "*.sqlite-wal", "*.db-wal", "*.db-shm", "*.lock",
    ".git/credentials", ".git/config",
    "*.dump"
]

# Heavy directories and cache files
BUILD_CACHE_EXCLUDES = [
    "node_modules",
    ".git",
    ".venv", "venv", "env",
    "__pycache__", "*.pyc",
    "dist", "build", ".next", ".nuxt", ".output",
    ".cache", ".turbo", "target",
    ".DS_Store", "Thumbs.db", "desktop.ini",
    "*.tmp"
]

# Combined project excludes
PROJECT_EXCLUDES = SENSITIVE_EXCLUDES + BUILD_CACHE_EXCLUDES

# Config folder specific excludes
CONFIG_EXCLUDES = SENSITIVE_EXCLUDES + [
    "node_modules",
    ".DS_Store",
    "Thumbs.db"
]

# Brain artifacts excludes (Preserves transcript.jsonl, steps, and messages for full conversation context)
BRAIN_EXCLUDES = SENSITIVE_EXCLUDES + [
    "*.lock",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini"
]


# ----------------------------------------------------
# Helper Functions: Atomic JSON & Safety
# ----------------------------------------------------
def atomic_write_json(file_path: Path, data: dict):
    """Write JSON file atomically to prevent corruption during unexpected exits."""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = file_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, file_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "git_sync_dir": str(DEFAULT_GIT_SYNC_DIR),
        "gdrive_path": "",
        "sync_conversations": True,
        "default_projects_dir": str(HOME / "Developer")
    }


def save_config(cfg: dict):
    atomic_write_json(CONFIG_FILE, cfg)


def get_default_projects_dir() -> Path:
    cfg = load_config()
    custom_dir = cfg.get("default_projects_dir")
    if custom_dir:
        p = Path(os.path.expanduser(custom_dir))
        return p
    return HOME / "Developer"


def load_projects() -> dict:
    if PROJECTS_FILE.exists():
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"projects": []}


def save_projects(data: dict):
    atomic_write_json(PROJECTS_FILE, data)


def is_safe_project_path(p: Path, target_os: str = None) -> tuple:
    """Validate project path against directory traversal and critical system targets across OSes."""
    s = str(p).strip()
    if not s:
        return False, "Путь не может быть пустым."

    # Windows-format path check (whether running on Windows or evaluating Windows path on Mac/Linux)
    is_win_format = bool(re.match(r"^[a-zA-Z]:[\\/]", s)) or (target_os == "Windows")
    if is_win_format:
        s_norm = s.lower().replace("/", "\\")
        # Drive root forbidden (e.g. C:\)
        if re.match(r"^[a-zA-Z]:\\?$", s_norm):
            return False, "Нельзя добавлять корневой каталог диска Windows."
        win_forbidden = [
            ":\\windows", ":\\program files", ":\\program files (x86)",
            ":\\system volume information", ":\\$recycle.bin", ":\\recovery"
        ]
        for win_fb in win_forbidden:
            if win_fb in s_norm:
                return False, f"Запрещено добавлять системный каталог Windows ({win_fb})."
        return True, "OK"

    # POSIX path check
    try:
        resolved = Path(os.path.expanduser(s)).resolve()
    except Exception as e:
        return False, f"Некорректный путь: {e}"

    # Do not allow system roots
    if resolved == resolved.parent:
        return False, "Нельзя добавлять корневой каталог диска."

    # Do not allow user home itself
    if resolved == HOME:
        return False, "Нельзя добавлять всю домашнюю папку пользователя целиком."

    # Do not allow internal Antigravity data directories as standalone projects
    if resolved == GEMINI_DIR or resolved in GEMINI_DIR.parents or GEMINI_DIR in resolved.parents:
        return False, "Внутренняя папка Antigravity (.gemini) уже синхронизируется автоматически."

    if resolved == DEFAULT_GIT_SYNC_DIR or DEFAULT_GIT_SYNC_DIR in resolved.parents:
        return False, "Нельзя добавлять служебную папку синхронизации в качестве проекта."

    posix_str = str(resolved).rstrip("/")

    # POSIX system directories
    posix_forbidden = [
        "/etc", "/bin", "/sbin", "/usr", "/System", "/Library",
        "/boot", "/dev", "/proc", "/sys", "/var", "/private/etc", "/private/var", "/root"
    ]
    for fb in posix_forbidden:
        if posix_str == fb or posix_str.startswith(fb + "/"):
            return False, f"Запрещено добавлять системный каталог ({fb})."

    return True, "OK"


def is_valid_git_url(url: str) -> bool:
    """Validate Git repository URL to prevent flag and argument injection."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if url.startswith("-") or url.startswith("ext::"):
        return False
    # Standard URL protocols: https, http, ssh, git
    if re.match(r"^(https?|ssh|git)://[a-zA-Z0-9_\-\.]+(:[0-9]+)?/[a-zA-Z0-9_\-\./~]+(\.git)?/?$", url):
        return True
    # SCP-style: user@host:path.git
    if re.match(r"^[a-zA-Z0-9_\-]+@[a-zA-Z0-9_\-\.]+:[a-zA-Z0-9_\-\./~]+(\.git)?/?$", url):
        return True
    return False


def match_any(name: str, patterns: list) -> bool:
    """Case-insensitive pattern matching for cross-platform consistency."""
    name_norm = name.lower()
    for pat in patterns:
        if fnmatch.fnmatch(name_norm, pat.lower()):
            return True
    return False


# ----------------------------------------------------
# SQLite Backup & Merge for Conversations
# ----------------------------------------------------
def backup_sqlite_db(src_path: Path, dst_path: Path) -> bool:
    """Safely snapshot a live SQLite database with WAL commits into a standalone file."""
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    if not src_path.exists():
        return False

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        src_conn = sqlite3.connect(str(src_path))
        dst_conn = sqlite3.connect(str(dst_path))
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        return True
    except Exception as e:
        print(f"[Warn] Ошибка резервного копирования базы {src_path.name}: {e}")
        return False


def merge_summaries_db(src_db: Path, local_db: Path):
    """Merges conversation summaries across multiple devices without data loss."""
    src_db = Path(src_db)
    local_db = Path(local_db)
    if not src_db.exists():
        return

    if not local_db.exists():
        backup_sqlite_db(src_db, local_db)
        return

    try:
        conn = sqlite3.connect(str(local_db))
        conn.execute(f"ATTACH DATABASE \"{src_db}\" AS remote_summary")
        c = conn.cursor()
        c.execute("SELECT name FROM remote_summary.sqlite_master WHERE type='table' AND name='conversation_summaries'")
        if c.fetchone():
            conn.execute("""
                INSERT OR REPLACE INTO conversation_summaries
                SELECT * FROM remote_summary.conversation_summaries;
            """)
            conn.commit()
        conn.execute("DETACH DATABASE remote_summary")
        conn.close()
    except Exception as e:
        print(f"[Warn] Ошибка объединения conversation_summaries.db: {e}")


def heal_workspace_uris(db_path: Path):
    """
    Fixes foreign/missing OS paths in conversation_summaries.db across macOS, Windows, and Linux.
    Prevents 'Missing folder' / 'Пропавшая папка' warnings when opening chats synced from another OS.
    Automatically binds workspaces to each project's configured local directory.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return

    default_projects_dir = get_default_projects_dir()
    scratch_dir = GEMINI_ANTIGRAVITY / "scratch"
    default_projects_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    projects_data = load_projects()
    tracked_projects = {p["name"].lower(): Path(p["path"]) for p in projects_data.get("projects", [])}

    try:
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("SELECT conversation_id, workspace_uris FROM conversation_summaries;")
        rows = c.fetchall()

        updates = []
        for cid, uris_raw in rows:
            if not uris_raw:
                continue
            try:
                uris = json.loads(uris_raw)
            except Exception:
                continue

            new_uris = []
            changed = False

            for u in uris:
                if not u.startswith("file://"):
                    new_uris.append(u)
                    continue

                unquoted = urllib.parse.unquote(u[7:])

                # Detect cross-OS format differences (Windows drive letters vs Unix paths)
                is_win_format = (len(unquoted) >= 3 and unquoted[0] == "/" and unquoted[2] == ":") or (len(unquoted) >= 2 and unquoted[1] == ":") or (":\\" in unquoted)
                is_unix_format = unquoted.startswith("/") and not (len(unquoted) >= 3 and unquoted[2] == ":")

                is_foreign = (SYSTEM_OS != "Windows" and is_win_format) or (SYSTEM_OS == "Windows" and is_unix_format)

                if is_win_format and unquoted.startswith("/"):
                    local_path_str = unquoted[1:]
                else:
                    local_path_str = unquoted

                path_obj = Path(local_path_str)

                # If path exists locally on this machine, keep it as-is
                if not is_foreign and path_obj.exists():
                    new_uris.append(u)
                    continue

                changed = True
                base_name = path_obj.name or "workspace"

                matched_target = None
                for proj_name, proj_path in tracked_projects.items():
                    if (proj_name == base_name.lower() or
                        proj_name in base_name.lower() or
                        base_name.lower() in proj_name or
                        "дизайн" in base_name.lower() and "design" in proj_name):
                        matched_target = proj_path
                        break

                if matched_target:
                    matched_target.mkdir(parents=True, exist_ok=True)
                    new_uris.append(matched_target.as_uri())
                elif "antigravity" in str(path_obj).lower():
                    local_target = scratch_dir / base_name
                    local_target.mkdir(parents=True, exist_ok=True)
                    new_uris.append(local_target.as_uri())
                else:
                    local_target = default_projects_dir / base_name
                    local_target.mkdir(parents=True, exist_ok=True)
                    new_uris.append(local_target.as_uri())

            if changed:
                updates.append((json.dumps(new_uris), cid))

        for new_val, cid in updates:
            c.execute("UPDATE conversation_summaries SET workspace_uris = ? WHERE conversation_id = ?;", (new_val, cid))

        conn.commit()
        conn.close()
        if updates:
            print(f"[Antigravity Sync] Исправлены пути к рабочим папкам для {len(updates)} диалогов.")
    except Exception as e:
        print(f"[Warn] Ошибка адаптации путей рабочих папок: {e}")


# ----------------------------------------------------
# Pure-Python Cross-Platform File Synchronizer
# ----------------------------------------------------
def sync_tree(src: Path, dst: Path, excludes: list, delete: bool = False) -> tuple:
    """
    Pure Python directory synchronizer.
    Works natively on Windows, Linux, and macOS without rsync or external dependencies.
    Safely ignores symlink loops and respects exclusions.
    """
    src = Path(src).resolve()
    dst = Path(dst).resolve()

    if not src.exists():
        return False, 0, f"Исходная папка не существует: {src}"

    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    all_target_rel_paths = set()

    for root, dirs, files in os.walk(src, followlinks=False):
        try:
            rel_root = Path(root).relative_to(src)
        except ValueError:
            continue

        # In-place directory filtering
        dirs[:] = [d for d in dirs if not match_any(d, excludes)]

        target_dir = dst / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)

        for f in files:
            if match_any(f, excludes):
                continue

            src_file = Path(root) / f
            dst_file = target_dir / f
            rel_file = rel_root / f
            all_target_rel_paths.add(str(rel_file))

            need_copy = False
            try:
                if not dst_file.exists():
                    need_copy = True
                elif src_file.is_file() and dst_file.is_file():
                    s_stat = src_file.stat()
                    d_stat = dst_file.stat()
                    if s_stat.st_size != d_stat.st_size or abs(s_stat.st_mtime - d_stat.st_mtime) > 1.0:
                        need_copy = True

                if need_copy:
                    shutil.copy2(src_file, dst_file, follow_symlinks=False)
                    copied += 1
            except Exception:
                pass

    if delete:
        for root, dirs, files in os.walk(dst, followlinks=False):
            try:
                rel_root = Path(root).relative_to(dst)
            except ValueError:
                continue

            for f in files:
                rel_file = rel_root / f
                if str(rel_file) not in all_target_rel_paths and not match_any(f, excludes):
                    try:
                        (Path(root) / f).unlink()
                    except OSError:
                        pass

    return True, copied, "OK"


# ----------------------------------------------------
# Target Sync Utilities (Config, Brain, Conversations, Projects)
# ----------------------------------------------------
def copy_all_to_target(target_dir: Path):
    """
    Copies configurations, conversation histories (with context and steps),
    brain artifacts, and registered projects to target directory.
    """
    target_dir = Path(target_dir)

    # 1. Antigravity Configuration
    if GEMINI_CONFIG.exists():
        dst = target_dir / "config"
        sync_tree(GEMINI_CONFIG, dst, CONFIG_EXCLUDES, delete=True)

    # 2. Conversation Trajectories & Messages
    if GEMINI_CONVERSATIONS.exists():
        conv_target = target_dir / "data" / "conversations"
        conv_target.mkdir(parents=True, exist_ok=True)
        for db_file in GEMINI_CONVERSATIONS.glob("*.db"):
            dst_db = conv_target / db_file.name
            backup_sqlite_db(db_file, dst_db)

    # 3. Conversation Summaries (Sidebar History List)
    summary_db = GEMINI_ANTIGRAVITY / "conversation_summaries.db"
    if summary_db.exists():
        backup_sqlite_db(summary_db, target_dir / "data" / "conversation_summaries.db")
        heal_workspace_uris(target_dir / "data" / "conversation_summaries.db")

    proto_file = GEMINI_ANTIGRAVITY / "agyhub_summaries_proto.pb"
    if proto_file.exists():
        (target_dir / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy2(proto_file, target_dir / "data" / proto_file.name)

    # 4. Annotations
    if GEMINI_ANNOTATIONS.exists():
        ann_target = target_dir / "data" / "annotations"
        ann_target.mkdir(parents=True, exist_ok=True)
        for ann in GEMINI_ANNOTATIONS.glob("*.pbtxt"):
            shutil.copy2(ann, ann_target / ann.name)

    # 5. Brain Artifacts & Conversation Transcripts (Context preservation)
    if GEMINI_BRAIN.exists():
        dst = target_dir / "data" / "brain"
        sync_tree(GEMINI_BRAIN, dst, BRAIN_EXCLUDES, delete=False)

    # 6. User Projects
    projects_data = load_projects()
    if projects_data.get("projects"):
        projects_target = target_dir / "projects"
        projects_target.mkdir(parents=True, exist_ok=True)

        # Merge with existing registry in target to preserve cross-OS target paths
        remote_reg_file = target_dir / "projects_registry.json"
        if remote_reg_file.exists():
            try:
                with open(remote_reg_file, "r", encoding="utf-8") as f:
                    old_remote = json.load(f)
                old_remote_projects = {p["name"]: p for p in old_remote.get("projects", [])}
                for prj in projects_data["projects"]:
                    p_name = prj["name"]
                    if p_name in old_remote_projects:
                        rem_p = old_remote_projects[p_name]
                        rem_targets = rem_p.get("target_paths", {})
                        local_targets = prj.setdefault("target_paths", {})
                        for os_k, val in rem_targets.items():
                            if os_k not in local_targets:
                                local_targets[os_k] = val
                        if not prj.get("custom_path") and rem_p.get("custom_path"):
                            prj["custom_path"] = rem_p["custom_path"]
            except Exception:
                pass

        # Save registry snapshot into target
        atomic_write_json(target_dir / "projects_registry.json", projects_data)

        for prj in projects_data["projects"]:
            src_p = Path(prj["path"])
            if src_p.exists():
                dst_p = projects_target / prj["name"]
                sync_tree(src_p, dst_p, PROJECT_EXCLUDES, delete=True)


def restore_all_from_target(target_dir: Path):
    """
    Restores configurations, conversation histories (with context and steps),
    brain artifacts, and registered projects from target directory.
    """
    target_dir = Path(target_dir)

    # 1. Configuration
    src = target_dir / "config"
    if src.exists():
        GEMINI_CONFIG.mkdir(parents=True, exist_ok=True)
        ok, cnt, err = sync_tree(src, GEMINI_CONFIG, CONFIG_EXCLUDES, delete=False)
        if ok:
            print("[Antigravity Sync] Конфигурация успешно восстановлена.")
        else:
            print(f"[Error] Сбой восстановления конфигурации: {err}")

    # 2. Conversation Trajectories & Context (*.db)
    remote_conv = target_dir / "data" / "conversations"
    if remote_conv.exists():
        GEMINI_CONVERSATIONS.mkdir(parents=True, exist_ok=True)
        restored_count = 0
        for remote_db in remote_conv.glob("*.db"):
            local_db = GEMINI_CONVERSATIONS / remote_db.name
            conv_id = remote_db.stem
            # Check if conversation is currently active on this machine
            is_active = (GEMINI_PRESENCE / f"{conv_id}.lock").exists() if GEMINI_PRESENCE.exists() else False

            if not is_active:
                shutil.copy2(remote_db, local_db)
                restored_count += 1
            else:
                # If active locally, compare modification times
                if not local_db.exists() or remote_db.stat().st_mtime > local_db.stat().st_mtime:
                    try:
                        shutil.copy2(remote_db, local_db)
                        restored_count += 1
                    except Exception:
                        pass
        print(f"[Antigravity Sync] Диалоги и контекст моделей восстановлены ({restored_count} шт).")

    # 3. Conversation Summaries (Sidebar History)
    remote_summaries = target_dir / "data" / "conversation_summaries.db"
    if remote_summaries.exists():
        GEMINI_ANTIGRAVITY.mkdir(parents=True, exist_ok=True)
        merge_summaries_db(remote_summaries, GEMINI_ANTIGRAVITY / "conversation_summaries.db")
        heal_workspace_uris(GEMINI_ANTIGRAVITY / "conversation_summaries.db")
        print("[Antigravity Sync] Сводки и история диалогов (summaries) успешно объединены.")

    remote_proto = target_dir / "data" / "agyhub_summaries_proto.pb"
    if remote_proto.exists():
        local_proto = GEMINI_ANTIGRAVITY / "agyhub_summaries_proto.pb"
        if not local_proto.exists() or remote_proto.stat().st_mtime > local_proto.stat().st_mtime:
            shutil.copy2(remote_proto, local_proto)

    # 4. Annotations
    remote_ann = target_dir / "data" / "annotations"
    if remote_ann.exists():
        GEMINI_ANNOTATIONS.mkdir(parents=True, exist_ok=True)
        for ann in remote_ann.glob("*.pbtxt"):
            shutil.copy2(ann, GEMINI_ANNOTATIONS / ann.name)

    # 5. Brain Artifacts & Transcripts
    src_brain = target_dir / "data" / "brain"
    if src_brain.exists():
        GEMINI_BRAIN.mkdir(parents=True, exist_ok=True)
        sync_tree(src_brain, GEMINI_BRAIN, BRAIN_EXCLUDES, delete=False)
        print("[Antigravity Sync] Артефакты, степы и контекст brain успешно восстановлены.")

    # 6. Projects Registry & Cross-Platform Path Mapping
    registry_file = target_dir / "projects_registry.json"
    if registry_file.exists():
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                remote_registry = json.load(f)
            local_registry = load_projects()
            known_names = {p["name"]: p for p in local_registry.get("projects", [])}

            for prj in remote_registry.get("projects", []):
                p_name = prj["name"]
                remote_path_str = prj.get("path", "")
                remote_targets = prj.get("target_paths", {})
                custom_path = prj.get("custom_path")

                dest_path = None

                # 1. Has user locally configured this project?
                if p_name in known_names:
                    existing_path = Path(known_names[p_name]["path"])
                    dest_path = existing_path

                # 2. Check explicit target path for current OS
                if not dest_path and SYSTEM_OS in remote_targets:
                    candidate = Path(os.path.expanduser(remote_targets[SYSTEM_OS]))
                    is_safe, _ = is_safe_project_path(candidate, target_os=SYSTEM_OS)
                    if is_safe:
                        dest_path = candidate

                # 3. Check 'default' target path
                if not dest_path and "default" in remote_targets:
                    candidate = Path(os.path.expanduser(remote_targets["default"]))
                    is_safe, _ = is_safe_project_path(candidate, target_os=SYSTEM_OS)
                    if is_safe:
                        dest_path = candidate

                # 4. Check custom_path
                if not dest_path and custom_path:
                    candidate = Path(os.path.expanduser(custom_path))
                    is_safe, _ = is_safe_project_path(candidate, target_os=SYSTEM_OS)
                    is_win_str = bool(re.match(r"^[a-zA-Z]:[\\/]", custom_path))
                    if is_safe and ((SYSTEM_OS == "Windows" and is_win_str) or (SYSTEM_OS != "Windows" and not is_win_str)):
                        dest_path = candidate

                # 5. Check remote_path
                if not dest_path and remote_path_str:
                    is_win_remote = bool(re.match(r"^[a-zA-Z]:[\\/]", remote_path_str))
                    if (SYSTEM_OS == "Windows" and is_win_remote) or (SYSTEM_OS != "Windows" and not is_win_remote):
                        candidate = Path(remote_path_str)
                        is_safe, _ = is_safe_project_path(candidate, target_os=SYSTEM_OS)
                        if is_safe:
                            dest_path = candidate

                # 6. Fallback to default projects directory
                if not dest_path:
                    dest_path = get_default_projects_dir() / p_name
                    print(f"[Antigravity Sync] Выбрана папка для проекта '{p_name}': {dest_path}")

                dest_path = dest_path.resolve() if not (SYSTEM_OS == "Windows" and ":" in str(dest_path) and "\\" not in str(dest_path)) else dest_path

                # Merge target paths
                merged_targets = dict(remote_targets)
                merged_targets[SYSTEM_OS] = str(dest_path)

                if p_name not in known_names:
                    local_registry.setdefault("projects", []).append({
                        "name": p_name,
                        "path": str(dest_path),
                        "target_paths": merged_targets,
                        "custom_path": str(dest_path),
                        "added_at": prj.get("added_at", datetime.now().isoformat())
                    })
                else:
                    known_names[p_name]["path"] = str(dest_path)
                    cur_targets = known_names[p_name].setdefault("target_paths", {})
                    for k, v in merged_targets.items():
                        if k not in cur_targets:
                            cur_targets[k] = v
                    cur_targets[SYSTEM_OS] = str(dest_path)

            save_projects(local_registry)
        except Exception as e:
            print(f"[Warn] Ошибка объединения реестра проектов: {e}")

    # 7. Projects Content
    projects_src = target_dir / "projects"
    if projects_src.exists():
        local_registry = load_projects()
        for prj in local_registry.get("projects", []):
            prj_target_dir = projects_src / prj["name"]
            if prj_target_dir.exists():
                local_path = Path(prj["path"])
                local_path.mkdir(parents=True, exist_ok=True)
                ok, cnt, err = sync_tree(prj_target_dir, local_path, PROJECT_EXCLUDES, delete=False)
                if ok:
                    print(f"[Antigravity Sync] Проект '{prj['name']}' восстановлен в {local_path}")
                else:
                    print(f"[Error] Ошибка при восстановлении проекта {prj['name']}: {err}")


# ----------------------------------------------------
# Project Management Commands (Custom per-project directories)
# ----------------------------------------------------
def project_add(path_str: str, name: str = None, target_path_str: str = None):
    p = Path(os.path.expanduser(path_str))

    is_safe, reason = is_safe_project_path(p, target_os=SYSTEM_OS)
    if not is_safe:
        print(f"[Error] Отклонено из соображений безопасности: {reason}")
        sys.exit(1)

    p = p.resolve()
    if not p.exists():
        print(f"[Error] Каталог не найден: {p}")
        sys.exit(1)
    if not p.is_dir():
        print(f"[Error] Указанный путь не является директорией: {p}")
        sys.exit(1)

    project_name = name or p.name
    project_name = re.sub(r"[^\w\-\.]", "_", project_name, flags=re.UNICODE)

    data = load_projects()
    existing_prj = None
    for prj in data.get("projects", []):
        if prj["name"] == project_name or prj["path"] == str(p):
            existing_prj = prj
            break

    if existing_prj:
        existing_prj["path"] = str(p)
        existing_prj.setdefault("target_paths", {})[SYSTEM_OS] = str(p)
        if target_path_str:
            existing_prj["target_paths"]["default"] = target_path_str
            existing_prj["custom_path"] = target_path_str
        existing_prj["updated_at"] = datetime.now().isoformat()
        save_projects(data)
        print(f"[Antigravity Sync] Проект '{project_name}' обновлен в синхронизации: {p}")
        if target_path_str:
            print(f"  Целевая папка для восстановления: {target_path_str}")
        return

    prj_entry = {
        "name": project_name,
        "path": str(p),
        "target_paths": {
            SYSTEM_OS: str(p)
        },
        "added_at": datetime.now().isoformat()
    }
    if target_path_str:
        prj_entry["target_paths"]["default"] = target_path_str
        prj_entry["custom_path"] = target_path_str

    data.setdefault("projects", []).append(prj_entry)
    save_projects(data)
    print(f"[Antigravity Sync] Проект '{project_name}' успешно добавлен в синхронизацию: {p}")
    if target_path_str:
        print(f"  Целевая папка для восстановления: {target_path_str}")


def project_set_path(identifier: str, new_path_str: str):
    data = load_projects()
    norm_id = identifier.lower().strip()

    target_prj = None
    for prj in data.get("projects", []):
        if prj["name"].lower() == norm_id or prj["path"].lower() == norm_id:
            target_prj = prj
            break

    if not target_prj:
        print(f"[Error] Проект '{identifier}' не найден в списке отслеживаемых.")
        print("Используйте 'sync.sh project list', чтобы увидеть список проектов.")
        sys.exit(1)

    new_p = Path(os.path.expanduser(new_path_str)).resolve()
    is_safe, reason = is_safe_project_path(new_p, target_os=SYSTEM_OS)
    if not is_safe:
        print(f"[Error] Недопустимый путь для проекта: {reason}")
        sys.exit(1)

    old_p = Path(target_prj["path"])
    print(f"[Antigravity Sync] Изменение папки для проекта '{target_prj['name']}':")
    print(f"  Текущий путь: {old_p}")
    print(f"  Новый путь:   {new_p}")

    # Transfer files if old path exists and new path is empty
    if old_p.exists() and old_p != new_p:
        new_p.mkdir(parents=True, exist_ok=True)
        if not any(new_p.iterdir()):
            print(f"[Antigravity Sync] Перенос файлов проекта в новую папку...")
            sync_tree(old_p, new_p, PROJECT_EXCLUDES, delete=False)
            print(f"[Antigravity Sync] Файлы проекта успешно скопированы в {new_p}")

    new_p.mkdir(parents=True, exist_ok=True)
    target_prj["path"] = str(new_p)
    target_prj.setdefault("target_paths", {})[SYSTEM_OS] = str(new_p)
    target_prj["custom_path"] = str(new_p)
    target_prj["updated_at"] = datetime.now().isoformat()

    save_projects(data)
    print(f"[Antigravity Sync] Проект '{target_prj['name']}' теперь привязан к: {new_p}")

    # Heal workspace URIs
    summary_db = GEMINI_ANTIGRAVITY / "conversation_summaries.db"
    if summary_db.exists():
        heal_workspace_uris(summary_db)
        print("[Antigravity Sync] Пути в истории диалогов обновлены для новой папки.")


def project_set_target(identifier: str, os_name: str, target_path_str: str):
    data = load_projects()
    norm_id = identifier.lower().strip()

    target_prj = None
    for prj in data.get("projects", []):
        if prj["name"].lower() == norm_id or prj["path"].lower() == norm_id:
            target_prj = prj
            break

    if not target_prj:
        print(f"[Error] Проект '{identifier}' не найден в списке отслеживаемых.")
        sys.exit(1)

    os_norm = os_name.lower().strip()
    if os_norm in ("win", "windows"):
        os_key = "Windows"
    elif os_norm in ("mac", "macos", "darwin", "osx"):
        os_key = "Darwin"
    elif os_norm in ("linux", "ubuntu", "debian"):
        os_key = "Linux"
    elif os_norm in ("all", "default"):
        os_key = "default"
    else:
        print(f"[Error] Неизвестная ОС '{os_name}'. Допустимо: windows, mac, linux, default")
        sys.exit(1)

    is_safe, reason = is_safe_project_path(Path(target_path_str), target_os=os_key)
    if not is_safe:
        print(f"[Error] Недопустимый путь: {reason}")
        sys.exit(1)

    target_prj.setdefault("target_paths", {})[os_key] = target_path_str
    target_prj["updated_at"] = datetime.now().isoformat()
    save_projects(data)
    print(f"[Antigravity Sync] Для проекта '{target_prj['name']}' установлен целевой путь на {os_key}: {target_path_str}")


def project_default_dir(new_dir: str = None):
    cfg = load_config()
    if not new_dir:
        current = cfg.get("default_projects_dir", str(HOME / "Developer"))
        print(f"[Antigravity Sync] Текущая папка для проектов по умолчанию: {current}")
        return

    p = Path(os.path.expanduser(new_dir)).resolve()
    is_safe, reason = is_safe_project_path(p, target_os=SYSTEM_OS)
    if not is_safe:
        print(f"[Error] Недопустимый каталог: {reason}")
        sys.exit(1)

    p.mkdir(parents=True, exist_ok=True)
    cfg["default_projects_dir"] = str(p)
    save_config(cfg)
    print(f"[Antigravity Sync] Папка для проектов по умолчанию установлена: {p}")


def project_remove(identifier: str):
    data = load_projects()
    initial_len = len(data.get("projects", []))
    norm_id = str(Path(os.path.expanduser(identifier)).resolve()) if os.path.exists(os.path.expanduser(identifier)) else identifier

    data["projects"] = [
        p for p in data.get("projects", [])
        if p["name"] != identifier and p["path"] != norm_id and p["path"] != identifier
    ]
    if len(data["projects"]) < initial_len:
        save_projects(data)
        print(f"[Antigravity Sync] Проект '{identifier}' удален из синхронизации.")
    else:
        print(f"[Antigravity Sync] Проект '{identifier}' не найден в списке отслеживаемых.")


def project_list():
    data = load_projects()
    projects = data.get("projects", [])
    if not projects:
        print("[Antigravity Sync] Список проектов пуст. Добавьте проект: sync.sh project add <путь>")
        return

    cfg = load_config()
    default_dir = cfg.get("default_projects_dir", str(HOME / "Developer"))

    print(f"=== Отслеживаемые проекты (папка по умолчанию: {default_dir}) ===")
    for idx, p in enumerate(projects, 1):
        status = "Доступен локально" if os.path.exists(p["path"]) else "НЕ НАЙДЕН на этом компьютере"
        print(f"\n{idx}. [{p['name']}]")
        print(f"   Локальный путь: {p['path']} ({status})")
        targets = p.get("target_paths", {})
        if targets:
            target_strs = [f"{os_k}: {path_v}" for os_k, path_v in targets.items()]
            print(f"   Целевые папки: {', '.join(target_strs)}")
        if p.get("custom_path"):
            print(f"   Пользовательская папка: {p['custom_path']}")
    print("")


# ----------------------------------------------------
# Google Drive Operations (Cross-Platform)
# ----------------------------------------------------
def detect_gdrive_path() -> list:
    """Cross-platform detection for Google Drive on macOS, Windows, and Linux."""
    candidates = []

    if SYSTEM_OS == "Darwin":  # macOS
        cloud_storage = HOME / "Library" / "CloudStorage"
        if cloud_storage.exists():
            for item in cloud_storage.glob("GoogleDrive*"):
                if item.is_dir():
                    for sub in ["My Drive", "Мой диск", ""]:
                        p = item / sub if sub else item
                        if p.exists():
                            candidates.append(p / "AntigravitySync")
                            break

        for p in [HOME / "Google Drive" / "My Drive", HOME / "Google Drive", Path("/Volumes/GoogleDrive/My Drive")]:
            if p.exists():
                candidates.append(p / "AntigravitySync")

    elif SYSTEM_OS == "Windows":
        for letter in ["G", "H", "I", "D", "E"]:
            root = Path(f"{letter}:\\")
            if root.exists():
                for sub in ["My Drive", "Мой диск", ""]:
                    p = root / sub if sub else root
                    if p.exists():
                        candidates.append(p / "AntigravitySync")
                        break

        for p in [HOME / "Google Drive", HOME / "GoogleDrive"]:
            if p.exists():
                candidates.append(p / "AntigravitySync")

    else:  # Linux
        for p in [HOME / "Google Drive", HOME / "GoogleDrive", HOME / "google-drive"]:
            if p.exists():
                candidates.append(p / "AntigravitySync")

        uid = os.getuid() if hasattr(os, "getuid") else 1000
        gvfs = Path(f"/run/user/{uid}/gvfs")
        if gvfs.exists():
            for item in gvfs.glob("google-drive*"):
                candidates.append(item / "AntigravitySync")

    return [str(c) for c in candidates]


def get_gdrive_path() -> Path:
    cfg = load_config()
    configured = cfg.get("gdrive_path")
    if configured:
        return Path(configured)
    candidates = detect_gdrive_path()
    if candidates:
        cfg["gdrive_path"] = candidates[0]
        save_config(cfg)
        return Path(candidates[0])
    return None


def gdrive_set_path(path_str: str):
    p = Path(os.path.expanduser(path_str)).resolve()
    p.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["gdrive_path"] = str(p)
    save_config(cfg)
    print(f"[Antigravity Sync] Путь к Google Drive установлен: {p}")


def gdrive_status():
    gd_path = get_gdrive_path()
    if not gd_path:
        print("[Antigravity Sync] Google Drive не настроен и не найден автоматически.")
        print("Укажите путь вручную: sync.sh gdrive set-path <путь к Google Drive>")
        return

    print(f"=== Статус Google Drive ({gd_path}) ===")
    if not gd_path.exists():
        print(f"[Статус] Папка синхронизации еще не создана.")
        return

    subdirs = [p.name for p in gd_path.iterdir() if p.is_dir()]
    print(f"[Директории в Google Drive] {', '.join(subdirs) if subdirs else 'Папка пуста'}")

    conv_dir = gd_path / "data" / "conversations"
    if conv_dir.exists():
        convs = [p.stem for p in conv_dir.glob("*.db")]
        print(f"[Синхронизированные диалоги в GDrive] {len(convs)} диалогов")

    projects_dir = gd_path / "projects"
    if projects_dir.exists():
        synced_projects = [p.name for p in projects_dir.iterdir() if p.is_dir()]
        print(f"[Синхронизированные проекты в GDrive] {', '.join(synced_projects) if synced_projects else 'Нет'}")


def gdrive_push():
    gd_path = get_gdrive_path()
    if not gd_path:
        print("[Antigravity Sync] Google Drive не настроен. Укажите путь: sync.sh gdrive set-path <путь>")
        sys.exit(1)

    print(f"[Antigravity Sync] Отправка данных и диалогов в Google Drive ({gd_path})...")
    gd_path.mkdir(parents=True, exist_ok=True)
    copy_all_to_target(gd_path)
    atomic_write_json(gd_path / "last_sync.json", {"last_sync": datetime.now().isoformat(), "source": "push"})
    print(f"[Antigravity Sync] Синхронизация с Google Drive (включая историю диалогов) успешно завершена!")


def gdrive_pull():
    gd_path = get_gdrive_path()
    if not gd_path or not gd_path.exists():
        print(f"[Antigravity Sync] Папка Google Drive не найдена: {gd_path}")
        sys.exit(1)

    print(f"[Antigravity Sync] Загрузка данных и истории диалогов из Google Drive ({gd_path})...")
    restore_all_from_target(gd_path)
    print(f"[Antigravity Sync] Настройки и диалоги успешно восстановлены из Google Drive!")


# ----------------------------------------------------
# Git Operations (Cross-Platform via subprocess)
# ----------------------------------------------------
def run_git(args: list, cwd: Path = DEFAULT_GIT_SYNC_DIR) -> tuple:
    """Run git command safely without shell=True."""
    if not shutil.which("git"):
        return False, "Git не установлен в системе."
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False
        )
        return res.returncode == 0, res.stdout.strip() or res.stderr.strip()
    except Exception as e:
        return False, str(e)


def git_init(remote_url: str):
    if not is_valid_git_url(remote_url):
        print("[Error] Недопустимый или потенциально небезопасный URL репозитория.")
        print("Поддерживаются форматы: git@github.com:user/repo.git или https://github.com/user/repo.git")
        sys.exit(1)

    DEFAULT_GIT_SYNC_DIR.mkdir(parents=True, exist_ok=True)

    if not (DEFAULT_GIT_SYNC_DIR / ".git").exists():
        ok, out = run_git(["init", "-b", "main"], cwd=DEFAULT_GIT_SYNC_DIR)
        if not ok:
            run_git(["init"], cwd=DEFAULT_GIT_SYNC_DIR)
        print(f"[Antigravity Sync] Инициализирован локальный репозиторий в {DEFAULT_GIT_SYNC_DIR}")

    # Generate cross-platform .gitignore
    gitignore_path = DEFAULT_GIT_SYNC_DIR / ".gitignore"
    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write("# Security & Credentials\n")
        for item in SENSITIVE_EXCLUDES:
            f.write(f"{item}\n")
        f.write("\n# Build caches & temp files\n")
        for item in BUILD_CACHE_EXCLUDES:
            f.write(f"{item}\n")

    # Set or add remote
    ok, remotes = run_git(["remote"], cwd=DEFAULT_GIT_SYNC_DIR)
    if "origin" in remotes.split():
        run_git(["remote", "set-url", "origin", remote_url], cwd=DEFAULT_GIT_SYNC_DIR)
    else:
        run_git(["remote", "add", "origin", remote_url], cwd=DEFAULT_GIT_SYNC_DIR)

    print(f"[Antigravity Sync] Remote origin установлен: {remote_url}")

    copy_all_to_target(DEFAULT_GIT_SYNC_DIR)
    run_git(["add", "-A"], cwd=DEFAULT_GIT_SYNC_DIR)
    run_git(["commit", "-m", "Initial Antigravity sync setup with conversation history", "--"], cwd=DEFAULT_GIT_SYNC_DIR)
    print("[Antigravity Sync] Инициализация Git завершена. Выполните: sync.sh push")


def git_status():
    if not (DEFAULT_GIT_SYNC_DIR / ".git").exists():
        print("[Antigravity Sync] Git-репозиторий еще не настроен. Запустите: sync.sh init <remote-url>")
        return

    copy_all_to_target(DEFAULT_GIT_SYNC_DIR)
    print(f"=== Статус Git ({DEFAULT_GIT_SYNC_DIR}) ===")
    ok, st = run_git(["status", "-s"], cwd=DEFAULT_GIT_SYNC_DIR)
    print(st if st else "Рабочая директория чиста.")
    print("")
    ok, log = run_git(["log", "-1", "--oneline"], cwd=DEFAULT_GIT_SYNC_DIR)
    print(f"Последний коммит: {log if ok else 'Коммитов пока нет'}")
    ok, r_url = run_git(["remote", "get-url", "origin"], cwd=DEFAULT_GIT_SYNC_DIR)
    print(f"Remote: {r_url if ok else 'не настроен'}")


def git_push(msg: str = None):
    if not (DEFAULT_GIT_SYNC_DIR / ".git").exists():
        print("[Antigravity Sync] Git-репозиторий не найден. Запустите: sync.sh init <remote-url>")
        sys.exit(1)

    commit_msg = msg or f"Sync Antigravity configuration & conversation context {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    copy_all_to_target(DEFAULT_GIT_SYNC_DIR)

    run_git(["add", "-A"], cwd=DEFAULT_GIT_SYNC_DIR)
    ok_diff, _ = run_git(["diff-index", "--quiet", "HEAD", "--"], cwd=DEFAULT_GIT_SYNC_DIR)
    if ok_diff:
        print("[Antigravity Sync] Нет новых изменений для коммита.")
    else:
        ok_com, err_com = run_git(["commit", "-m", commit_msg, "--"], cwd=DEFAULT_GIT_SYNC_DIR)
        if ok_com:
            print(f"[Antigravity Sync] Создан коммит: {commit_msg}")
        else:
            print(f"[Warn] Ошибка коммита: {err_com}")

    ok, remotes = run_git(["remote"], cwd=DEFAULT_GIT_SYNC_DIR)
    if "origin" in remotes.split():
        print("[Antigravity Sync] Отправка изменений и контекста диалогов в remote origin...")
        ok_push, out_push = run_git(["push", "-u", "origin", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)
        if ok_push:
            print("[Antigravity Sync] Успешно отправлено в Git!")
        else:
            print(f"[Error] Ошибка при отправке в Git: {out_push}")
    else:
        print("[Antigravity Sync] Внимание: remote origin не настроен.")


def git_pull():
    if not (DEFAULT_GIT_SYNC_DIR / ".git").exists():
        print("[Antigravity Sync] Git-репозиторий не найден. Запустите: sync.sh init <remote-url>")
        sys.exit(1)

    ok, remotes = run_git(["remote"], cwd=DEFAULT_GIT_SYNC_DIR)
    if "origin" not in remotes.split():
        print("[Error] Remote origin не настроен.")
        sys.exit(1)

    print("[Antigravity Sync] Получение изменений и контекста диалогов из Git remote...")
    ok_pull, out_pull = run_git(["pull", "--rebase", "origin", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)
    if not ok_pull:
        ok_pull, out_pull = run_git(["pull", "origin", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)

    if ok_pull:
        restore_all_from_target(DEFAULT_GIT_SYNC_DIR)
        print("[Antigravity Sync] Конфигурация, диалоги и проекты успешно обновлены из Git!")
    else:
        print(f"[Error] Ошибка обновления из Git: {out_pull}")


# ----------------------------------------------------
# Main CLI Dispatcher
# ----------------------------------------------------
def print_help():
    print("================ Antigravity Cross-Platform Sync ================")
    print("Использование:")
    print("  1. Git (включая историю и контекст диалогов):")
    print("     init <repo-url>           - Инициализировать репозиторий")
    print("     push [сообщение]          - Отправить настройки, диалоги и проекты в Git")
    print("     pull                      - Подтянуть настройки, диалоги и проекты из Git")
    print("     status                    - Проверить статус Git")
    print("     sync [сообщение]          - Pull, затем Push в Git")
    print("")
    print("  2. Google Drive:")
    print("     gdrive detect             - Найти Google Drive на компьютере")
    print("     gdrive set-path <путь>    - Указать папку Google Drive вручную")
    print("     gdrive push               - Синхронизировать в Google Drive (с диалогами)")
    print("     gdrive pull               - Загрузить из Google Drive")
    print("     gdrive status             - Статус синхронизации Google Drive")
    print("")
    print("  3. Проекты (выбор индивидуальной папки для каждого проекта):")
    print("     project add <путь> [имя] [папка]     - Добавить проект (с возможностью указать целевую папку)")
    print("     project set-path <имя> <новый_путь>  - Задать/изменить локальную папку для проекта на этом ПК")
    print("     project set-target <имя> <os> <путь> - Задать целевую папку для ОС (windows/mac/linux/default)")
    print("     project default-dir [путь]           - Посмотреть или изменить общую папку для проектов")
    print("     project remove <имя>                 - Удалить проект из синхронизации")
    print("     project list                         - Список отслеживаемых проектов и их папок")
    print("")
    print("  4. Все источники сразу:")
    print("     all push | all pull | all status")
    print("==================================================================")


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "init":
        if len(sys.argv) < 3:
            print("Укажите URL репозитория: sync.sh init <url>")
            sys.exit(1)
        git_init(sys.argv[2])
    elif cmd in ("status", "st"):
        git_status()
    elif cmd in ("heal", "fix-paths"):
        heal_workspace_uris(GEMINI_ANTIGRAVITY / "conversation_summaries.db")
        print("[Antigravity Sync] Пути ко всем рабочим папкам проверены и исправлены.")
    elif cmd == "push":
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        git_push(msg)
    elif cmd == "pull":
        git_pull()
    elif cmd == "sync":
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        git_pull()
        git_push(msg)

    elif cmd == "git":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "init":
            if len(sys.argv) < 4:
                print("Укажите URL: sync.sh git init <url>")
                sys.exit(1)
            git_init(sys.argv[3])
        elif sub == "status":
            git_status()
        elif sub == "push":
            msg = sys.argv[3] if len(sys.argv) > 3 else None
            git_push(msg)
        elif sub == "pull":
            git_pull()
        elif sub == "sync":
            msg = sys.argv[3] if len(sys.argv) > 3 else None
            git_pull()
            git_push(msg)
        else:
            print("Команды git: init <url> | status | push [msg] | pull | sync")

    elif cmd == "gdrive":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if sub == "set-path":
            if len(sys.argv) < 4:
                print("Укажите путь: sync.sh gdrive set-path <путь>")
                sys.exit(1)
            gdrive_set_path(sys.argv[3])
        elif sub == "push":
            gdrive_push()
        elif sub == "pull":
            gdrive_pull()
        elif sub == "status":
            gdrive_status()
        elif sub == "detect":
            paths = detect_gdrive_path()
            if paths:
                print("Найдены варианты Google Drive:")
                for p in paths:
                    print(f" - {p}")
            else:
                print(f"Google Drive не обнаружен в стандартных директориях ({SYSTEM_OS}).")
        else:
            print("Команды gdrive: set-path <путь> | push | pull | status | detect")

    elif cmd == "project":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "list"
        if sub == "add":
            if len(sys.argv) < 4:
                print("Использование: sync.sh project add <путь_к_проекту> [имя] [целевая_папка]")
                sys.exit(1)
            src_path = sys.argv[3]
            name = sys.argv[4] if len(sys.argv) > 4 and not sys.argv[4].startswith("/") and not sys.argv[4].startswith("\\") and ":" not in sys.argv[4] else None
            target_path = None
            if len(sys.argv) > 5:
                target_path = sys.argv[5]
            elif len(sys.argv) == 5 and (sys.argv[4].startswith("/") or sys.argv[4].startswith("\\") or ":" in sys.argv[4] or sys.argv[4].startswith("~")):
                # User passed: project add <src> <target_path> without custom name
                name = None
                target_path = sys.argv[4]
            project_add(src_path, name, target_path)
        elif sub in ("set-path", "move", "path"):
            if len(sys.argv) < 5:
                print("Использование: sync.sh project set-path <имя_проекта> <новый_путь>")
                sys.exit(1)
            project_set_path(sys.argv[3], sys.argv[4])
        elif sub in ("set-target", "target"):
            if len(sys.argv) < 6:
                print("Использование: sync.sh project set-target <имя_проекта> <windows|mac|linux|default> <целевой_путь>")
                sys.exit(1)
            project_set_target(sys.argv[3], sys.argv[4], sys.argv[5])
        elif sub in ("default-dir", "default-path"):
            new_dir = sys.argv[3] if len(sys.argv) > 3 else None
            project_default_dir(new_dir)
        elif sub == "remove":
            if len(sys.argv) < 4:
                print("Использование: sync.sh project remove <имя_или_путь>")
                sys.exit(1)
            project_remove(sys.argv[3])
        elif sub == "list":
            project_list()
        else:
            print("Команды project: add | set-path | set-target | default-dir | remove | list")

    elif cmd == "all":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "push"
        if sub == "push":
            msg = sys.argv[3] if len(sys.argv) > 3 else None
            if (DEFAULT_GIT_SYNC_DIR / ".git").exists():
                git_push(msg)
            gd = get_gdrive_path()
            if gd:
                gdrive_push()
        elif sub == "pull":
            if (DEFAULT_GIT_SYNC_DIR / ".git").exists():
                git_pull()
            gd = get_gdrive_path()
            if gd and gd.exists():
                gdrive_pull()
        elif sub == "status":
            if (DEFAULT_GIT_SYNC_DIR / ".git").exists():
                git_status()
            gdrive_status()
            project_list()
        else:
            print("Команды all: push | pull | status")

    elif cmd in ("-h", "--help", "help"):
        print_help()
    else:
        print(f"Неизвестная команда: {cmd}")
        print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
