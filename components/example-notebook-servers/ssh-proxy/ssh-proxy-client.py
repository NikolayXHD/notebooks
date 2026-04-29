#!/usr/bin/env python3
"""
SSH client proxy for Kubeflow GPU pods.

Used as a ProxyCommand for SSH:
    Host kubeflow.*
        User jovyan
        ProxyCommand ~/.kubeflow-proxy/run %n

Reads config from config.yaml next to the script.
"""

import argparse
import asyncio
import os
import signal
import sys

import websockets


def _find_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "config.yaml")
    if os.path.isfile(path):
        return path
    return None


def _load_config(config_path):
    import yaml
    with open(config_path) as f:
        return yaml.safe_load(f)


def _resolve_notebook_name(cli_name, host_arg, config):
    if cli_name:
        return cli_name
    name = _extract_notebook_name_from_host(host_arg)
    if name:
        return name
    return config.get("default_name", "")


def _extract_notebook_name_from_host(host):
    if not host or "." not in host:
        return None
    return host.strip().split(".", 1)[1]


def _extract_authservice_session(source):
    for part in source.split(";"):
        part = part.strip()
        if part.startswith("authservice_session="):
            return part.split("=", 1)[1]
    return None


def _load_cookie(config):
    cookie = config.get("cookie")
    if cookie:
        cookie = cookie.strip()
        if ";" in cookie:
            value = _extract_authservice_session(cookie)
            if value:
                return value
        if cookie.startswith("authservice_session="):
            cookie = cookie.split("=", 1)[1]
        return cookie

    cookie_file = config.get("cookie_file")
    if cookie_file:
        expanded = os.path.expanduser(cookie_file)
        if os.path.isfile(expanded):
            with open(expanded) as f:
                content = f.read().strip()
            if ";" in content:
                return _extract_authservice_session(content)
            if content.startswith("authservice_session="):
                return content.split("=", 1)[1]
            return content
    return None


def _build_url(config, notebook_name):
    url_template = config.get("url_template", "")
    if not url_template:
        print("[ssh-proxy] error: url_template is not set in config", file=sys.stderr, flush=True)
        sys.exit(1)

    url = url_template.replace("{name}", notebook_name)

    if url.startswith("https://"):
        url = "wss://" + url[8:]
    elif url.startswith("http://"):
        url = "ws://" + url[7:]
    elif not url.startswith(("ws://", "wss://")):
        url = "wss://" + url

    if not url.endswith("/"):
        url += "/"
    url += "?ssh=true"
    return url


async def stdin_to_ws(ws, force_exit=False):
    loop = asyncio.get_running_loop()
    try:
        while True:
            data = await loop.run_in_executor(None, os.read, 0, 65536)
            if not data:
                break
            await ws.send(data)
    except (asyncio.CancelledError, Exception):
        pass
    if force_exit:
        await ws.close()


async def ws_to_stdout(ws):
    try:
        while True:
            data = await ws.recv()
            if isinstance(data, str):
                data = data.encode()
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
    except (asyncio.CancelledError, Exception):
        pass


async def main():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    parser = argparse.ArgumentParser(description="SSH WebSocket proxy client")
    parser.add_argument("-n", "--notebook-name", help="Notebook name (overrides default_name in config)")
    parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)
    parsed = parser.parse_args()

    config_path = _find_config()
    if not config_path:
        print("[ssh-proxy] error: config.yaml not found next to the script", file=sys.stderr, flush=True)
        sys.exit(1)

    config = _load_config(config_path)

    host_arg = parsed.args[0] if parsed.args else None
    notebook_name = _resolve_notebook_name(parsed.notebook_name, host_arg, config)
    if not notebook_name:
        print("[ssh-proxy] error: no notebook name provided and no default_name in config", file=sys.stderr, flush=True)
        sys.exit(1)

    url = _build_url(config, notebook_name)
    cookie = _load_cookie(config)

    extra_headers = None
    if cookie:
        extra_headers = {"Cookie": f"authservice_session={cookie}"}
        print(f"[ssh-proxy] Connecting to {url}", file=sys.stderr, flush=True)
    else:
        print(f"[ssh-proxy] Connecting to {url} (no auth cookie)", file=sys.stderr, flush=True)

    try:
        async with websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 ** 20,
        ) as ws:
            print("[ssh-proxy] WebSocket connected, starting proxy", file=sys.stderr, flush=True)

            stdin_task = asyncio.create_task(
                stdin_to_ws(ws, force_exit=os.environ.get("SSH_PROXY_FORCE_EXIT") == "1")
            )
            stdout_task = asyncio.create_task(ws_to_stdout(ws))

            await stop.wait()

            stdin_task.cancel()
            stdout_task.cancel()
            for t in (stdin_task, stdout_task):
                try:
                    await t
                except asyncio.CancelledError:
                    pass

            await ws.close()
    except Exception as exc:
        print(f"[ssh-proxy] Error: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
