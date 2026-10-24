# Antigravity Sync Rules & Agent Instructions

This document instructs the AI agent on handling all Antigravity synchronization requests, whether through Git, Google Drive, or managing project sync across macOS, Linux, and Windows.

## Main Sync Scripts
Operations are performed via the cross-platform plugin scripts:
- **macOS / Linux**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh`
- **Windows**: `%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd`
- **Direct Python (Universal)**: `python3 ~/.gemini/config/plugins/antigravity-sync/scripts/sync_manager.py`

---

## 1. Project Management via Chat

When the user asks to add, remove, or view projects in synchronization:

### Adding a Project:
- **Triggers**: "добавь проект X в синхронизацию", "добавь текущий проект", "sync project /path/to/project", "включи проект в бэкап"
- **Action**:
  1. If the user specifies a path (e.g. `/Users/name/projects/my-app`, `C:\dev\app` or `~/dev/app`), expand and validate it.
  2. If the user says "текущий проект" or doesn't specify a path, check the active workspace or ask the user for the directory path.
  3. Execute:
     ```bash
     ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add "<path>" "[optional_name]"
     ```
  4. Confirm to the user that the project has been added. Heavy dependencies (`node_modules`, `.venv`, `.git`, build directories) and sensitive files (`.env`, keys, secrets) are automatically excluded.

### Listing Projects:
- **Triggers**: "какие проекты синхронизируются?", "покажи список проектов", "list synced projects"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project list
  ```

### Removing a Project:
- **Triggers**: "удали проект X из синхронизации", "перестань синхронизировать проект Y"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project remove "<name_or_path>"
  ```

---

## 2. Google Drive Synchronization

### Setup & Detection:
- **Triggers**: "настрой синхронизацию с гугл диском", "подключи google drive"
- **Action**:
  1. Run `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive detect` (checks CloudStorage on macOS, drive letters on Windows, and standard paths on Linux).
  2. If detected, inform the user and automatically configure it.
  3. If not detected, ask the user where their Google Drive is mounted, then run:
     ```bash
     ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive set-path "<path>/AntigravitySync"
     ```

### Push to Google Drive:
- **Triggers**: "синхронизируй с гугл диском", "сохрани на google drive", "бэкап в google drive"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
  ```

### Pull from Google Drive:
- **Triggers**: "подтяни настройки с гугл диска", "восстанови из google drive"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull
  ```

### Google Drive Status:
- **Triggers**: "статус гугл диска", "проверь синхронизацию google drive"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive status
  ```

---

## 3. Git Synchronization

### Push to Git:
- **Triggers**: "синхронизируй с гит", "запушь настройки в репозиторий", "sync git"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "[optional commit message]"
  ```

### Pull from Git:
- **Triggers**: "подтяни изменения из гита", "pull git", "обнови настройки из репозитория"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull
  ```

### Git Status & Init:
- **Status**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh status`
- **Init**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh init "<remote_url>"`

---

## 4. Full / Universal Sync

When the user asks to "синхронизируй всё" or "полная синхронизация":
- Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
  ```

---

## 5. Security & Safety Principles
- **Credential Protection**: NEVER commit or upload sensitive files (`.env*`, private SSH/SSL keys `id_rsa*`, `*.pem`, `*.key`, OAuth tokens `jetski-standalone-oauth-token`, `*.token*`, SQLite lock/WAL files `*.db-wal`, `*.db-shm`).
- **Path Traversal Protection**: System roots (`/`, `/etc`, `C:\Windows`) and user home root cannot be added as projects.
- **Cross-Platform Compatibility**: When pulling a project from another operating system, if the path is incompatible with the host OS, it is safely mapped to `~/Developer/<project_name>`.
