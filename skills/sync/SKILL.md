---
name: antigravity-sync
description: Cross-platform synchronization for Antigravity configuration, skills, rules, MCP servers, brain artifacts, and user projects via Git and/or Google Drive on macOS, Windows, and Linux. Add projects to sync directly via chat.
---

# Antigravity Cross-Platform Sync Skill

This skill provides multi-target synchronization (Git, Google Drive) for Antigravity configurations, rules, skills, MCP servers, brain artifacts, and user-specified development projects across macOS, Linux, and Windows.

## Execution Entry Points
- **macOS / Linux**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh`
- **Windows**: `%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd`
- **Universal Python**: `python3 ~/.gemini/config/plugins/antigravity-sync/scripts/sync_manager.py`

Pure Python synchronizer requires zero third-party dependencies and no `rsync` installation.

---

## Instructions for AI Agents

### 1. Adding & Managing Projects in Sync
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

### 2. Google Drive Synchronization Workflow

- **Auto-Detection & Path Setting**:
  Check if Google Drive is available on the machine (supports macOS CloudStorage, Windows Drive letters G:/H:, and Linux mount points):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive detect
  ```
  Set custom path:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive set-path "<path_to_gdrive_folder>"
  ```

- **Push to Google Drive**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
  ```

- **Pull from Google Drive**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull
  ```

- **Google Drive Status**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive status
  ```

---

### 3. Git Synchronization Workflow

- **Initialization**:
  Connects to a remote repository (GitHub, GitLab, etc.):
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh init "<remote_url>"
  ```
  *(URLs are strictly validated to prevent flag injection attacks).*

- **Push to Git**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "[commit message]"
  ```

- **Pull from Git**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull
  ```

- **Git Status**:
  ```bash
  ~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh status
  ```

---

### 4. Combined / All Targets Sync
- **Push all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push`
- **Pull all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all pull`
- **Status all**: `~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all status`
