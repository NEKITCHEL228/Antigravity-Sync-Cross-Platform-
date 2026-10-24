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

*Кроссплатформенный плагин резервного копирования и синхронизации для Google Antigravity (Git & Google Drive).*

---

</div>

## Обзор
**Antigravity Sync** — инструмент синхронизации и резервного копирования для **Google Antigravity 2.0** на **macOS, Windows и Linux**. Позволяет синхронизировать настройки окружения, навыки (Skills), правила (Rules), серверы MCP, артефакты brain и проекты разработки через **Git** и **Google Drive**.

---

## Ключевые возможности
* 🌐 **Полная кроссплатформенность:** ядро на чистом Python 3 без сторонних зависимостей. Работает без `rsync`, MSYS2 или Cygwin. Включает готовые лаунчеры для bash (`sync.sh`) и Windows (`sync.cmd`).
* ☁️ **Два провайдера синхронизации:**
  * **Git:** приватные репозитории на GitHub, GitLab или любом Git-сервере.
  * **Google Drive:** автоматическое обнаружение путей на macOS (CloudStorage), Windows (виртуальные диски `G:\`, `H:\`) и Linux (GVFS).
* 💬 **Управление проектами через чат:** подключайте любые локальные папки и репозитории к синхронизации прямо фразой в диалоге с агентом.
* 🛡️ **Безопасность данных (Zero-Leakage):**
  * Автоматическая изоляция секретов (`.env*`, SSH-ключи `id_rsa*`, SSL-сертификаты `*.pem`, `*.key`, OAuth-токены сессий `jetski-standalone-oauth-token`, `*.token`).
  * Исключение тяжёлых папок (`node_modules`, `.venv`, `.git`, кэши сборки).
  * Защита от Path Traversal и системных каталогов (`/etc`, `/System`, `C:\Windows`, корень диска).
  * Атомарная запись конфигурационных файлов JSON для защиты от сбоев питания.
  * Кроссплатформенная адаптация путей при переносе между разными ОС.

---

## Что синхронизируется?
1. **Конфигурация Antigravity** (`~/.gemini/config/` / `%USERPROFILE%\.gemini\config\`):
   * Пользовательские навыки (`skills/`)
   * Правила поведения агентов (`rules/`)
   * Серверы протокола Model Context Protocol (`mcp_config.json`)
   * Установленные плагины (`plugins/`)
   * Параметры окружения (`config.json`)
2. **Артефакты brain и заметки** (`~/.gemini/antigravity/brain/`)
3. **Отслеживаемые проекты** (любые локальные репозитории и каталоги)

---

## Команды в чате с агентом (Нейросеть)

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

## Использование через терминал

Скрипты расположены в папке `scripts/`:

### macOS / Linux
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

### Windows (cmd.exe / PowerShell)
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
