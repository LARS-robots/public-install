# LARS-cloud Installation

## Быстрая установка (работает везде)

```bash
python3 -c "import urllib.request; urllib.request.urlretrieve('https://github.com/LARS-robots/public-install/raw/main/LARS-cloud/install.py', 'install.py'); import subprocess; subprocess.run(['python3', 'install.py'])"
```

## Альтернативные способы скачать install.py:

скачайте файл `install.py` из репозитория и поместите его в папку в желаемом месте.

## Запуск установки:
```bash
python3 install.py
```

## Что делает скрипт:

1. **Проверяет системные требования** - Docker, Docker Compose, Python3
2. **Скачивает tar-архив с проектом** - Получает последнюю версию LARS-cloud
3. **Создает директорию LARS-cloud** - В текущей папке
4. **Распаковывает архив** - Извлекает все файлы проекта
5. **Собирает Docker образы** - Использует `docker buildx bake` для сборки контейнеров

## Системные требования

- **Python 3.11** (для скрипта установки)
- **Docker** (для контейнеров) 
- **Docker Compose** (для оркестрации)
- **Docker Buildx** (для сборки образов)
- **NVIDIA GPU** (опционально, для ускорения)

## Поддерживаемые ОС

- ✅ **Linux** (Ubuntu, Debian, CentOS, etc.)
- ✅ **macOS** (с Docker Desktop)
- ✅ **Windows** (с Docker Desktop и Python)

## После установки

Интерфейс будет доступен по адресу: http://localhost:7860

Для запуска выполните:
```bash
cd LARS-cloud
docker-compose up -d
```
