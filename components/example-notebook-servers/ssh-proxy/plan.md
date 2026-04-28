# План реализации: SSH Proxy для Kubeflow GPU Pods

## Цель

Дать SSH/SCP/RSync доступ к GPU-подам Kubeflow через WebSocket, проброшенный через существующий HTTPS-канал Istio.

## Структура файлов

```
ssh-proxy/
├── Dockerfile
├── Makefile
├── Makefile.dev
├── requirements.txt          # websockets (для server.py)
├── .dockerignore
├── server.py                 # WebSocket ↔ sshd прокси (серверная часть)
├── ssh-proxy-client.py       # Клиент для ProxyCommand
├── pyproject.toml            # uv-конфиг для клиентского прокси
├── s6/
│   ├── cont-init.d/
│   │   └── 01-setup-ssh      # Генерация SSH host-ключей
│   └── services.d/
│       ├── ssh-server/
│       │   └── run            # Запуск sshd на 127.0.0.1:22
│       └── websocket-proxy/
│           ├── run            # Запуск server.py на 0.0.0.0:8888
│           └── finish
└── tests/
    ├── conftest.py
    ├── requirements-test.txt
    └── test_server.py
```

## Архитектура

### Серверная часть (внутри пода)

```
SSH client ──wss──> Istio ──HTTP──> websocket-proxy:8888 ──TCP──> sshd:127.0.0.1:22
```

**server.py** — asyncio-прокси на `websockets`:
- Слушает `0.0.0.0:8888`
- Plain HTTP → 200 OK (health check)
- `Upgrade: websocket` → WebSocket handshake → TCP к `127.0.0.1:22` → двунаправленный проброс
- Бинарный режим (`send_bytes`/`recv_bytes`) для корректной работы с SSH-трафиком
- Multiple sessions — nice to have (через `process_request` для обработки concurrent connections)

**sshd** конфигурация:
- `ListenAddress 127.0.0.1 22` — только loopback
- `PermitEmptyPasswords yes` — без пароля
- `PasswordAuthentication yes` — для пустого пароля
- `KbdInteractiveAuthentication no`, `ChallengeResponseAuthentication no` — только empty password
- Пользователь `jovyan`, home `/home/jovyan` (PVC-mounted)

### Клиентская часть (локальная машина)

**ssh-proxy-client.py** — asyncio-клиент:
- Аргументы: `%h %p` (от SSH ProxyCommand, игнорируются)
- `KUBEFLOW_NOTEBOOK_URL` → базовый URL, меняем `https://` на `wss://`
- `KUBEFLOW_SESSION_COOKIE` → кука для заголовка
- stdin → WebSocket (binary), WebSocket → stdout (binary)
- Обработка SIGINT/SIGTERM → graceful close

Запуск: `uv run ssh-proxy-client.py %h %p`

### Docker-образ

- Base: `ghcr.io/kubeflow/kubeflow/notebook-servers/base`
- `apt-get install openssh-server`
- `pip install websockets`
- s6-overlay: sshd + server.py как два сервиса
- Порт 8888

## Пошаговый план

### Шаг 1. `server.py` — WebSocket ↔ sshd прокси

Asyncio-сервер на `websockets`:
- `start_server` на port 8888
- `process_request` — проверяем `Upgrade: websocket`, если нет → возвращаем 200 OK
- При WebSocket: `await websocket.accept()`, `asyncio.open_connection("127.0.0.1", 22)`, два `asyncio.create_task` для двунаправленного проброса
- Binary frames только (`binary=True`)
- Graceful shutdown при закрытии любой стороны

### Шаг 2. `ssh-proxy-client.py` — клиент для ProxyCommand

Asyncio-клиент:
- `sys.argv[1]` и `sys.argv[2]` — игнорируем
- Читаем `KUBEFLOW_NOTEBOOK_URL` и `KUBEFLOW_SESSION_COOKIE`
- `websockets.connect()` с cookie header
- Два `asyncio.create_task`: stdin → ws, ws → stdout
- Binary mode

### Шаг 3. Dockerfile

Наследуем от `base`, ставим openssh-server и websockets.
Два s6-сервиса: sshd и websocket-proxy.

### Шаг 4. s6 services

- `01-setup-ssh` (cont-init): `ssh-keygen` если нет ключей
- `ssh-server/run`: `exec /usr/sbin/sshd -D` с config в memory
- `websocket-proxy/run`: `exec /opt/venv/bin/python /opt/ssh-proxy/server.py`

### Шаг 5. Makefile и Makefile.dev

Стандартный шаблон из `common.mk`, как в mcp-shell-server.
Makefile.dev: build image, run container, test.

### Шаг 6. Тесты

- pytest + testcontainers
- Build image → запустить контейнер
- Проверить health endpoint (plain HTTP)
- WebSocket-подключение → выполнить SSH-команду (через `paramiko` или `asyncssh` в тестах)
- Бинарная целостность данных
