# Установка npm 
## Linux
### Ubuntu/Debian
```bash
sudo apt update
sudo apt install nodejs npm
```

### Arch Linux
```bash
sudo pacman -S nodejs npm
```

### Проверка установки
```bash
node -v
npm -v
```
## Windows (10/11)
Скачайте [файл](https://nodejs.org/dist/v22.19.0/node-v22.19.0-x64.msi) и следуйте инструкциям установщика.
**Примечание**: работайте через cmd а не PowerShell.
---
# Установка fleet-server

Получение и распаковка архива:

```bash
curl -sSL https://github.com/LARS-robots/public-install/raw/main/fleet_server/install.py | python3
```

После распаковки:
```bash
cd fleet_server
npm ci
npm start
```
