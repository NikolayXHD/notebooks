# ssh-proxy

Базовый SSH-прокси образ. Поднимает OpenSSH server (на 127.0.0.1:22) и WebSocket-прокси (на 0.0.0.0:8888) на Python 3.11. Позволяет подключаться к поду через `ssh` по WebSocket.

**Цепочка наследования:** `base` ← `ssh-proxy`

## Сборка

```bash
# только ssh-proxy (base должен быть собран заранее)
REGISTRY=ghcr.io/kubeflow/kubeflow/notebook-servers TAG=sha-xxxxx make docker-build

# ssh-proxy + base
REGISTRY=my-registry TAG=my-tag make docker-build-dep
```

## Тестирование

```bash
# Интеграционные (testcontainers — собирает образ, стартует контейнер, проверяет health/ws/ssh)
make test

# E2E (реальный SSH-клиент через WebSocket-прокси в контейнере)
python tests/ssh_e2e_test.py
```

> **Важно:** после любых изменений в образе прогонять тесты.
