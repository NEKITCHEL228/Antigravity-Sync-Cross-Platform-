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

*Universal cross-platform synchronization and backup plugin for Google Antigravity (Git & Google Drive).*

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
**Antigravity Sync** is an open-source, zero-dependency plugin designed for **Google Antigravity 2.0** on **macOS, Windows, and Linux**. It automatically manages synchronization and backups for your agent configurations, skills, rules, MCP servers, brain artifacts, and custom developer projects via **Git** (GitHub, GitLab, self-hosted) and **Google Drive**.

---

### Key Features
* 🌐 **100% Cross-Platform:** Pure Python 3 core engine. No external tools like `rsync` or MSYS2 required—runs natively on Windows cmd/PowerShell, macOS, and Linux.
* ☁️ **Dual Sync Providers:**
  * **Git:** Private GitHub, GitLab, or any remote repository.
  * **Google Drive:** Auto-detection for macOS CloudStorage, Windows virtual drive letters (`G:\`, `H:\`), and Linux GVFS mounts.
* 💬 **Chat-Driven Project Sync:** Add, inspect, and remove developer projects from sync simply by asking the agent in natural language.
* 🛡️ **Zero-Leakage Security:**
  * Automatic exclusion of secrets (`.env*`, `id_rsa*`, `*.pem`, `*.key`, OAuth tokens, session tokens).
  * Build and cache exclusion (`node_modules`, `.venv`, `.git`, `dist`, `build`, caches).
  * Path traversal protection against unauthorized system writes.
  * Atomic JSON writing preventing configuration corruption during power outages.
  * Cross-platform path normalization (e.g. mapping Windows paths to `~/Developer` when pulling on macOS/Linux).

---

### What is Synchronized?
1. **Antigravity Configuration** (`~/.gemini/config/` or `%USERPROFILE%\.gemini\config\`):
   * Custom Skills (`skills/`)
   * Agent Rules (`rules/`)
   * Model Context Protocol servers (`mcp_config.json`)
   * Installed Plugins (`plugins/`)
   * Environment parameters (`config.json`)
2. **Brain Artifacts & Notes** (`~/.gemini/antigravity/brain/`)
3. **Tracked User Projects** (any local repository or workspace added via chat or CLI)

---

### Chat Commands (Prompting the AI)

You can manage synchronization directly through chat with the agent:

| Action | Example Prompt |
| :--- | :--- |
| **Add Project** | *"Add project `/path/to/my-app` to sync"* |
| **List Projects** | *"What projects are currently synced?"* |
| **Remove Project** | *"Remove project `my-app` from sync"* |
| **Google Drive Sync** | *"Sync with Google Drive"* or *"Pull from Google Drive"* |
| **Git Sync** | *"Sync with Git"* or *"Pull changes from Git"* |
| **Full Sync** | *"Sync all"* (pushes to both Git & Google Drive) |

---

### Terminal CLI Usage

Launchers are available for each platform inside `scripts/`:

#### macOS / Linux
```bash
# Add a project
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add /path/to/project "project-name"

# Google Drive sync
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull

# Git sync
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "Updated skills and project"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull

# Full sync
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
```

#### Windows (Command Prompt / PowerShell)
```cmd
rem Add a project
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project add C:\dev\project "project-name"

rem Google Drive sync
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive push
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive pull

rem Git sync
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd push "Updated config"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd pull
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
**Antigravity Sync** — кроссплатформенный плагин для **Google Antigravity 2.0** на **macOS, Windows и Linux**. Обеспечивает надёжную синхронизацию и резервное копирование настроек среды, навыков (Skills), правил (Rules), серверов MCP, артефактов brain и пользовательских проектов разработки через **Git** (GitHub, GitLab) и **Google Drive**.

---

### Ключевые возможности
* 🌐 **Полная кроссплатформенность:** ядро на чистом Python 3 без внешних зависимостей. Работает без необходимости ставить `rsync`, MSYS2 или Cygwin. Включает готовые лаунчеры для bash (`sync.sh`) и Windows (`sync.cmd`).
* ☁️ **Два провайдера синхронизации:**
  * **Git:** приватные репозитории на GitHub, GitLab или любом собственном Git-сервере.
  * **Google Drive:** автоопределение путей на macOS (CloudStorage), Windows (виртуальные диски `G:\`, `H:\`) и Linux (GVFS).
* 💬 **Управление проектами через чат:** подключайте любые локальные папки и репозитории к синхронизации прямо фразой в диалоге с агентом.
* 🛡️ **Безопасность данных (Zero-Leakage):**
  * Автоматическая изоляция секретов (`.env*`, SSH-ключи `id_rsa*`, SSL-сертификаты `*.pem`, `*.key`, OAuth-токены сессий `jetski-standalone-oauth-token`, `*.token`).
  * Исключение тяжёлых папок (`node_modules`, `.venv`, `.git`, кэши сборки).
  * Защита от Path Traversal и системных каталогов (`/etc`, `/System`, `C:\Windows`, корень диска).
  * Атомарная запись конфигурационных файлов JSON для защиты от сбоев питания.
  * Кроссплатформенная адаптация путей при переносе между разными ОС (например, адаптация путей Windows в `~/Developer` на macOS/Linux).

---

### Что синхронизируется?
1. **Конфигурация Antigravity** (`~/.gemini/config/` / `%USERPROFILE%\.gemini\config\`):
   * Пользовательские навыки (`skills/`)
   * Правила поведения агентов (`rules/`)
   * Серверы протокола Model Context Protocol (`mcp_config.json`)
   * Установленные плагины (`plugins/`)
   * Параметры окружения (`config.json`)
2. **Артефакты brain и заметки** (`~/.gemini/antigravity/brain/`)
3. **Отслеживаемые проекты** (любые локальные репозитории и каталоги)

---

### Команды в чате с агентом (Нейросеть)

Синхронизацией можно управлять обычными фразами в чате:

| Действие | Пример фразы в чате |
| :--- | :--- |
| **Добавить проект** | *«Добавь проект `/Users/.../my-app` в синхронизацию»* |
| **Список проектов** | *«Какие проекты сейчас синхронизируются?»* |
| **Удалить проект** | *«Удали проект `my-app` из синхронизации»* |
| **Google Drive** | *«Синхронизируй с Google Drive»* или *«Подтяни данные с Google Drive»* |
| **Git** | *«Синхронизируй с Git»* или *«Подтяни изменения из Git»* |
| **Полная синхронизация** | *«Синхронизируй всё»* (отправка в Git и в Google Drive) |

---

### Использование через терминал

Скрипты расположены в папке `scripts/`:

#### macOS / Linux
```bash
# Добавить проект
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add /путь/к/проекту "имя-проекта"

# Синхронизация с Google Drive
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull

# Синхронизация с Git
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "Обновление настроек"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull

# Синхронизация всех источников
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
```

#### Windows (cmd.exe / PowerShell)
```cmd
rem Добавить проект
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project add C:\dev\project "project-name"

rem Google Drive
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive push
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive pull

rem Git
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd push "Обновление настроек"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd pull
```

---

<p align="right">
  <a href="#-english"><b>🇬🇧 Back to English</b></a> •
  <a href="#-antigravity-sync-cross-platform"><b>⬆ Наверх</b></a>
</p>
