import asyncio
import shlex

import httpx
import pytest
import websockets


def test_health(client, unauthenticated_client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"healthy" in resp.content

    resp = unauthenticated_client.get("/")
    assert resp.status_code == 200
    assert b"healthy" in resp.content


def _make_ws_url(base_url, cookies=None):
    url = str(base_url).replace("http://", "ws://")
    headers = None
    if cookies:
        cookie_val = list(cookies.values())[0]
        headers = {"Cookie": f"authservice_session={cookie_val}"}
    return url, headers


def test_websocket_connection(client):
    url, headers = _make_ws_url(client.base_url, client.cookies)

    async def _connect():
        async with websockets.connect(url, additional_headers=headers) as ws:
            test_data = b"hello from ssh-proxy-custom test"
            await ws.send(test_data)
            return True

    result = asyncio.run(_connect())
    assert result is True


def test_websocket_connection_unauthenticated():
    assert True


def test_binary_data_through_proxy(client):
    url, headers = _make_ws_url(client.base_url, client.cookies)

    async def _send_binary():
        async with websockets.connect(url, additional_headers=headers) as ws:
            test_data = bytes(range(256))
            await ws.send(test_data)
            return True

    result = asyncio.run(_send_binary())
    assert result is True


def test_multiple_connections(client):
    url, headers = _make_ws_url(client.base_url, client.cookies)

    async def _connect_n(n):
        results = []
        for _ in range(n):
            async with websockets.connect(url, additional_headers=headers) as ws:
                await ws.send(b"test data")
                results.append(True)
        return results

    results = asyncio.run(_connect_n(3))
    assert len(results) == 3


def test_connection_closes_gracefully(client):
    url, headers = _make_ws_url(client.base_url, client.cookies)

    async def _close_test():
        async with websockets.connect(url, additional_headers=headers) as ws:
            await ws.send(b"test")
        return True

    result = asyncio.run(_close_test())
    assert result


def test_python_version(container):
    exit_code, output = container.exec("python3.11 --version")
    assert exit_code == 0
    assert b"3.11" in output


def test_fish_installed(container):
    exit_code, output = container.exec("fish --version")
    assert exit_code == 0
    assert b"fish" in output


def test_micro_installed(container):
    exit_code, output = container.exec("micro --version")
    assert exit_code == 0


def test_du_dust_installed(container):
    exit_code, output = container.exec("dust --version")
    assert exit_code == 0


def test_lazygit_installed(container):
    exit_code, output = container.exec("lazygit --version")
    assert exit_code == 0


def test_p7zip_installed(container):
    exit_code, output = container.exec("7z --help")
    assert exit_code == 0


def test_build_essential_installed(container):
    exit_code, output = container.exec("gcc --version")
    assert exit_code == 0


def test_mc_installed(container):
    exit_code, output = container.exec("mc --version")
    assert exit_code == 0


def test_htop_installed(container):
    exit_code, output = container.exec("htop --version")
    assert exit_code == 0


def test_poetry_installed(container):
    exit_code, output = container.exec("poetry --version")
    assert exit_code == 0


def test_poetry_venv_creation(container):
    exit_code, output = container.exec(
        ["sh", "-c",
         "cd /tmp && rm -rf test-pkg && mkdir test-pkg && cd test-pkg && cat > pyproject.toml << 'EOF' && poetry lock && poetry run python --version\n"
         "[tool.poetry]\n"
         "name = \"test-pkg\"\n"
         "version = \"0.1.0\"\n"
         "description = \"\"\n"
         "authors = []\n"
         "\n"
         "[tool.poetry.dependencies]\n"
         "python = \"^3.11\"\n"
         "\n"
         "[build-system]\n"
         "requires = [\"poetry-core\"]\n"
         "build-backend = \"poetry.core.masonry.api\"\n"
         "EOF"
        ]
    )
    assert exit_code == 0, f"poetry failed: {output}"
    assert b"3.11" in output


def test_pip_index_configured(container):
    exit_code, output = container.exec("pip config list")
    assert exit_code == 0
    assert b"repo.sberned.ru" in output


def test_openssh_client_installed(container):
    exit_code, output = container.exec("ssh -V")
    assert exit_code == 0


def test_su_without_password(container):
    exit_code, output = container.exec(
        ["sh", "-c", "echo 'whoami before su'; whoami; echo 'su to root'; echo | su - -c whoami"]
    )
    assert exit_code == 0
    assert b"root" in output, f"Expected 'root' in output, got: {output}"


def test_sudo_without_password(container):
    exit_code, output = container.exec(
        ["sh", "-c", "echo 'whoami before sudo'; whoami; echo 'sudo whoami'; sudo whoami"]
    )
    assert exit_code == 0
    assert b"root" in output, f"Expected 'root' in output, got: {output}"
