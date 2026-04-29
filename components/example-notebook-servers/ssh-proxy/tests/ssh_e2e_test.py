"""
E2E test: real SSH client → WebSocket proxy → sshd in Docker container.

Usage (standalone):
    python tests/ssh_e2e_test.py

Usage (pytest):
    pytest tests/ssh_e2e_test.py -v -s
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time


PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
IMAGE_NAME = "ssh-proxy:test"
CONTAINER_NAME = "ssh-proxy-test-e2e"
AUTH_COOKIE = "test-session-token"
CLIENT_SCRIPT = PROJECT_DIR / "ssh-proxy-client.py"


def _build_image():
    dockerfile = PROJECT_DIR / "Dockerfile"
    base_img = os.environ.get(
        "TEST_BASE_IMAGE",
        "ghcr.io/kubeflow/kubeflow/notebook-servers/base:sha-28140b7620a1b0f5e46c4c7dbddcda12148099dc-dirty",
    )
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "--build-arg", f"BASE_IMG={base_img}",
        "--tag", str(IMAGE_NAME),
        str(PROJECT_DIR),
    ]
    print(f"  Building image...")
    result = os.system(" ".join(cmd))
    if result != 0:
        raise RuntimeError(f"Failed to build image (exit code {result})")


def _container_running():
    result = os.popen(
        f"docker inspect -f '{{{{.State.Running}}}}' {CONTAINER_NAME} 2>/dev/null"
    ).read().strip()
    return result == "true"


def _wait_for_health(base_url, timeout=30):
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(0.5)
    return False


def _get_container_url(host, port):
    return f"http://{host}:{port}"


def _start_container(base_image=None):
    if _container_running():
        print(f"  Stopping existing container {CONTAINER_NAME}")
        os.system(f"docker stop {CONTAINER_NAME} >/dev/null 2>&1")
        os.system(f"docker rm {CONTAINER_NAME} >/dev/null 2>&1")

    base_img = base_image or os.environ.get(
        "TEST_BASE_IMAGE",
        "ghcr.io/kubeflow/kubeflow/notebook-servers/base:sha-28140b7620a1b0f5e46c4c7dbddcda12148099dc-dirty",
    )

    import subprocess
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", CONTAINER_NAME,
            "-p", "0:8888",
            "-e", "NB_PREFIX=/ssh-proxy/",
            IMAGE_NAME,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"docker run failed: {result.stderr}")

    container_id = result.stdout.strip()

    # Get exposed port
    port_result = subprocess.run(
        ["docker", "port", CONTAINER_NAME, "8888"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    port_line = port_result.stdout.strip()
    if not port_line:
        raise RuntimeError("No port mapping found")
    # Format: 0.0.0.0:XXXXX
    host_port = port_line.split(":")[-1]

    base_url = _get_container_url("127.0.0.1", host_port)
    if not _wait_for_health(base_url):
        _stop_container()
        raise RuntimeError(f"Server did not become ready within 30s")

    return container_id, base_url


def _stop_container():
    os.system(f"docker stop {CONTAINER_NAME} >/dev/null 2>&1")
    os.system(f"docker rm {CONTAINER_NAME} >/dev/null 2>&1")


def _get_ssh_banner(base_url):
    """Connect via WebSocket and read the SSH banner from sshd."""
    import asyncio
    import websockets

    async def _fetch():
        url = str(base_url).replace("http://", "ws://")
        headers = {"Cookie": f"authservice_session={AUTH_COOKIE}"}
        async with websockets.connect(url, additional_headers=headers) as ws:
            data = await asyncio.wait_for(ws.recv(), timeout=10)
            if isinstance(data, str):
                data = data.encode()
            return data.decode().strip()

    return asyncio.run(_fetch())


def _create_ssh_config(proxy_cmd, ssh_dir):
    """Create a temporary SSH config file."""
    config_content = f"""
Host our-image
    HostName localhost
    User jovyan
    ProxyCommand {proxy_cmd}
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR
"""
    config_path = ssh_dir / "config"
    config_path.write_text(config_content)
    config_path.chmod(0o600)
    return config_path


def run_ssh_test(base_url, command="echo hello", timeout=30):
    """
    Run a real SSH command through the WebSocket proxy.
    Returns (returncode, stdout, stderr).
    """
    import pathlib

    ws_base = base_url.replace("http://", "ws://")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Prepare proxy script + config in a temp directory
        proxy_dir = pathlib.Path(tmpdir) / "kubeflow-proxy"
        proxy_dir.mkdir()
        shutil.copy(CLIENT_SCRIPT, proxy_dir / "ssh-proxy-client.py")
        (proxy_dir / "config.yaml").write_text(
            f"url_template: {ws_base}/{{name}}/\n"
            f"default_name: ssh-test\n"
            f"cookie: {AUTH_COOKIE}\n"
        )

        proxy_cmd = f"{sys.executable} {proxy_dir}/ssh-proxy-client.py"

        ssh_dir = pathlib.Path(tmpdir) / ".ssh"
        ssh_dir.mkdir()
        config_path = _create_ssh_config(proxy_cmd, ssh_dir)

        env = os.environ.copy()

        cmd = [
            "ssh",
            "-F", str(config_path),
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            "our-image",
            command,
        ]

        print(f"  Command: {' '.join(cmd)}")
        print(f"  ProxyCommand: {proxy_cmd}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr


def test_ssh_e2e():
    """End-to-end test: SSH client → WebSocket proxy → sshd in Docker → command execution."""
    print("\n" + "=" * 60)
    print("E2E Test: SSH through WebSocket proxy")
    print("=" * 60)

    # Build image
    print("\n1. Building Docker image...")
    _build_image()

    # Start container
    print("\n2. Starting test container...")
    container_id, base_url = _start_container()
    print(f"   Container: {container_id[:12]}")
    print(f"   URL: {base_url}")

    try:
        # Run SSH command
        print("\n4. Running 'echo hello' via SSH...")
        returncode, stdout, stderr = run_ssh_test(base_url, "echo hello")

        print(f"   Exit code: {returncode}")
        print(f"   STDOUT: {stdout.decode()!r}")
        if stderr:
            print(f"   STDERR: {stderr.decode()!r}")

        # Verify
        assert returncode == 0, f"SSH exited with code {returncode}"
        assert stdout.decode().strip() == "hello", f"Expected 'hello', got {stdout.decode()!r}"
        print("\n   ✓ Command 'echo hello' → 'hello'")

        # Run another command to be more thorough
        print("\n5. Running 'whoami' via SSH...")
        returncode, stdout, stderr = run_ssh_test(base_url, "whoami")
        print(f"   STDOUT: {stdout.decode()!r}")
        assert returncode == 0
        assert stdout.decode().strip() == "jovyan", f"Expected 'jovyan', got {stdout.decode()!r}"
        print("   ✓ Command 'whoami' → 'jovyan'")

        print("\n" + "=" * 60)
        print("E2E test PASSED!")
        print("=" * 60)

    finally:
        if os.environ.get("SKIP_CLEANUP"):
            print(f"\nSkipping cleanup (container: {CONTAINER_NAME})")
        else:
            print("\nCleaning up...")
            _stop_container()


if __name__ == "__main__":
    try:
        test_ssh_e2e()
    except Exception as e:
        print(f"\n✗ E2E test FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
