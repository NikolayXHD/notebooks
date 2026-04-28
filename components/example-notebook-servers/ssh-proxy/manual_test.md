# Ручное тестирование: SSH через WebSocket-прокси

## Запуск контейнера

```bash
docker run -d \
  --name ssh-proxy-test \
  -p 8888:8888 \
  -e NB_PREFIX=/ssh-proxy/ \
  ssh-proxy:test
```

Проверка, что сервер запустился:

```bash
curl http://localhost:8888/
# Должно вернуть: SSH WebSocket Proxy - healthy
```

## Настройка SSH-клиента

Создайте временный файл `~/.ssh/config_ssh_proxy`:

```
Host gpu-kube
    HostName localhost
    User jovyan
    ProxyCommand python3 /path/to/ssh-proxy/ssh-proxy-client.py \
        -u 'ws://localhost:8888/?ssh=true' \
        -c 'any-cookie-value'
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
```

> **Важно:** `ProxyCommand` передаёт `%h %p` от SSH, но наш клиент их игнорирует — URL задаётся через `-u`.
> Кука может быть любой — сервер не проверяет её (аутентификация делегирована Istio).

## Подключение

```bash
ssh -F ~/.ssh/config_ssh_proxy gpu-kube
```

Если всё работает, вы увидите SSH-баннер и приглашение `jovyan@gpu-server` или ошибку аутентификации (если пароль не пустой).

## Выполнение команд

```bash
# Одна команда
ssh -F ~/.ssh/config_ssh_proxy gpu-kube "whoami"
# → jovyan

ssh -F ~/.ssh/config_ssh_proxy gpu-kube "echo hello"
# → hello

ssh -F ~/.ssh/config_ssh_proxy gpu-kube "ls -la /home/jovyan"
```

## SCP

```bash
scp -F ~/.ssh/config_ssh_proxy local_file.txt gpu-kube:/home/jovyan/
```

## Очистка

```bash
docker stop ssh-proxy-test && docker rm ssh-proxy-test
rm ~/.ssh/config_ssh_proxy
```

## Переменные окружения (альтернатива `-u` и `-c`)

Можно использовать env вместо аргументов командной строки:

```bash
# Вариант 1: env vars
export KUBEFLOW_NOTEBOOK_URL=http://localhost:8888
export KUBEFLOW_SESSION_COOKIE=any-value

# Тогда ProxyCommand проще:
# ProxyCommand python3 ssh-proxy-client.py %h %p
```

## Troubleshooting

- **Connection refused** — проверьте, что контейнер запущен: `docker ps | grep ssh-proxy`
- **Permission denied (password)** — проверьте, что в контейнере аккаунт `jovyan` разблокирован (`passwd -d jovyan`)
- **Connection timed out** — убедитесь, что порт 8888 проброшен корректно
- **Клиент падает без ошибки** — добавьте `SSH_PROXY_FORCE_EXIT=1` для принудительного закрытия WebSocket при завершении stdin
