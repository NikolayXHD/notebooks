#!/usr/bin/env python3
"""
SSH client proxy for Kubeflow GPU pods.

Used as a ProxyCommand for SSH:
    uv run ssh-proxy-client.py %h %p

Reads KUBEFLOW_NOTEBOOK_URL and KUBEFLOW_SESSION_COOKIE from environment.
Forwards stdin ↔ WebSocket ↔ stdout in binary mode.
"""

import argparse
import asyncio
import os
import signal
import sys

import websockets

_NOTEBOOK_URL = os.environ.get("KUBEFLOW_NOTEBOOK_URL", "")
_COOKIE_SOURCE = os.environ.get("KUBEFLOW_SESSION_COOKIE", "")


def _parse_args():
    parser = argparse.ArgumentParser(description="SSH WebSocket proxy client")
    parser.add_argument("-u", "--url", help="WebSocket URL (overrides KUBEFLOW_NOTEBOOK_URL)")
    parser.add_argument("-c", "--cookie", help="Auth cookie value (overrides KUBEFLOW_SESSION_COOKIE)")
    parser.add_argument("host", nargs="?", help="SSH host (ignored, for ProxyCommand compatibility)")
    parser.add_argument("port", nargs="?", help="SSH port (ignored, for ProxyCommand compatibility)")
    return parser.parse_args()


def _extract_authservice_session(source):
    """Extract authservice_session value from a multi-cookie string."""
    for part in source.split(";"):
        part = part.strip()
        if part.startswith("authservice_session="):
            print(
                "[ssh-proxy] cookie: extracted authservice_session from multi-cookie string",
                file=sys.stderr, flush=True,
            )
            return part.split("=", 1)[1]
    return None


def _load_cookie(cookie_source=None):
    """
    Return the authservice_session cookie value.

    Accepts:
      - multi-cookie string: ``apt.uid=...; authservice_session=VALUE; dtCookie=...``
      - key=value pair:     ``authservice_session=VALUE``
      - file path:          ``~/.kubeflow_cookie``
      - raw value:          ``VALUE``
    """
    source = cookie_source or _COOKIE_SOURCE
    if not source:
        return None

    # 1. Multi-cookie string (contains ;)
    if ";" in source:
        value = _extract_authservice_session(source)
        if value:
            return value
        print(
            "[ssh-proxy] error: 'authservice_session' not found in cookie string",
            file=sys.stderr, flush=True,
        )
        sys.exit(1)

    # 2. key=value pair
    if source.startswith("authservice_session="):
        print(
            "[ssh-proxy] cookie: extracted authservice_session from key=value pair",
            file=sys.stderr, flush=True,
        )
        return source.split("=", 1)[1]

    # 3. File path
    expanded = os.path.expanduser(source)
    if os.path.isfile(expanded):
        print(
            f"[ssh-proxy] cookie: read from file {expanded}",
            file=sys.stderr, flush=True,
        )
        with open(expanded, "r") as f:
            content = f.read().strip()
        # File content may be a multi-cookie string itself
        if ";" in content:
            return _extract_authservice_session(content)
        if content.startswith("authservice_session="):
            return content.split("=", 1)[1]
        return content

    # 4. Raw value
    print(
        "[ssh-proxy] cookie: using raw value",
        file=sys.stderr, flush=True,
    )
    return source


def _build_wss_url(env_url=None):
    """Convert URL to a WebSocket URL."""
    url = env_url or _NOTEBOOK_URL
    if not url:
        raise RuntimeError("KUBEFLOW_NOTEBOOK_URL is not set")

    # If already a WebSocket URL, just append query param
    if url.startswith(("ws://", "wss://")):
        if not url.endswith("/"):
            url = url + "/"
        url = url + "?ssh=true"
        return url

    # Convert HTTP(S) to WS(S)
    if url.startswith("https://"):
        url = "wss://" + url[8:]
    elif url.startswith("http://"):
        url = "ws://" + url[7:]
    elif not url.startswith(("ws://", "wss://")):
        url = "wss://" + url

    if not url.endswith("/"):
        url = url + "/"
    url = url + "?ssh=true"
    return url


async def stdin_to_ws(ws, force_exit=False):
    """Read from stdin (fd 0) and send as binary WebSocket frames."""
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
    """Receive binary WebSocket frames and write to stdout."""
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

    args = _parse_args()
    url = _build_wss_url(args.url)
    cookie = _load_cookie(args.cookie)

    extra_headers = None
    if cookie:
        extra_headers = {"Cookie": f"authservice_session={cookie}"}
        print(f"[ssh-proxy] Connecting to {url}", file=sys.stderr, flush=True)
    else:
        print(
            f"[ssh-proxy] Connecting to {url} (no auth cookie)",
            file=sys.stderr, flush=True,
        )

    try:
        async with websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=2 ** 20,
        ) as ws:
            print(
                "[ssh-proxy] WebSocket connected, starting proxy",
                file=sys.stderr, flush=True,
            )

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
