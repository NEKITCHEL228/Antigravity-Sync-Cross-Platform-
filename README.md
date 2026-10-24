<div align="center">

# 🚀 Antigravity Sync (Cross-Platform)

<p align="center">
  <a href="#-english"><img src="https://img.shields.io/badge/Language-English-007ACC?style=for-the-badge&logo=github" alt="English"></a>
  <a href="#-русский"><img src="https://img.shields.io/badge/Язык-Русский-D9381E?style=for-the-badge" alt="Русский"></a>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)]()
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-yellow.svg)]()
[![Antigravity](https://img.shields.io/badge/Google%20Antigravity-2.0-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-1.3.0-orange.svg)]()

*Universal cross-platform synchronization and backup plugin for Google Antigravity. Seamlessly continue conversations with models and sync configurations, skills, rules, and projects via Git & Google Drive.*

---

</div>

<p align="center">
  <b>Quick Navigation / Быстрая навигация:</b><br>
  <a href="#-english"><b>🇬🇧 English Documentation</b></a> | <a href="#-русский"><b>🇷🇺 Русская документация</b></a>
</p>

---

<a name="-english"></a>
## 🇬🇧 English

### Overview
**Antigravity Sync** is an open-source, zero-dependency plugin designed for **Google Antigravity 2.0** on **macOS, Windows, and Linux**. It automatically synchronizes and backs up your **conversation history, chat trajectories, and model context**, agent configurations, custom skills, rules, MCP servers, brain artifacts, and custom developer projects via **Git** (GitHub, GitLab, self-hosted) and **Google Drive**.

---

### Key Features
* 💬 **Seamless Conversation Continuity:** Automatically captures and syncs full conversation histories (`conversations/*.db`), step outputs, thought trajectories, and transcripts (`transcript.jsonl`). Switch between machines and continue your chat with the model right where you left off.
* 🗄️ **Smart SQLite Backup & Merge:** Uses Python's native `sqlite3.backup()` API to snapshot live databases without locking conflicts, safely merging SQLite WAL pages and conversation history lists across devices.
* 🌐 **100% Cross-Platform:** Pure Python 3 core engine. No external tools like `rsync` or MSYS2 required—runs natively on Windows cmd/PowerShell, macOS, and Linux.
* ☁️ **Dual Sync Providers:**
  * **Git:** Private GitHub, GitLab, or any remote repository.
  * **Google Drive:** Auto-detection for macOS CloudStorage, Windows virtual drive letters (`G:\`, `H:\`), and Linux GVFS mounts.
* 📁 **Chat-Driven Project Sync:** Add, inspect, and remove developer projects from sync simply by asking the agent in natural language.
* 🛡️ **Zero-Leakage Security:**
  * Automatic exclusion of secrets (`.env*`, `id_rsa*`, `*.pem`, `*.key`, OAuth tokens, session tokens).
  * Build and cache exclusion (`node_modules`, `.venv`, `.git`, `dist`, `build`, caches).
  * Path traversal protection against unauthorized system writes.
  * Atomic JSON writing preventing configuration corruption during power outages.
  * Cross-platform path normalization (e.g. mapping Windows paths to `~/Developer` when pulling on macOS/Linux).

---

### What is Synchronized?
1. **Conversation History & Full Context** (`~/.gemini/antigravity/` or `%USERPROFILE%\.gemini\antigravity\`):
   * Trajectory databases with full messages and steps (`conversations/*.db`)
   * Conversation history and sidebar summaries (`conversation_summaries.db`, `agyhub_summaries_proto.pb`)
   * Detailed transcripts, step outputs, and logs (`brain/<id>/.system_generated/logs/transcript*.jsonl`, `steps/`)
   * Metadata & annotations (`annotations/*.pbtxt`)
2. **Antigravity Configuration** (`~/.gemini/config/`):
   * Custom Skills (`skills/`)
   * Agent Rules (`rules/`)
   * Model Context Protocol servers (`mcp_config.json`)
   * Installed Plugins (`plugins/`)
   * Environment parameters (`config.json`)
3. **Tracked User Projects** (any local repository or workspace added via chat or CLI)

---

### Chat Commands (Prompting the AI)

You can manage synchronization directly through chat with the agent:

| Action | Example Prompt |
| :--- | :--- |
| **Sync Conversations & Context** | *"Sync conversation history"* or *"Backup chats to Google Drive"* |
| **Restore & Continue Chats** | *"Pull chat history from Git"* or *"Restore conversations from Google Drive"* |
| **Add Project to Sync** | *"Add project `/path/to/my-app` to sync"* |
| **List Synced Projects** | *"What projects are currently synced?"* |
| **Google Drive Sync** | *"Sync with Google Drive"* or *"Pull from Google Drive"* |
| **Git Sync** | *"Sync with Git"* or *"Pull changes from Git"* |
| **Full Sync** | *"Sync all"* (pushes conversations, config, and projects to both Git & Google Drive) |

---

### Terminal CLI Usage

Launchers are available for each platform inside `scripts/`:

#### macOS / Linux
```bash
# Push configurations, conversations, and projects
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "Updated chats and project"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull

# Google Drive sync (includes full chat trajectories)
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull

# Add a project
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add /path/to/project "project-name"

# Full sync (all destinations)
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
```

#### Windows (Command Prompt / PowerShell)
```cmd
rem Push configurations, conversations, and projects
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd push "Updated chats and config"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd pull

rem Google Drive sync
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive push
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive pull

rem Add a project
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project add C:\dev\project "project-name"
```

---

<p align="right">
  <a href="#-русский"><b>🇷🇺 Перейти к русской версии</b></a> •
  <a href="#-antigravity-sync-cross-platform"><b>⬆ Наверх</b></a>
</p>

---

<a name="-русский"></a>
## 🇷🇺 Русский

### Обзор
**Antigravity Sync** — кроссплатформенный плагин для **Google Antigravity 2.0** на **macOS, Windows и Linux**. Обеспечивает непрерывность работы: синхронизирует **историю переписки, контекст диалогов, степы и мысли модели**, настройки среды, навыки (Skills), правила (Rules), серверы MCP и проекты разработки через **Git** (GitHub, GitLab) и **Google Drive**.

---

### Ключевые возможности
* 💬 **Продолжение диалогов на любом компьютере:** автоматический захват и перенос всей траектории переписки (`conversations/*.db`), степов выполнения, артефактов и транскриптов (`transcript.jsonl`). Пересаживайтесь за другой ноутбук или ПК и продолжайте разговор с агентом с того же места!
* 🗄️ **Надёжный бэкап и слияние SQLite:** использование штатного API `sqlite3.backup()` позволяет создавать снимки баз данных «на лету» без блокировок и потери несохранённых данных из WAL-файлов. История диалогов с разных устройств объединяется без перезаписи.
* 🌐 **Полная кроссплатформенность:** ядро на чистом Python 3 без внешних зависимостей. Работает без необходимости ставить `rsync`, MSYS2 или Cygwin. Включает готовые лаунчеры для bash (`sync.sh`) и Windows (`sync.cmd`).
* ☁️ **Два провайдера синхронизации:**
  * **Git:** приватные репозитории на GitHub, GitLab или любом Git-сервере.
  * **Google Drive:** автоопределение путей на macOS (CloudStorage), Windows (диски `G:\`, `H:\`) и Linux (GVFS).
* 📁 **Управление проектами через чат:** подключайте любые локальные репозитории к синхронизации прямо фразой в диалоге с агентом.
* 🛡️ **Безопасность данных (Zero-Leakage):**
  * Автоматическая изоляция секретов (`.env*`, SSH-ключи `id_rsa*`, SSL-сертификаты `*.pem`, `*.key`, OAuth-токены сессий `jetski-standalone-oauth-token`, `*.token`).
  * Исключение тяжёлых папок (`node_modules`, `.venv`, `.git`, кэши сборки).
  * Защита от Path Traversal и системных каталогов (`/etc`, `/System`, `C:\Windows`, корень диска).
  * Атомарная запись конфигурационных файлов JSON для защиты от сбоев питания.
  * Кроссплатформенная адаптация путей при переносе между разными ОС.

---

### Что синхронизируется?
1. **История диалогов и контекст моделей** (`~/.gemini/antigravity/` / `%USERPROFILE%\.gemini\antigravity\`):
   * Базы данных траекторий со всеми сообщениями и шагами (`conversations/*.db`)
   * Сводки и список истории в боковой панели (`conversation_summaries.db`, `agyhub_summaries_proto.pb`)
   * Транскрипты, результаты шагов и логи (`brain/<id>/.system_generated/logs/transcript*.jsonl`, `steps/`)
   * Метаданные и аннотации (`annotations/*.pbtxt`)
2. **Конфигурация Antigravity** (`~/.gemini/config/`):
   * Пользовательские навыки (`skills/`)
   * Правила поведения агентов (`rules/`)
   * Серверы протокола Model Context Protocol (`mcp_config.json`)
   * Установленные плагины (`plugins/`)
   * Параметры окружения (`config.json`)
3. **Отслеживаемые проекты** (любые локальные репозитории и каталоги)

---

### Команды в чате с агентом (Нейросеть)

Синхронизацией можно управлять обычными фразами в чате:

| Действие | Пример фразы в чате |
| :--- | :--- |
| **Синхронизировать переписку и контекст** | *«Синхронизируй историю переписки»* или *«Бэкап диалогов в Google Drive»* |
| **Подтянуть историю чатов** | *«Подтяни историю диалогов из Git»* или *«Восстанови чаты из Google Drive»* |
| **Добавить проект** | *«Добавь проект `/Users/.../my-app` в синхронизацию»* |
| **Список проектов** | *«Какие проекты сейчас синхронизируются?»* |
| **Google Drive** | *«Синхронизируй с Google Drive»* или *«Подтяни данные с Google Drive»* |
| **Git** | *«Синхронизируй с Git»* или *«Подтяни изменения из Git»* |
| **Полная синхронизация** | *«Синхронизируй всё»* (отправка диалогов, настроек и проектов в Git и Google Drive) |

---

### Использование через терминал

Скрипты расположены в папке `scripts/`:

#### macOS / Linux
```bash
# Синхронизация с Git (включая историю диалогов и контекст)
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "Обновил диалоги и проекты"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull

# Синхронизация с Google Drive
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull

# Добавить проект
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add /путь/к/проекту "имя-проекта"

# Синхронизация всех источников
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
```

#### Windows (cmd.exe / PowerShell)
```cmd
rem Синхронизация с Git (включая историю диалогов и контекст)
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd push "Обновил диалоги и проекты"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd pull

rem Google Drive
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive push
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive pull

rem Добавить проект
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project add C:\dev\project "project-name"
```

---

<p align="right">
  <a href="#-english"><b>🇬🇧 Back to English</b></a> •
  <a href="#-antigravity-sync-cross-platform"><b>⬆ Наверх</b></a>
</p>
