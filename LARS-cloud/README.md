# LARS-cloud Installation

---

# Подробные инструкции по установке

## Linux (Ubuntu/Debian)

### 1. Установка Docker и Docker Compose

```bash
# Обновить список пакетов
sudo apt update

# Установить зависимости для HTTPS репозиториев
sudo apt install apt-transport-https ca-certificates curl software-properties-common

# Добавить официальный GPG ключ Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавить репозиторий Docker
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Обновить список пакетов
sudo apt update

# Установить Docker Engine и Docker Compose
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Настройка GPU поддержки (опционально)

```bash
# Установить NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Настроить Docker для работы с GPU
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 3. Проверка установки

```bash
docker --version
docker compose version
docker buildx version
nvidia-smi  # если есть GPU
```

## Windows

### 1. Установка Docker Desktop

- Скачать Docker Desktop: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe
- Запустить установщик и следовать инструкциям
- Включить WSL 2 integration в настройках Docker Desktop

### 2. Настройка GPU поддержки (опционально)

```powershell
# Обновить WSL 2 ядро
wsl --update

# Проверить наличие NVIDIA GPU
nvidia-smi

# Включить WSL 2 backend в Docker Desktop:
# Settings → General → Use the WSL 2 based engine
# Settings → Resources → WSL Integration → Enable integration
```

### 3. Проверка установки

```powershell
docker --version
docker compose version
docker buildx version
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi
```

## macOS

### 1. Установка Docker Desktop

- Скачать Docker Desktop для Mac: https://desktop.docker.com/mac/main/amd64/Docker.dmg
- Установить и запустить Docker Desktop
- Docker Compose включен по умолчанию

### 2. Проверка установки

```bash
docker --version
docker compose version
docker buildx version
```

---

# Запуск LARS-cloud

## Быстрая установка (работает везде)

```bash
curl -sSL https://github.com/LARS-robots/public-install/raw/main/LARS-cloud/install.py | python3
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
docker-compose up
```

*Последнее обновление: $(date)*
