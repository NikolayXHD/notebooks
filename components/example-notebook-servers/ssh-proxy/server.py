"""
WebSocket ↔ SSH proxy server for Kubeflow GPU pods.

Listens on port 8888, accepts WebSocket connections, and proxies them
to a local SSH daemon on 127.0.0.1:22.

Plain HTTP requests (no Upgrade header) return 200 OK for health checks.
All WebSocket data is transferred in binary mode to preserve SSH protocol integrity.
"""

import asyncio
import logging
import os
import signal

import websockets
from websockets.http11 import Response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ssh-proxy")

TARGET_SSH_HOST = os.environ.get("TARGET_SSH_HOST", "127.0.0.1")
TARGET_SSH_PORT = int(os.environ.get("TARGET_SSH_PORT", "22"))
PROXY_LISTEN_HOST = os.environ.get("PROXY_LISTEN_HOST", "0.0.0.0")
PROXY_LISTEN_PORT = int(os.environ.get("PROXY_LISTEN_PORT", "8888"))

logger.info(
    "Starting SSH proxy on %s:%s → %s:%s",
    PROXY_LISTEN_HOST, PROXY_LISTEN_PORT, TARGET_SSH_HOST, TARGET_SSH_PORT,
)


async def forward_from_ws(ws, writer):
    """Forward from WebSocket (recv) to TCP writer (write+drain)."""
    try:
        while True:
            data = await ws.recv()
            if not data:
                break
            if isinstance(data, str):
                data = data.encode()
            writer.write(data)
            await writer.drain()
    except (asyncio.CancelledError, Exception):
        pass


async def forward_from_tcp(reader, ws):
    """Forward from TCP reader (read) to WebSocket (send)."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            await ws.send(data)
    except (asyncio.CancelledError, Exception):
        pass


async def handle_connection(websocket):
    """Handle a single WebSocket connection by proxying to SSH."""
    peer = websocket.remote_address
    logger.info("WebSocket connection from %s", peer)

    # Open TCP connection to SSH daemon
    try:
        ssh_reader, ssh_writer = await asyncio.open_connection(TARGET_SSH_HOST, TARGET_SSH_PORT)
    except (ConnectionRefusedError, OSError) as exc:
        logger.error("Failed to connect to SSH daemon at %s:%s: %s", TARGET_SSH_HOST, TARGET_SSH_PORT, exc)
        await websocket.close(1013, f"SSH daemon unavailable: {exc}")
        return

    logger.info("TCP connected to %s:%s", TARGET_SSH_HOST, TARGET_SSH_PORT)

    # Two bidirectional forwarding tasks
    try:
        to_ssh = asyncio.create_task(forward_from_ws(websocket, ssh_writer))
        to_ws = asyncio.create_task(forward_from_tcp(ssh_reader, websocket))

        # Wait for either direction to complete
        done, pending = await asyncio.wait(
            [to_ssh, to_ws],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except Exception as exc:
        logger.error("Proxy error for %s: %s", peer, exc)
    finally:
        try:
            ssh_writer.close()
            await ssh_writer.wait_closed()
        except Exception:
            pass
        logger.info("Connection from %s closed", peer)


async def health_check(websocket, request):
    """
    Intercept plain HTTP requests (no WebSocket upgrade).
    Returns a Response object to short-circuit with a plain HTTP response.
    Returns None to let websockets proceed with WebSocket handshake.
    """
    from websockets.datastructures import Headers as WSHeaders

    upgrade = request.headers.get("upgrade", "").lower()
    if "websocket" in upgrade:
        return None

    logger.info("Plain HTTP request to %s - returning 200 OK", request.path)
    return Response(
        status_code=200,
        reason_phrase="OK",
        headers=WSHeaders([("Content-Type", "text/plain")]),
        body=b"SSH WebSocket Proxy - healthy\n",
    )


async def main():
    stop = asyncio.Future()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: not stop.done() and stop.set_result(None))

    async with websockets.serve(
        handle_connection,
        PROXY_LISTEN_HOST,
        PROXY_LISTEN_PORT,
        process_request=health_check,
        ping_interval=20,
        ping_timeout=20,
        max_size=2 ** 20,
        max_queue=64,
    ):
        logger.info("SSH proxy server started on %s:%s", PROXY_LISTEN_HOST, PROXY_LISTEN_PORT)
        await stop

    logger.info("SSH proxy server stopped")


if __name__ == "__main__":
    asyncio.run(main())
