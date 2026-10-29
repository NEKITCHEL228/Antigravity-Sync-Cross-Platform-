<div align="center">

# 🚀 Antigravity Sync (Cross-Platform)

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-007ACC?style=for-the-badge&logo=github" alt="English"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/Язык-Русский-D9381E?style=for-the-badge" alt="Русский"></a>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)]()
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-yellow.svg)]()
[![Antigravity](https://img.shields.io/badge/Google%20Antigravity-2.0-blue.svg)]()
[![Version](https://img.shields.io/badge/Version-1.5.0-orange.svg)]()

*Кроссплатформенный плагин резервного копирования и синхронизации для Google Antigravity (Git & Google Drive). Непрерывность диалогов с моделями, сохранение контекста, настроек и проектов с выбором индивидуальных папок.*

---

</div>

## Обзор
**Antigravity Sync** — инструмент синхронизации и резервного копирования для **Google Antigravity 2.0** на **macOS, Windows и Linux**. Обеспечивает непрерывность работы: синхронизирует **историю переписки, контекст диалогов, степы и мысли модели**, настройки среды, навыки (Skills), правила (Rules), серверы MCP и проекты разработки через **Git** и **Google Drive**.

---

## Ключевые возможности
* 💬 **Продолжение диалогов на любом компьютере:** автоматический захват и перенос всей траектории переписки (`conversations/*.db`), степов выполнения, артефактов и транскриптов (`transcript.jsonl`). Пересаживайтесь за другой ноутбук или ПК и продолжайте разговор с агентом с того же места!
* 🔀 **Умное разрешение конфликтов диалогов:** если вы общались в одном чате с разных устройств, плагин пошагово определит расхождение и предложит объединить обе истории (Merge), разветвить в два отдельных чата (Fork) или оставить нужную версию (Local/Remote).
* 🗄️ **Надёжный бэкап и слияние SQLite:** использование штатного API `sqlite3.backup()` позволяет создавать снимки баз данных «на лету» без блокировок и потери несохранённых данных из WAL-файлов. История диалогов с разных устройств объединяется без перезаписи.
* 📁 **Индивидуальные папки для каждого проекта:** возможность выбирать, куда именно восстанавливать или сохранять каждый проект. Проекты могут жить в совершенно разных папках на разных компьютерах (`project set-path`, `project set-target`, `config default-dir`).
* 🩹 **Автоматическое исправление путей проектов и Antigravity IDE:** сопоставляет и перелинковывает пути из других ОС (например, диски Windows `C:\` на macOS) в истории диалогов и в файлах проектов IDE (`~/.gemini/config/projects/*.json`), полностью устраняя предупреждения «Пропавшая папка» (Missing folder).
* 🔌 **Кроссплатформенная изоляция MCP-серверов:** автоматически выявляет несовместимые команды MCP (например, `.exe` файлы Windows на macOS) и изолирует их в `_disabled_mcpServers`, сохраняя для целевых ПК и избавляя от всплывающих ошибок при старте.
* 🌐 **Полная кроссплатформенность:** ядро на чистом Python 3 без сторонних зависимостей. Работает без `rsync`, MSYS2 или Cygwin. Включает готовые лаунчеры для bash (`sync.sh`) и Windows (`sync.cmd`).
* ☁️ **Два провайдера синхронизации:**
  * **Git:** приватные репозитории на GitHub, GitLab или любом Git-сервере.
  * **Google Drive:** автоматическое обнаружение путей на macOS (CloudStorage), Windows (виртуальные диски `G:\`, `H:\`) и Linux (GVFS).
* 🛡️ **Безопасность данных (Zero-Leakage):**
  * Автоматическая изоляция секретов (`.env*`, SSH-ключи `id_rsa*`, SSL-сертификаты `*.pem`, `*.key`, OAuth-токены сессий `jetski-standalone-oauth-token`, `*.token`).
  * Исключение тяжёлых папок (`node_modules`, `.venv`, `.git`, кэши сборки).
  * Защита от Path Traversal и системных каталогов (`/etc`, `/System`, `C:\Windows`, корень диска).
  * Атомарная запись конфигурационных файлов JSON для защиты от сбоев питания.
  * Кроссплатформенная адаптация путей при переносе между разными ОС.

---

## Что синхронизируется?
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

## Команды в чате с агентом (Нейросеть)

Синхронизацией и папками проектов можно управлять обычными фразами в чате:

| Действие | Пример фразы в чате |
| :--- | :--- |
| **Синхронизировать переписку и контекст** | *«Синхронизируй историю переписки»* или *«Бэкап диалогов в Google Drive»* |
| **Подтянуть историю чатов** | *«Подтяни историю диалогов из Git»* или *«Восстанови чаты из Google Drive»* |
| **Добавить проект в синхронизацию** | *«Добавь проект `/Users/.../my-app` в синхронизацию»* или *«Добавь проект X в папку Y»* |
| **Выбрать / изменить папку проекта** | *«Перенеси проект `my-app` в папку `/new/path`»* или *«Сохраняй проект `my-app` в `D:\Projects\app`»* |
| **Настроить папку для конкретной ОС** | *«На Windows восстанавливай проект `my-app` в `C:\work\app`»* |
| **Папка по умолчанию для всех проектов** | *«Сделай стандартной папкой для проектов `~/MyProjects`»* |
| **Список проектов** | *«Какие проекты сейчас синхронизируются?»* или *«Где лежат мои проекты?»* |
| **Google Drive** | *«Синхронизируй с Google Drive»* или *«Подтяни данные с Google Drive»* |
| **Git** | *«Синхронизируй с Git»* или *«Подтяни изменения из Git»* |
| **Полная синхронизация** | *«Синхронизируй всё»* (отправка диалогов, настроек и проектов в Git и Google Drive) |

---

## Использование через терминал

Скрипты расположены в папке `scripts/`:

### macOS / Linux
```bash
# Синхронизация с Git (включая историю диалогов и контекст)
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh push "Обновил диалоги и проекты"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh pull

# Синхронизация с Google Drive
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive push
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh gdrive pull

# Управление проектами и выбор индивидуальных папок
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project add /путь/к/проекту [имя] [/целевая/папка]
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project set-path "имя-проекта" /новый/путь
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project set-target "имя-проекта" windows "C:\work\app"
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh project list

# Разрешение конфликтов чатов (при одновременной переписке с разных ПК)
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh conflict list
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh conflict resolve <id|all> merge
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh conflict resolve <id|all> fork
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh conflict strategy prompt

# Настройки плагина и стандартные папки для ОС
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh config show
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh config default-dir ~/MyProjects mac
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh config default-dir "D:\Projects" windows
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh heal

# Синхронизация всех источников
~/.gemini/config/plugins/antigravity-sync/scripts/sync.sh all push
```

### Windows (cmd.exe / PowerShell)
```cmd
rem Синхронизация с Git (включая историю диалогов и контекст)
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd push "Обновил диалоги и проекты"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd pull

rem Google Drive
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive push
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd gdrive pull

rem Управление проектами и выбор индивидуальных папок
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project add C:\dev\project [имя] [C:\целевая\папка]
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project set-path "имя-проекта" D:\Projects\app
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project set-target "имя-проекта" mac "/Users/name/Projects/app"
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd project list

rem Разрешение конфликтов и настройки
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd conflict list
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd conflict resolve all merge
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd config show
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd config default-dir D:\Projects windows
%USERPROFILE%\.gemini\config\plugins\antigravity-sync\scripts\sync.cmd heal
```
