# Antigravity Sync Rules & Agent Instructions

This document instructs the AI agent on handling all Antigravity synchronization requests, whether through Git, Google Drive, managing project sync, or syncing full conversation histories and model contexts across macOS, Linux, and Windows.

## Main Sync Scripts
Operations are performed via the cross-platform plugin scripts:
- **macOS / Linux**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh`
- **Windows**: `%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd`
- **Direct Python (Universal)**: `python3 ~/.gemini/config/plugins/antigravity-sync/scripts/sync_manager.py`

---

## 1. Conversation History & Context Continuation

The plugin automatically captures and synchronizes full conversation trajectories:
- Conversation SQLite databases (`conversations/*.db`) with active WAL pages safely merged.
- Conversation summaries database (`conversation_summaries.db`) and proto indexes (`agyhub_summaries_proto.pb`) for sidebar history.
- Conversation transcripts (`transcript.jsonl`, `transcript_full.jsonl`), step logs, and inter-agent messages.
- Conversation annotations (`annotations/*.pbtxt`).

### Triggers:
- "синхронизируй диалоги", "сохрани историю чатов", "синхронизируй контекст", "перенеси переписку на другой компьютер", "продолжи диалог на другом ноуте"
- Standard push/pull commands automatically include all conversation histories!

---

## 2. Project Management via Chat

Users can choose individual target directories for each project. When the user asks to add, relocate, or configure projects in synchronization:

### Adding a Project (with optional custom destination folder):
- **Triggers**: "добавь проект X в синхронизацию", "добавь текущий проект", "sync project /path/to/project", "включи проект в бэкап", "добавь проект X в папку Y"
- **Action**:
  1. If the user specifies a source path and optional custom target path, expand and validate them.
  2. If the user says "текущий проект" or doesn't specify a path, check the active workspace or ask the user for the directory path.
  3. Execute:
     ```bash
     ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add "<path>" "[optional_name]" "[optional_target_folder]"
     ```
  4. Confirm to the user that the project has been added. Heavy dependencies (`node_modules`, `.venv`, `.git`, build directories) and sensitive files (`.env`, keys, secrets) are automatically excluded.

### Changing / Choosing a Project's Folder:
- **Triggers**: "измени папку для проекта X на Y", "перенеси проект X в папку Y", "сохраняй проект X в /path", "пусть проект X лежит в /path", "set project path"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project set-path "<project_name>" "<new_path>"
  ```
  This updates the project binding, moves existing project files if the new directory is empty, and automatically heals conversation history links (`conversation_summaries.db`) so active chats point to the new folder without "missing folder" errors.

### Setting OS-Specific Target Directories:
- **Triggers**: "на Windows сохраняй проект X в D:\Projects\X", "для Mac путь к проекту X /custom/path", "set target path"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project set-target "<project_name>" "<windows|mac|linux|default>" "<target_path>"
  ```

### Setting Default Directory for All Projects:
- **Triggers**: "сохраняй проекты по умолчанию в ~/MyProjects", "измени стандартную папку для проектов"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project default-dir "<new_default_directory>"
  ```

### Listing Projects:
- **Triggers**: "какие проекты синхронизируются?", "покажи список проектов", "list synced projects", "где лежат проекты?"
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

## 3. Google Drive Synchronization

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
- **Triggers**: "подтяни настройки с гугл диска", "восстанови из google drive", "восстанови переписку из гугл диска"
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

## 4. Git Synchronization

### Push to Git:
- **Triggers**: "синхронизируй с гит", "запушь настройки в репозиторий", "sync git", "сохрани переписку в гит"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "[optional commit message]"
  ```

### Pull from Git:
- **Triggers**: "подтяни изменения из гита", "pull git", "обнови настройки из репозитория", "восстанови чаты из гита"
- **Action**: Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull
  ```

### Git Status & Init:
- **Status**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh status`
- **Init**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh init "<remote_url>"`

---

## 5. Full / Universal Sync

When the user asks to "синхронизируй всё" or "полная синхронизация":
- Run:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
  ```

---

## 6. Security & Safety Principles
- **Credential Protection**: NEVER commit or upload sensitive files (`.env*`, private SSH/SSL keys `id_rsa*`, `*.pem`, `*.key`, OAuth tokens `jetski-standalone-oauth-token`, `*.token*`, SQLite lock/WAL files `*.db-wal`, `*.db-shm`).
- **Path Traversal Protection**: System roots (`/`, `/etc`, `C:\Windows`) and user home root cannot be added as projects.
- **Cross-Platform Compatibility**: When pulling a project from another operating system, if the path is incompatible with the host OS, it is safely mapped to `~/Developer/<project_name>`.
- **Database Safety**: Live SQLite databases are safely snapshotted via Python's `sqlite3.backup()` API to merge uncommitted WAL transactions without file corruption.
