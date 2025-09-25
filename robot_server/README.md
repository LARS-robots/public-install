# LARS Robot Server

## Быстрая установка
```bash
curl -sSL https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/install.py | python3
```

## Альтернативная установка
```bash
wget https://raw.githubusercontent.com/LARS-robots/public-install/main/robot_server/install.py
python3 install.py
# OR
git clone https://github.com/LARS-robots/public-install.git
cd public-install/robot_server
python3 install.py
```

## После установки

### Запуск через systemd
```bash
sudo systemctl start lars-robot-server
sudo systemctl status lars-robot-server
```

### Ручной запуск
```bash
cd ~/LARS
python3 -m uvicorn robot_server.app.main:app --host 0.0.0.0 --port 8081
```

## Настройки сети
- **SSID**: LARSrobot
- **Пароль**: LARSrobot1234
- **IP робота**: 10.42.0.13:8081
- **Веб-интерфейс**: http://10.42.0.13:8081/docs

---
Версия: dev-20250925-090134
