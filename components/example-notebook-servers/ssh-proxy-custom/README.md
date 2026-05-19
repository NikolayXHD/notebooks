# ssh-proxy-custom

Расширенный SSH-прокси образ для продакшена. Добавляет поверх `ssh-proxy`: fish, micro, du-dust, lazygit, sudo/su без пароля, **CUDA 12.6 toolkit** (из официального NVIDIA репозитория), poetry, Yandex-зеркало apt, внутренний PyPI-индекс.

**Цепочка наследования:** `base` ← `ssh-proxy` ← `ssh-proxy-custom`

## Сборка

```bash
# только ssh-proxy-custom (ssh-proxy + base должны быть собраны заранее)
REGISTRY=ghcr.io/kubeflow/kubeflow/notebook-servers TAG=sha-xxxxx make docker-build

# ssh-proxy-custom + ssh-proxy + base
REGISTRY=my-registry TAG=my-tag make docker-build-dep
```

## Тестирование

```bash
# Интеграционные (testcontainers)
make test

# E2E (SSH + проверка установленных пакетов: fish, lazygit, dust, poetry и т.д.)
python tests/ssh_e2e_test.py
```

> **Важно:** после любых изменений в образе прогонять тесты.
