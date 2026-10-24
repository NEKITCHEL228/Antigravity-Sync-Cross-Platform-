---
name: antigravity-sync
description: Cross-platform synchronization for Antigravity configuration, conversation history, context, skills, rules, MCP servers, brain artifacts, and user projects via Git and/or Google Drive on macOS, Windows, and Linux. Continue chats with models seamlessly across devices.
---

# Antigravity Cross-Platform Sync Skill

This skill provides multi-target synchronization (Git, Google Drive) for Antigravity configurations, full conversation trajectories, chat context, rules, skills, MCP servers, brain artifacts, and user-specified development projects across macOS, Linux, and Windows.

## Execution Entry Points
- **macOS / Linux**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh`
- **Windows**: `%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd`
- **Universal Python**: `python3 ~/.gemini/config/plugins/antigravity-sync/scripts/sync_manager.py`

Pure Python synchronizer requires zero third-party dependencies and no `rsync` installation.

---

## Instructions for AI Agents

### 1. Conversation History & Context Continuation
All synchronization commands automatically capture and restore:
- Complete conversation trajectories (`conversations/*.db`).
- SQLite Write-Ahead Log (WAL) commits safely merged via Python's `sqlite3.backup()` API.
- Conversation summaries index (`conversation_summaries.db`, `agyhub_summaries_proto.pb`) for the sidebar history list.
- Transcripts (`transcript.jsonl`, `transcript_full.jsonl`), step logs, and inter-agent messages.
- Conversation metadata and annotations (`annotations/*.pbtxt`).

When pulled on another device, the user can open any past conversation from the sidebar and immediately continue chatting with the model with full previous context preserved.

---

### 2. Adding & Managing Projects in Sync
The user can add arbitrary projects to the synchronization pool via chat.

- **Add Project**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add "<path_to_project>" "[optional_name]"
  ```
  *Security & Optimization:*
  - System directories (`/etc`, `/System`, `C:\Windows`, user home root) are strictly prohibited.
  - Secrets and environment files (`.env*`, `id_rsa*`, `*.pem`, `*.key`, tokens) are automatically excluded.
  - Heavy caches (`node_modules`, `venv`, `.git`, `dist`, `build`) are excluded.

- **List Synced Projects**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project list
  ```

- **Remove Project from Sync**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project remove "<name_or_path>"
  ```

---

### 3. Google Drive Synchronization Workflow

- **Auto-Detection & Path Setting**:
  Check if Google Drive is available on the machine (supports macOS CloudStorage, Windows Drive letters G:/H:, and Linux mount points):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive detect
  ```
  Set custom path:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive set-path "<path_to_gdrive_folder>"
  ```

- **Push to Google Drive** (Includes conversations, context, configs, projects):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
  ```

- **Pull from Google Drive** (Restores conversations, context, configs, projects):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull
  ```

- **Google Drive Status**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive status
  ```

---

### 4. Git Synchronization Workflow

- **Initialization**:
  Connects to a remote repository (GitHub, GitLab, etc.):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh init "<remote_url>"
  ```

- **Push to Git** (Includes conversations, context, configs, projects):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "[commit message]"
  ```

- **Pull from Git** (Restores conversations, context, configs, projects):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull
  ```

- **Git Status**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh status
  ```

---

### 5. Combined / All Targets Sync
- **Push all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push`
- **Pull all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all pull`
- **Status all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all status`
