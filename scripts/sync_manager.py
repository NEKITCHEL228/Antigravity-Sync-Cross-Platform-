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
import time
from datetime import datetime
from pathlib import Path

# Base Paths
PLUGIN_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = PLUGIN_DIR / "config.json"
PROJECTS_FILE = PLUGIN_DIR / "projects.json"
CONFLICTS_FILE = PLUGIN_DIR / "pending_conflicts.json"

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

# Conflict Staging & Backup Dirs
CONFLICTS_STAGING_DIR = GEMINI_CONVERSATIONS / "pending_conflicts"
CONFLICTS_BRAIN_DIR = GEMINI_BRAIN / "pending_conflicts"
BACKUPS_DIR = GEMINI_CONVERSATIONS / "backups"

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
    "Thumbs.db",
    "plugins/antigravity-sync",
    "antigravity-sync"
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
                cfg = json.load(f)
                cfg.setdefault("git_sync_dir", str(DEFAULT_GIT_SYNC_DIR))
                cfg.setdefault("gdrive_path", "")
                cfg.setdefault("sync_conversations", True)
                cfg.setdefault("default_projects_dir", str(HOME / "Developer"))
                cfg.setdefault("os_default_projects_dirs", {
                    "Darwin": str(HOME / "Developer"),
                    "Windows": "C:\Developer",
                    "Linux": str(HOME / "Developer")
                })
                cfg.setdefault("conflict_strategy", "prompt")
                cfg.setdefault("auto_heal_ide_projects", True)
                return cfg
        except Exception:
            pass
    return {
        "git_sync_dir": str(DEFAULT_GIT_SYNC_DIR),
        "gdrive_path": "",
        "sync_conversations": True,
        "default_projects_dir": str(HOME / "Developer"),
        "os_default_projects_dirs": {
            "Darwin": str(HOME / "Developer"),
            "Windows": "C:\Developer",
            "Linux": str(HOME / "Developer")
        },
        "conflict_strategy": "prompt",
        "auto_heal_ide_projects": True
    }


def save_config(cfg: dict):
    atomic_write_json(CONFIG_FILE, cfg)


def get_default_projects_dir(target_os: str = None) -> Path:
    cfg = load_config()
    target_os = target_os or SYSTEM_OS
    os_dirs = cfg.get("os_default_projects_dirs", {})
    if target_os in os_dirs:
        return Path(os.path.expanduser(os_dirs[target_os]))
    custom_dir = cfg.get("default_projects_dir")
    if custom_dir:
        return Path(os.path.expanduser(custom_dir))
    return HOME / "Developer"


def set_default_projects_dir(new_dir: str, target_os: str = None):
    cfg = load_config()
    p_str = new_dir.strip()
    os_key = None
    if target_os:
        norm_os = target_os.lower().strip()
        if norm_os in ("win", "windows"):
            os_key = "Windows"
        elif norm_os in ("mac", "macos", "darwin", "osx"):
            os_key = "Darwin"
        elif norm_os in ("linux", "ubuntu", "debian"):
            os_key = "Linux"

    if os_key:
        cfg.setdefault("os_default_projects_dirs", {})[os_key] = p_str
        save_config(cfg)
        print(f"[Antigravity Sync] Папка для проектов на {os_key} установлена: {p_str}")
    else:
        cfg.setdefault("os_default_projects_dirs", {})[SYSTEM_OS] = p_str
        cfg["default_projects_dir"] = p_str
        save_config(cfg)
        print(f"[Antigravity Sync] Папка для проектов по умолчанию ({SYSTEM_OS}) установлена: {p_str}")


def config_show():
    cfg = load_config()
    print("================ Antigravity Sync Configuration ================")
    print(f"Файл конфигурации: {CONFIG_FILE}")
    print(f"Текущая ОС:        {SYSTEM_OS}")
    print("")
    print("1. Папки проектов по умолчанию:")
    print(f"   - Для текущей ОС ({SYSTEM_OS}): {get_default_projects_dir()}")
    os_dirs = cfg.get("os_default_projects_dirs", {})
    for os_k, p_val in os_dirs.items():
        print(f"   - {os_k}: {p_val}")
    print(f"   - Общий fallback: {cfg.get('default_projects_dir', str(HOME / 'Developer'))}")
    print("")
    print("2. Разрешение конфликтов диалогов:")
    print(f"   - Стратегия: {cfg.get('conflict_strategy', 'prompt')}")
    print("     (prompt = спрашивать | merge = автослияние | fork = авторазветвление | local | remote)")
    print("")
    print("3. Интеграция с Antigravity IDE:")
    print(f"   - Автоисправление проектов IDE: {'Включено' if cfg.get('auto_heal_ide_projects', True) else 'Выключено'}")
    print("")
    print("4. Провайдеры синхронизации:")
    print(f"   - Git репозиторий:  {cfg.get('git_sync_dir', str(DEFAULT_GIT_SYNC_DIR))}")
    print(f"   - Google Drive:     {cfg.get('gdrive_path') or 'Не настроен'}")
    print(f"   - Синхронизация чатов: {'Включена' if cfg.get('sync_conversations', True) else 'Выключена'}")
    print("================================================================")


def config_set(key: str, value: str):
    cfg = load_config()
    norm_key = key.lower().strip()
    if norm_key in ("strategy", "conflict_strategy", "conflict"):
        strat = value.lower().strip()
        if strat not in ("prompt", "merge", "fork", "local", "remote"):
            print("[Error] Допустимые стратегии конфликтов: prompt, merge, fork, local, remote")
            sys.exit(1)
        cfg["conflict_strategy"] = strat
        save_config(cfg)
        print(f"[Antigravity Sync] Стратегия разрешения конфликтов установлена: {strat}")
    elif norm_key in ("default_dir", "default-dir", "projects_dir"):
        set_default_projects_dir(value)
    elif norm_key in ("auto_heal_ide_projects", "heal_ide"):
        val_bool = value.lower() in ("true", "1", "yes", "да")
        cfg["auto_heal_ide_projects"] = val_bool
        save_config(cfg)
        print(f"[Antigravity Sync] Автоисправление проектов IDE: {val_bool}")
    else:
        cfg[key] = value
        save_config(cfg)
        print(f"[Antigravity Sync] Настройка '{key}' обновлена: {value}")


def load_pending_conflicts() -> dict:
    if CONFLICTS_FILE.exists():
        try:
            with open(CONFLICTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"conflicts": []}


def save_pending_conflicts(data: dict):
    atomic_write_json(CONFLICTS_FILE, data)


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

def heal_ide_projects():
    """
    Adapts and heals Antigravity IDE project configuration files (~/.gemini/config/projects/*.json).
    Ensures that folderUri in each project configuration points to the valid local directory on the current OS.
    """
    ide_projects_dir = GEMINI_CONFIG / "projects"
    if not ide_projects_dir.exists():
        return 0

    projects_data = load_projects()
    tracked_projects = {p["name"].lower(): Path(p["path"]) for p in projects_data.get("projects", [])}
    default_dir = get_default_projects_dir()

    healed_count = 0
    for proj_file in ide_projects_dir.glob("*.json"):
        if proj_file.name == "outside-of-project.json":
            continue
        try:
            with open(proj_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            p_name = data.get("name", "")
            modified = False

            def heal_uri_str(uri: str) -> str:
                nonlocal modified
                if not uri or not uri.startswith("file://"):
                    return uri

                unquoted = urllib.parse.unquote(uri[7:])
                is_win_format = (len(unquoted) >= 3 and unquoted[0] == "/" and unquoted[2] == ":") or (len(unquoted) >= 2 and unquoted[1] == ":") or (":\\" in unquoted)
                is_unix_format = unquoted.startswith("/") and not (len(unquoted) >= 3 and unquoted[2] == ":")
                is_foreign = (SYSTEM_OS != "Windows" and is_win_format) or (SYSTEM_OS == "Windows" and is_unix_format)

                local_path_str = unquoted[1:] if (is_win_format and unquoted.startswith("/")) else unquoted
                path_obj = Path(local_path_str)

                if not is_foreign and path_obj.exists():
                    return uri

                modified = True
                matched_target = None
                base_name = path_obj.name or p_name
                for t_name, t_path in tracked_projects.items():
                    if t_name == p_name.lower() or t_name in base_name.lower() or base_name.lower() in t_name or ("дизайн" in p_name.lower() and "design" in t_name):
                        matched_target = t_path
                        break

                if matched_target:
                    matched_target.mkdir(parents=True, exist_ok=True)
                    return matched_target.as_uri()
                else:
                    target_local = default_dir / base_name
                    target_local.mkdir(parents=True, exist_ok=True)
                    return target_local.as_uri()

            def traverse_and_heal(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "folderUri" and isinstance(v, str):
                            obj[k] = heal_uri_str(v)
                        else:
                            traverse_and_heal(v)
                elif isinstance(obj, list):
                    for item in obj:
                        traverse_and_heal(item)

            traverse_and_heal(data)

            if modified:
                atomic_write_json(proj_file, data)
                healed_count += 1
        except Exception:
            pass

    if healed_count > 0:
        print(f"[Antigravity Sync] Исправлены пути для {healed_count} проектов Antigravity IDE.")
    return healed_count


def get_conversation_title(conv_id: str) -> str:
    db = GEMINI_ANTIGRAVITY / "conversation_summaries.db"
    if not db.exists():
        return conv_id
    try:
        conn = sqlite3.connect(str(db))
        c = conn.cursor()
        c.execute("SELECT title FROM conversation_summaries WHERE conversation_id = ?;", (conv_id,))
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return conv_id


def stage_conflict(conv_id: str, remote_db: Path, remote_brain: Path, info: dict):
    CONFLICTS_STAGING_DIR.mkdir(parents=True, exist_ok=True)
    staged_db = CONFLICTS_STAGING_DIR / f"{conv_id}_remote.db"
    shutil.copy2(remote_db, staged_db)

    if remote_brain and remote_brain.exists():
        staged_brain = CONFLICTS_BRAIN_DIR / conv_id
        staged_brain.mkdir(parents=True, exist_ok=True)
        sync_tree(remote_brain, staged_brain, BRAIN_EXCLUDES, delete=False)

    conflicts = load_pending_conflicts()
    existing = [c for c in conflicts.get("conflicts", []) if c["conversation_id"] != conv_id]
    existing.append(info)
    conflicts["conflicts"] = existing
    save_pending_conflicts(conflicts)


def detect_conversation_conflict(local_db: Path, remote_db: Path) -> dict:
    """
    Detects if local and remote conversation databases have diverged.
    Returns details on common prefix, divergence step index, and conflict state.
    """
    local_db = Path(local_db)
    remote_db = Path(remote_db)

    if not local_db.exists() and not remote_db.exists():
        return {"has_conflict": False, "status": "empty"}
    if not local_db.exists():
        return {"has_conflict": False, "status": "remote_ahead", "local_count": 0, "remote_count": 0}
    if not remote_db.exists():
        return {"has_conflict": False, "status": "local_ahead", "local_count": 0, "remote_count": 0}

    try:
        conn_l = sqlite3.connect(str(local_db))
        conn_r = sqlite3.connect(str(remote_db))

        c_l = conn_l.cursor()
        c_r = conn_r.cursor()

        c_l.execute("SELECT idx, step_type, status, length(step_payload) FROM steps ORDER BY idx ASC;")
        loc_steps = c_l.fetchall()

        c_r.execute("SELECT idx, step_type, status, length(step_payload) FROM steps ORDER BY idx ASC;")
        rem_steps = c_r.fetchall()

        conn_l.close()
        conn_r.close()

        len_l = len(loc_steps)
        len_r = len(rem_steps)

        # 1. Exact match
        if loc_steps == rem_steps:
            return {
                "has_conflict": False,
                "status": "identical",
                "common_prefix": len_l,
                "local_count": len_l,
                "remote_count": len_r
            }

        # 2. Remote is clean fast-forward of local
        if len_r > len_l and rem_steps[:len_l] == loc_steps:
            return {
                "has_conflict": False,
                "status": "remote_ahead",
                "common_prefix": len_l,
                "local_count": len_l,
                "remote_count": len_r
            }

        # 3. Local is clean fast-forward of remote
        if len_l > len_r and loc_steps[:len_r] == rem_steps:
            return {
                "has_conflict": False,
                "status": "local_ahead",
                "common_prefix": len_r,
                "local_count": len_l,
                "remote_count": len_r
            }

        # 4. Divergence / True Conflict
        divergence_idx = 0
        for idx, (s1, s2) in enumerate(zip(loc_steps, rem_steps)):
            if s1 != s2:
                divergence_idx = idx
                break

        return {
            "has_conflict": True,
            "status": "diverged",
            "common_prefix": divergence_idx,
            "divergence_idx": divergence_idx,
            "local_count": len_l,
            "remote_count": len_r,
            "local_mtime": local_db.stat().st_mtime,
            "remote_mtime": remote_db.stat().st_mtime
        }
    except Exception as e:
        return {
            "has_conflict": True,
            "status": "diverged",
            "divergence_idx": 0,
            "local_count": 0,
            "remote_count": 0,
            "error": str(e)
        }


def resolve_conversation_conflict(
    conv_id: str,
    choice: str,
    local_db: Path,
    remote_db: Path,
    local_brain: Path = None,
    remote_brain: Path = None
) -> bool:
    choice = choice.lower().strip()
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    title = get_conversation_title(conv_id)

    # 1. LOCAL (Keep local, archive remote)
    if choice in ("local", "keep-local"):
        if remote_db and remote_db.exists():
            shutil.copy2(remote_db, BACKUPS_DIR / f"{conv_id}_remote_{ts}.db")
        print(f"[Antigravity Sync] Выбран локальный вариант диалога '{title}'. Удаленная копия заархивирована.")
        return True

    # 2. REMOTE (Accept remote, archive local)
    elif choice in ("remote", "keep-remote"):
        if local_db.exists():
            shutil.copy2(local_db, BACKUPS_DIR / f"{conv_id}_local_{ts}.db")
        if remote_db and remote_db.exists():
            shutil.copy2(remote_db, local_db)
        if remote_brain and remote_brain.exists() and local_brain:
            sync_tree(remote_brain, local_brain, BRAIN_EXCLUDES, delete=False)
        print(f"[Antigravity Sync] Принята версия с другого устройства для диалога '{title}'. Предыдущая локальная копия сохранена в backups/.")
        return True

    # 3. FORK (Branch remote into a new chat in sidebar)
    elif choice in ("fork", "branch", "both"):
        fork_id = f"{conv_id[:8]}_fork_{int(time.time())}"
        fork_db = GEMINI_CONVERSATIONS / f"{fork_id}.db"

        if remote_db and remote_db.exists():
            shutil.copy2(remote_db, fork_db)
            try:
                conn_f = sqlite3.connect(str(fork_db))
                conn_f.execute("UPDATE trajectory_meta SET trajectory_id = ?;", (fork_id,))
                conn_f.commit()
                conn_f.close()
            except Exception:
                pass

        if remote_brain and remote_brain.exists():
            sync_tree(remote_brain, GEMINI_BRAIN / fork_id, BRAIN_EXCLUDES, delete=False)

        # Register in conversation_summaries.db
        sum_db = GEMINI_ANTIGRAVITY / "conversation_summaries.db"
        if sum_db.exists():
            try:
                conn_s = sqlite3.connect(str(sum_db))
                c_s = conn_s.cursor()
                c_s.execute("SELECT * FROM conversation_summaries WHERE conversation_id = ?;", (conv_id,))
                row = c_s.fetchone()
                if row:
                    cols = [col[1] for col in c_s.execute("PRAGMA table_info(conversation_summaries)").fetchall()]
                    r_dict = dict(zip(cols, row))
                    r_dict["conversation_id"] = fork_id
                    r_dict["title"] = f"[Ветка с другого ПК] {title}"
                    r_dict["preview"] = f"[Ветка с другого ПК] {r_dict.get('preview', '')}"
                    r_dict["last_modified_time"] = datetime.now().isoformat()

                    col_str = ", ".join([f'"{c}"' for c in cols])
                    placeholders = ", ".join(["?"] * len(cols))
                    vals = [r_dict[c] for c in cols]
                    c_s.execute(f"INSERT OR REPLACE INTO conversation_summaries ({col_str}) VALUES ({placeholders});", vals)
                    conn_s.commit()
                conn_s.close()
            except Exception as e:
                print(f"[Warn] Ошибка регистрации разветвленного диалога в conversation_summaries: {e}")

        heal_workspace_uris(sum_db)
        print(f"[Antigravity Sync] Диалог разветвлен! Создана ветка '{fork_id}' ('[Ветка с другого ПК] {title}').")
        print("  Обе версии теперь доступны как отдельные диалоги в боковой панели Antigravity!")
        return True

    # 4. MERGE (Combine both divergent branches)
    elif choice in ("merge", "combine"):
        if not local_db.exists() or not remote_db or not remote_db.exists():
            print("[Error] Для объединения требуются обе базы диалога.")
            return False

        # Backup local before merging
        shutil.copy2(local_db, BACKUPS_DIR / f"{conv_id}_pre_merge_{ts}.db")

        try:
            conn_l = sqlite3.connect(str(local_db))
            conn_r = sqlite3.connect(str(remote_db))

            c_l = conn_l.cursor()
            c_r = conn_r.cursor()

            c_l.execute("SELECT idx, step_type, status, length(step_payload) FROM steps ORDER BY idx ASC;")
            s_l = c_l.fetchall()
            c_r.execute("SELECT idx, step_type, status, length(step_payload) FROM steps ORDER BY idx ASC;")
            s_r = c_r.fetchall()

            K = 0
            for i, (a, b) in enumerate(zip(s_l, s_r)):
                if a != b:
                    K = i
                    break
            else:
                K = min(len(s_l), len(s_r))

            max_l = max([s[0] for s in s_l]) if s_l else -1
            step_tables = ["steps", "gen_metadata", "executor_metadata", "parent_references", "battle_mode_infos"]

            for t in step_tables:
                table_exists = c_r.execute(f"SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{t}'").fetchone()[0]
                if not table_exists:
                    continue
                cols = [col[1] for col in c_r.execute(f"PRAGMA table_info({t})").fetchall()]
                if "idx" not in cols:
                    continue

                col_str = ", ".join([f'"{c}"' for c in cols])
                placeholders = ", ".join(["?"] * len(cols))
                idx_pos = cols.index("idx")

                rows = c_r.execute(f"SELECT {col_str} FROM {t} WHERE idx >= ? ORDER BY idx ASC", (K,)).fetchall()
                for row in rows:
                    row_list = list(row)
                    old_idx = row_list[idx_pos]
                    new_idx = max_l + 1 + (old_idx - K)
                    row_list[idx_pos] = new_idx
                    c_l.execute(f"INSERT OR REPLACE INTO {t} ({col_str}) VALUES ({placeholders})", row_list)

            conn_l.commit()
            total_steps = c_l.execute("SELECT count(*) FROM steps").fetchone()[0]
            conn_l.close()
            conn_r.close()

            # Merge transcripts
            if local_brain and remote_brain:
                loc_t_file = local_brain / ".system_generated" / "logs" / "transcript.jsonl"
                rem_t_file = remote_brain / ".system_generated" / "logs" / "transcript.jsonl"
                if loc_t_file.exists() and rem_t_file.exists():
                    try:
                        with open(loc_t_file, "r", encoding="utf-8") as f:
                            loc_lines = [json.loads(line) for line in f if line.strip()]
                        with open(rem_t_file, "r", encoding="utf-8") as f:
                            rem_lines = [json.loads(line) for line in f if line.strip()]

                        max_s_idx = max([d.get("step_index", 0) for d in loc_lines]) if loc_lines else max_l

                        separator = {
                            "step_index": max_s_idx + 1,
                            "type": "EPHEMERAL_MESSAGE",
                            "source": "SYSTEM_SDK",
                            "status": "DONE",
                            "created_at": datetime.now().isoformat() + "Z",
                            "content": "🔀 [Antigravity Sync] Сообщения ниже объединены из параллельной ветки диалога с другого устройства"
                        }
                        loc_lines.append(separator)

                        for rem_item in rem_lines:
                            old_si = rem_item.get("step_index", 0)
                            if old_si >= K:
                                rem_item["step_index"] = max_s_idx + 2 + (old_si - K)
                                loc_lines.append(rem_item)

                        with open(loc_t_file, "w", encoding="utf-8") as f:
                            for item in loc_lines:
                                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    except Exception as e:
                        print(f"[Warn] Ошибка объединения transcript.jsonl: {e}")

                # Copy step logs and artifacts
                rem_steps_dir = remote_brain / ".system_generated" / "steps"
                loc_steps_dir = local_brain / ".system_generated" / "steps"
                if rem_steps_dir.exists():
                    loc_steps_dir.mkdir(parents=True, exist_ok=True)
                    sync_tree(rem_steps_dir, loc_steps_dir, BRAIN_EXCLUDES, delete=False)

            # Update conversation summaries
            sum_db = GEMINI_ANTIGRAVITY / "conversation_summaries.db"
            if sum_db.exists():
                try:
                    conn_s = sqlite3.connect(str(sum_db))
                    conn_s.execute(
                        "UPDATE conversation_summaries SET step_count = ?, last_modified_time = ? WHERE conversation_id = ?;",
                        (total_steps, datetime.now().isoformat(), conv_id)
                    )
                    conn_s.commit()
                    conn_s.close()
                except Exception:
                    pass

            print(f"[Antigravity Sync] Диалог '{title}' успешно объединен! Итоговое количество шагов: {total_steps}.")
            return True
        except Exception as e:
            print(f"[Error] Сбой объединения диалога '{conv_id}': {e}")
            return False

    return False


def conflict_list():
    conflicts = load_pending_conflicts()
    items = conflicts.get("conflicts", [])
    if not items:
        print("[Antigravity Sync] Нет нерешенных конфликтов диалогов. Все диалоги синхронизированы!")
        return

    print("=== Обнаруженные конфликты диалогов ===")
    for idx, c in enumerate(items, 1):
        cid = c["conversation_id"]
        title = c.get("title", cid)
        div = c.get("divergence_idx", "?")
        l_steps = c.get("local_steps", "?")
        r_steps = c.get("remote_steps", "?")
        print(f"\n{idx}. [{title}] (ID: {cid})")
        print(f"   Шагов локально: {l_steps} | Шагов на другом ПК: {r_steps}")
        print(f"   Точка расхождения: шаг {div}")
        print(f"   Команды для решения:")
        print(f"     sync.sh conflict resolve {cid} merge   - Объединить обе истории (Merge)")
        print(f"     sync.sh conflict resolve {cid} fork    - Сохранить как два разных чата (Fork)")
        print(f"     sync.sh conflict resolve {cid} local   - Оставить только локальную версию")
        print(f"     sync.sh conflict resolve {cid} remote  - Принять версию с другого ПК")
    print("")


def conflict_resolve(identifier: str, strategy: str):
    conflicts = load_pending_conflicts()
    items = conflicts.get("conflicts", [])
    if not items:
        print("[Antigravity Sync] Нет активных конфликтов для разрешения.")
        return

    strategy = strategy.lower().strip()
    if strategy not in ("local", "remote", "merge", "fork", "combine", "both"):
        print(f"[Error] Неизвестная стратегия: {strategy}. Допустимо: merge, fork, local, remote")
        sys.exit(1)

    if strategy == "combine":
        strategy = "merge"
    elif strategy == "both":
        strategy = "fork"

    target_items = []
    if identifier.lower() == "all":
        target_items = list(items)
    else:
        for c in items:
            if c["conversation_id"] == identifier or identifier in c["conversation_id"] or identifier.lower() in c.get("title", "").lower():
                target_items.append(c)

    if not target_items:
        print(f"[Error] Конфликт для '{identifier}' не найден.")
        print("Используйте 'sync.sh conflict list', чтобы просмотреть конфликты.")
        sys.exit(1)

    resolved_ids = set()
    for item in target_items:
        cid = item["conversation_id"]
        local_db = GEMINI_CONVERSATIONS / f"{cid}.db"
        staged_remote_db = CONFLICTS_STAGING_DIR / f"{cid}_remote.db"
        local_brain = GEMINI_BRAIN / cid
        staged_remote_brain = CONFLICTS_BRAIN_DIR / cid

        if not staged_remote_db.exists():
            target_repo_db = DEFAULT_GIT_SYNC_DIR / "data" / "conversations" / f"{cid}.db"
            if target_repo_db.exists():
                staged_remote_db = target_repo_db
            target_repo_brain = DEFAULT_GIT_SYNC_DIR / "data" / "brain" / cid
            if target_repo_brain.exists():
                staged_remote_brain = target_repo_brain

        ok = resolve_conversation_conflict(
            cid, strategy, local_db, staged_remote_db, local_brain, staged_remote_brain
        )

        if ok:
            resolved_ids.add(cid)
            if (CONFLICTS_STAGING_DIR / f"{cid}_remote.db").exists():
                try:
                    (CONFLICTS_STAGING_DIR / f"{cid}_remote.db").unlink()
                except OSError:
                    pass
            if (CONFLICTS_BRAIN_DIR / cid).exists():
                try:
                    shutil.rmtree(CONFLICTS_BRAIN_DIR / cid, ignore_errors=True)
                except OSError:
                    pass

    conflicts["conflicts"] = [c for c in conflicts["conflicts"] if c["conversation_id"] not in resolved_ids]
    save_pending_conflicts(conflicts)
    print(f"[Antigravity Sync] Успешно разрешено конфликтов: {len(resolved_ids)} из {len(target_items)}.")



def get_os_key() -> str:
    """Returns normalized OS key: 'windows', 'mac', or 'linux'."""
    if SYSTEM_OS == "Windows":
        return "windows"
    elif SYSTEM_OS == "Darwin":
        return "mac"
    return "linux"


def heal_mcp_config(mcp_config_path: Path = None):
    """
    Ensures mcp_config.json only registers MCP servers compatible with the current OS.
    Incompatible servers (e.g. Windows exe paths on macOS, or uninstalled local HTTP services)
    are safely moved to '_disabled_mcpServers' so Antigravity starts cleanly without error popups,
    while preserving their configurations for synchronization back to compatible devices.
    """
    if mcp_config_path is None:
        mcp_config_path = GEMINI_CONFIG / "mcp_config.json"
    mcp_config_path = Path(mcp_config_path)
    if not mcp_config_path.exists():
        return

    try:
        with open(mcp_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[Warn] Ошибка чтения mcp_config.json: {e}")
        return

    servers = data.setdefault("mcpServers", {})
    disabled = data.setdefault("_disabled_mcpServers", {})

    modified = False

    # 1. Inspect active servers
    to_disable = {}
    for name, srv in list(servers.items()):
        cmd = srv.get("command")
        if cmd:
            is_win_path = (len(cmd) >= 2 and cmd[1] == ":") or ("\\" in cmd) or cmd.lower().endswith(".exe")
            is_unix_path = cmd.startswith("/") and not (len(cmd) >= 3 and cmd[2] == ":")

            if SYSTEM_OS != "Windows" and is_win_path:
                if not Path(cmd).exists():
                    to_disable[name] = (srv, "Путь к исполняемому файлу Windows не найден в macOS/Linux")
            elif SYSTEM_OS == "Windows" and is_unix_path:
                if not Path(cmd).exists():
                    to_disable[name] = (srv, "Unix-путь не поддерживается в Windows")

        url = srv.get("url") or srv.get("serverUrl")
        if url:
            if "127.0.0.1:3845" in url or "localhost:3845" in url:
                if SYSTEM_OS == "Darwin":
                    figma_exists = Path("/Applications/Figma.app").exists() or (HOME / "Applications/Figma.app").exists()
                    if not figma_exists:
                        to_disable[name] = (srv, "Приложение Figma Desktop не установлено на данном Mac")
                elif SYSTEM_OS == "Linux":
                    to_disable[name] = (srv, "Figma Desktop недоступна на Linux")

    for name, (srv, reason) in to_disable.items():
        srv_copy = dict(srv)
        srv_copy["_disabled_reason"] = reason
        disabled[name] = srv_copy
        del servers[name]
        modified = True
        print(f"[Antigravity Sync] MCP сервер '{name}' временно отключен на {SYSTEM_OS} ({reason}).")

    # 2. Check if any disabled servers can be re-enabled on this OS
    to_enable = {}
    for name, srv in list(disabled.items()):
        srv_clean = {k: v for k, v in srv.items() if not k.startswith("_disabled")}
        cmd = srv_clean.get("command")
        if cmd:
            is_win_path = (len(cmd) >= 2 and cmd[1] == ":") or ("\\" in cmd) or cmd.lower().endswith(".exe")
            if SYSTEM_OS == "Windows" and is_win_path and Path(cmd).exists():
                to_enable[name] = srv_clean
            elif SYSTEM_OS != "Windows" and not is_win_path:
                if Path(cmd).exists() or shutil.which(cmd):
                    to_enable[name] = srv_clean

        url = srv_clean.get("url") or srv_clean.get("serverUrl")
        if url and ("127.0.0.1:3845" in url or "localhost:3845" in url):
            if SYSTEM_OS == "Windows":
                figma_win = HOME / "AppData" / "Local" / "Figma"
                if figma_win.exists():
                    to_enable[name] = srv_clean
            elif SYSTEM_OS == "Darwin":
                if Path("/Applications/Figma.app").exists():
                    to_enable[name] = srv_clean

    for name, srv in to_enable.items():
        servers[name] = srv
        del disabled[name]
        modified = True
        print(f"[Antigravity Sync] MCP сервер '{name}' активирован для {SYSTEM_OS}.")

    if modified:
        atomic_write_json(mcp_config_path, data)


def handle_mcp_config_push(local_config_dir: Path, target_config_dir: Path):
    """
    Saves OS-specific MCP configuration snapshot and preserves all servers in the target repository.
    """
    local_mcp = local_config_dir / "mcp_config.json"
    if not local_mcp.exists():
        return

    os_key = get_os_key()
    target_config_dir.mkdir(parents=True, exist_ok=True)
    target_os_mcp = target_config_dir / f"mcp_config.{os_key}.json"
    shutil.copy2(local_mcp, target_os_mcp)

    target_mcp = target_config_dir / "mcp_config.json"
    if target_mcp.exists():
        try:
            with open(target_mcp, "r", encoding="utf-8") as f:
                target_data = json.load(f)
            with open(local_mcp, "r", encoding="utf-8") as f:
                local_data = json.load(f)

            t_servers = target_data.setdefault("mcpServers", {})
            t_disabled = target_data.setdefault("_disabled_mcpServers", {})
            l_servers = local_data.get("mcpServers", {})
            l_disabled = local_data.get("_disabled_mcpServers", {})

            for k, v in l_servers.items():
                t_servers[k] = v
                if k in t_disabled:
                    del t_disabled[k]

            for k, v in l_disabled.items():
                if k not in t_servers:
                    t_disabled[k] = v

            atomic_write_json(target_mcp, target_data)
        except Exception as e:
            print(f"[Warn] Ошибка объединения target mcp_config.json: {e}")


def handle_mcp_config_pull(target_config_dir: Path, local_config_dir: Path):
    """
    Restores MCP configuration tailored for the current OS.
    """
    os_key = get_os_key()
    target_os_mcp = target_config_dir / f"mcp_config.{os_key}.json"
    local_mcp = local_config_dir / "mcp_config.json"

    if target_os_mcp.exists():
        shutil.copy2(target_os_mcp, local_mcp)
    elif (target_config_dir / "mcp_config.json").exists():
        shutil.copy2(target_config_dir / "mcp_config.json", local_mcp)

    heal_mcp_config(local_mcp)


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
        handle_mcp_config_push(GEMINI_CONFIG, dst)

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


def restore_all_from_target(target_dir: Path, conflict_strategy: str = None):
    """
    Restores configurations, conversation histories (with context and steps),
    brain artifacts, and registered projects from target directory.
    Supports intelligent conflict detection and resolution.
    """
    target_dir = Path(target_dir)
    cfg = load_config()
    strat = conflict_strategy or cfg.get("conflict_strategy", "prompt")

    # 1. Configuration
    src = target_dir / "config"
    if src.exists():
        GEMINI_CONFIG.mkdir(parents=True, exist_ok=True)
        ok, cnt, err = sync_tree(src, GEMINI_CONFIG, CONFIG_EXCLUDES, delete=False)
        handle_mcp_config_pull(src, GEMINI_CONFIG)
        if ok:
            print("[Antigravity Sync] Конфигурация успешно восстановлена.")
        else:
            print(f"[Error] Сбой восстановления конфигурации: {err}")

    # 2. Conversation Trajectories & Context (*.db) with Conflict Handling
    remote_conv = target_dir / "data" / "conversations"
    remote_brain_dir = target_dir / "data" / "brain"
    detected_conflicts = []

    if remote_conv.exists():
        GEMINI_CONVERSATIONS.mkdir(parents=True, exist_ok=True)
        restored_count = 0

        for remote_db in remote_conv.glob("*.db"):
            local_db = GEMINI_CONVERSATIONS / remote_db.name
            conv_id = remote_db.stem
            is_active = (GEMINI_PRESENCE / f"{conv_id}.lock").exists() if GEMINI_PRESENCE.exists() else False

            if not local_db.exists():
                shutil.copy2(remote_db, local_db)
                restored_count += 1
                continue

            c_info = detect_conversation_conflict(local_db, remote_db)

            if not c_info.get("has_conflict"):
                if c_info.get("status") == "remote_ahead":
                    shutil.copy2(remote_db, local_db)
                    restored_count += 1
                # If identical or local_ahead: local stays intact
            else:
                title = get_conversation_title(conv_id)
                conflict_entry = {
                    "conversation_id": conv_id,
                    "title": title,
                    "divergence_idx": c_info.get("divergence_idx", 0),
                    "local_steps": c_info.get("local_count", 0),
                    "remote_steps": c_info.get("remote_count", 0),
                    "is_active": is_active,
                    "detected_at": datetime.now().isoformat()
                }

                if strat != "prompt":
                    print(f"[Antigravity Sync] Разрешение конфликта для '{title}' (стратегия: {strat})...")
                    resolve_conversation_conflict(
                        conv_id,
                        strat,
                        local_db,
                        remote_db,
                        local_brain=GEMINI_BRAIN / conv_id,
                        remote_brain=remote_brain_dir / conv_id if remote_brain_dir.exists() else None
                    )
                    restored_count += 1
                else:
                    stage_conflict(
                        conv_id,
                        remote_db,
                        remote_brain_dir / conv_id if remote_brain_dir.exists() else None,
                        conflict_entry
                    )
                    detected_conflicts.append(conflict_entry)

        if restored_count > 0:
            print(f"[Antigravity Sync] Диалоги и контекст моделей восстановлены/обновлены ({restored_count} шт).")

        if detected_conflicts:
            print("")
            print(f"⚠️ [Antigravity Sync] Обнаружено конфликтующих диалогов: {len(detected_conflicts)}!")
            for c in detected_conflicts:
                print(f"   - '{c['title']}' ({c['conversation_id'][:8]}...): расхождение на шаге {c['divergence_idx']} (локально: {c['local_steps']} шагов, на другом ПК: {c['remote_steps']} шагов)")
            print("   Для разрешения конфликтов используйте:")
            print("     sync.sh conflict list                         - Список всех конфликтов")
            print("     sync.sh conflict resolve <id> merge           - Объединить обе истории (Merge)")
            print("     sync.sh conflict resolve <id> fork            - Разветвить (сохранить обе версии как отдельные чаты)")
            print("     sync.sh conflict resolve <id> local           - Оставить версию с этого ПК")
            print("     sync.sh conflict resolve <id> remote          - Принять версию с другого ПК")
            print("")

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

    # 8. Heal Workspace Links, MCP config & Antigravity IDE Projects
    heal_workspace_uris(GEMINI_ANTIGRAVITY / "conversation_summaries.db")
    heal_mcp_config(GEMINI_CONFIG / "mcp_config.json")
    if cfg.get("auto_heal_ide_projects", True):
        heal_ide_projects()


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


def project_default_dir(new_dir: str = None, target_os: str = None):
    cfg = load_config()
    if not new_dir:
        print(f"[Antigravity Sync] Папка для проектов по умолчанию ({SYSTEM_OS}): {get_default_projects_dir()}")
        os_dirs = cfg.get("os_default_projects_dirs", {})
        for os_k, p_val in os_dirs.items():
            print(f"   - {os_k}: {p_val}")
        return

    set_default_projects_dir(new_dir, target_os)


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


def gdrive_pull(strategy: str = None):
    gd_path = get_gdrive_path()
    if not gd_path or not gd_path.exists():
        print(f"[Antigravity Sync] Папка Google Drive не найдена: {gd_path}")
        sys.exit(1)

    print(f"[Antigravity Sync] Загрузка данных и истории диалогов из Google Drive ({gd_path})...")
    restore_all_from_target(gd_path, conflict_strategy=strategy)
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


def git_pull(strategy: str = None):
    if not (DEFAULT_GIT_SYNC_DIR / ".git").exists():
        print("[Antigravity Sync] Git-репозиторий не найден. Запустите: sync.sh init <remote-url>")
        sys.exit(1)

    ok, remotes = run_git(["remote"], cwd=DEFAULT_GIT_SYNC_DIR)
    if "origin" not in remotes.split():
        print("[Error] Remote origin не настроен.")
        sys.exit(1)

    # Discard any uncommitted temporary sync cache copies before pulling remote
    run_git(["reset", "--hard", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)
    run_git(["clean", "-fd"], cwd=DEFAULT_GIT_SYNC_DIR)

    print("[Antigravity Sync] Получение изменений и контекста диалогов из Git remote...")
    ok_pull, out_pull = run_git(["pull", "--rebase", "origin", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)
    if not ok_pull:
        ok_pull, out_pull = run_git(["pull", "origin", "HEAD"], cwd=DEFAULT_GIT_SYNC_DIR)

    if ok_pull:
        restore_all_from_target(DEFAULT_GIT_SYNC_DIR, conflict_strategy=strategy)
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
    print("     init <repo-url>                      - Инициализировать репозиторий")
    print("     push [сообщение]                     - Отправить настройки, диалоги и проекты в Git")
    print("     pull [стратегия]                     - Подтянуть настройки, диалоги и проекты из Git")
    print("     status                               - Проверить статус Git")
    print("     sync [сообщение]                     - Pull, затем Push в Git")
    print("")
    print("  2. Разрешение конфликтов диалогов (если писали с разных ПК):")
    print("     conflict list                        - Показать список конфликтующих диалогов")
    print("     conflict resolve <id|all> <стратегия>- Разрешить конфликт диалога:")
    print("                                            • merge  - объединить обе ветки истории")
    print("                                            • fork   - сохранить обе как отдельные чаты")
    print("                                            • local  - оставить версию с этого ПК")
    print("                                            • remote - оставить версию с другого ПК")
    print("     conflict strategy [стратегия]        - Задать стандартную стратегию (prompt/merge/fork/local/remote)")
    print("")
    print("  3. Google Drive:")
    print("     gdrive detect                        - Найти Google Drive на компьютере")
    print("     gdrive set-path <путь>               - Указать папку Google Drive вручную")
    print("     gdrive push                          - Синхронизировать в Google Drive (с диалогами)")
    print("     gdrive pull [стратегия]              - Загрузить из Google Drive")
    print("     gdrive status                        - Статус синхронизации Google Drive")
    print("")
    print("  4. Проекты (выбор индивидуальной папки для каждого проекта):")
    print("     project add <путь> [имя] [папка]     - Добавить проект (с возможностью указать целевую папку)")
    print("     project set-path <имя> <новый_путь>  - Задать/изменить локальную папку для проекта на этом ПК")
    print("     project set-target <имя> <os> <путь> - Задать целевую папку для ОС (windows/mac/linux/default)")
    print("     project default-dir [путь] [os]      - Посмотреть или изменить общую папку для проектов")
    print("     project remove <имя>                 - Удалить проект из синхронизации")
    print("     project list                         - Список отслеживаемых проектов и их папок")
    print("")
    print("  5. Конфигурация и адаптация:")
    print("     config show                          - Показать текущую конфигурацию плагина")
    print("     config set <ключ> <значение>         - Изменить параметр конфигурации")
    print("     config default-dir <путь> [os]       - Задать стандартную папку для проектов на ОС")
    print("     config heal                          - Проверить и исправить пути проектов и MCP")
    print("     heal                                 - Восстановить целостность ссылок проектов и IDE")
    print("")
    print("  6. Все источники сразу:")
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
    elif cmd in ("heal", "fix-paths", "heal-ide"):
        heal_workspace_uris(GEMINI_ANTIGRAVITY / "conversation_summaries.db")
        heal_mcp_config(GEMINI_CONFIG / "mcp_config.json")
        heal_ide_projects()
        print("[Antigravity Sync] Пути ко всем проектам, диалогам и конфигурация MCP проверены и исправлены.")
    elif cmd in ("heal-mcp", "fix-mcp"):
        heal_mcp_config(GEMINI_CONFIG / "mcp_config.json")
        print("[Antigravity Sync] Конфигурация MCP проверена и адаптирована под текущую ОС.")
    elif cmd == "push":
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        git_push(msg)
    elif cmd == "pull":
        strat = sys.argv[2] if len(sys.argv) > 2 else None
        git_pull(strategy=strat)
    elif cmd == "sync":
        msg = sys.argv[2] if len(sys.argv) > 2 else None
        git_pull()
        git_push(msg)

    elif cmd == "conflict":
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "list"
        if sub in ("list", "ls", "status"):
            conflict_list()
        elif sub in ("resolve", "res", "solve"):
            if len(sys.argv) < 5:
                print("Использование: sync.sh conflict resolve <conversation_id|all> <merge|fork|local|remote>")
                sys.exit(1)
            conflict_resolve(sys.argv[3], sys.argv[4])
        elif sub in ("strategy", "strat"):
            if len(sys.argv) > 3:
                config_set("conflict_strategy", sys.argv[3])
            else:
                cfg = load_config()
                print(f"[Antigravity Sync] Текущая стратегия разрешения конфликтов: {cfg.get('conflict_strategy', 'prompt')}")
                print("Допустимо: prompt (спрашивать), merge (автослияние), fork (авторазветвление), local, remote")
        else:
            print("Команды conflict: list | resolve <id|all> <merge|fork|local|remote> | strategy [prompt|merge|fork|local|remote]")

    elif cmd in ("config", "settings"):
        sub = sys.argv[2].lower() if len(sys.argv) > 2 else "show"
        if sub in ("show", "list", "get"):
            config_show()
        elif sub == "set":
            if len(sys.argv) < 5:
                print("Использование: sync.sh config set <key> <value>")
                sys.exit(1)
            config_set(sys.argv[3], sys.argv[4])
        elif sub in ("default-dir", "default_dir", "dir"):
            if len(sys.argv) < 4:
                print("Использование: sync.sh config default-dir <путь> [windows|mac|linux]")
                sys.exit(1)
            target_os = sys.argv[4] if len(sys.argv) > 4 else None
            set_default_projects_dir(sys.argv[3], target_os)
        elif sub in ("heal", "fix"):
            heal_workspace_uris(GEMINI_ANTIGRAVITY / "conversation_summaries.db")
            heal_mcp_config(GEMINI_CONFIG / "mcp_config.json")
            heal_ide_projects()
            print("[Antigravity Sync] Конфигурация, пути и проекты Antigravity успешно проверены и исправлены.")
        else:
            print("Команды config: show | set <key> <val> | default-dir <path> [os] | heal")

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
            strat = sys.argv[3] if len(sys.argv) > 3 else None
            git_pull(strategy=strat)
        elif sub == "sync":
            msg = sys.argv[3] if len(sys.argv) > 3 else None
            git_pull()
            git_push(msg)
        else:
            print("Команды git: init <url> | status | push [msg] | pull [strat] | sync")

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
            strat = sys.argv[3] if len(sys.argv) > 3 else None
            gdrive_pull(strategy=strat)
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
            print("Команды gdrive: set-path <путь> | push | pull [strat] | status | detect")

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
            target_os = sys.argv[4] if len(sys.argv) > 4 else None
            project_default_dir(new_dir, target_os)
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
            strat = sys.argv[3] if len(sys.argv) > 3 else None
            if (DEFAULT_GIT_SYNC_DIR / ".git").exists():
                git_pull(strategy=strat)
            gd = get_gdrive_path()
            if gd and gd.exists():
                gdrive_pull(strategy=strat)
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
