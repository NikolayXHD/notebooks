# AGENTS.md

> **Правило сборки:** Использовать только штатные механизмы репозитория (`make docker-build-dep` / `make docker-build`). Избегать ручного `docker build` без необходимости.
>
> **Перед выполнением задачи — прочитать `Makefile.dev`** соответствующего образа, чтобы знать доступные target-ы.
>
> **Сборка тестовых образов:** `make test-build` — таргет сам задаёт `REGISTRY=local TAG=test`, не дублировать на CLI.

**Направление последней работы:**

- [`ssh-proxy`](components/example-notebook-servers/ssh-proxy/README.md) — базовый SSH-прокси образ
- [`ssh-proxy-custom`](components/example-notebook-servers/ssh-proxy-custom/README.md) — расширенный SSH-прокси образ с CUDA 12.6
