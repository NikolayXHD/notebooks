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
SSH_PROXY_DIR = PROJECT_DIR.parent / "ssh-proxy"
IMAGE_NAME = "ssh-proxy-custom:test"
SSH_PROXY_IMAGE = "ssh-proxy:test-base"
CONTAINER_NAME = "ssh-proxy-custom-test-e2e"
AUTH_COOKIE = "test-session-token"
CLIENT_SCRIPT = SSH_PROXY_DIR / "ssh-proxy-client.py"


def _build_ssh_proxy_base():
    dockerfile = SSH_PROXY_DIR / "Dockerfile"
    base_img = os.environ.get(
        "TEST_BASE_IMAGE",
        "ghcr.io/kubeflow/kubeflow/notebook-servers/base:sha-28140b7620a1b0f5e46c4c7dbddcda12148099dc-dirty",
    )
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "--build-arg", f"BASE_IMG={base_img}",
        "--tag", str(SSH_PROXY_IMAGE),
        str(SSH_PROXY_DIR),
    ]
    print(f"  Building ssh-proxy base image...")
    result = os.system(" ".join(cmd))
    if result != 0:
        raise RuntimeError(f"Failed to build ssh-proxy base image (exit code {result})")


def _build_image():
    if not _image_exists(SSH_PROXY_IMAGE):
        _build_ssh_proxy_base()

    dockerfile = PROJECT_DIR / "Dockerfile"
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "--build-arg", f"BASE_IMG={SSH_PROXY_IMAGE}",
        "--tag", str(IMAGE_NAME),
        str(PROJECT_DIR),
    ]
    print(f"  Building ssh-proxy-custom image...")
    result = os.system(" ".join(cmd))
    if result != 0:
        raise RuntimeError(f"Failed to build image (exit code {result})")


def _image_exists(name):
    result = os.popen(f"docker image inspect {name} 2>/dev/null").read().strip()
    return bool(result)


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


def _start_container():
    if _container_running():
        print(f"  Stopping existing container {CONTAINER_NAME}")
        os.system(f"docker stop {CONTAINER_NAME} >/dev/null 2>&1")
        os.system(f"docker rm {CONTAINER_NAME} >/dev/null 2>&1")

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

    port_result = subprocess.run(
        ["docker", "port", CONTAINER_NAME, "8888"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    port_line = port_result.stdout.strip()
    if not port_line:
        raise RuntimeError("No port mapping found")
    host_port = port_line.split(":")[-1]

    base_url = _get_container_url("127.0.0.1", host_port)
    if not _wait_for_health(base_url):
        _stop_container()
        raise RuntimeError(f"Server did not become ready within 30s")

    return container_id, base_url


def _stop_container():
    os.system(f"docker stop {CONTAINER_NAME} >/dev/null 2>&1")
    os.system(f"docker rm {CONTAINER_NAME} >/dev/null 2>&1")


def _create_ssh_config(proxy_cmd, ssh_dir):
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
    ws_base = base_url.replace("http://", "ws://")

    with tempfile.TemporaryDirectory() as tmpdir:
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
    print("E2E Test: SSH through WebSocket proxy (ssh-proxy-custom)")
    print("=" * 60)

    print("\n1. Building Docker image...")
    _build_image()

    print("\n2. Starting test container...")
    container_id, base_url = _start_container()
    print(f"   Container: {container_id[:12]}")
    print(f"   URL: {base_url}")

    try:
        print("\n3. Running 'echo hello' via SSH...")
        returncode, stdout, stderr = run_ssh_test(base_url, "echo hello")

        print(f"   Exit code: {returncode}")
        print(f"   STDOUT: {stdout.decode()!r}")
        if stderr:
            print(f"   STDERR: {stderr.decode()!r}")

        assert returncode == 0, f"SSH exited with code {returncode}"
        assert stdout.decode().strip() == "hello", f"Expected 'hello', got {stdout.decode()!r}"
        print("\n   ✓ Command 'echo hello' → 'hello'")

        print("\n4. Running 'whoami' via SSH...")
        returncode, stdout, stderr = run_ssh_test(base_url, "whoami")
        print(f"   STDOUT: {stdout.decode()!r}")
        assert returncode == 0
        assert stdout.decode().strip() == "jovyan", f"Expected 'jovyan', got {stdout.decode()!r}"
        print("   ✓ Command 'whoami' → 'jovyan'")

        print("\n5. Verifying custom packages via SSH...")
        returncode, stdout, stderr = run_ssh_test(base_url, "fish --version")
        assert returncode == 0
        assert b"fish" in stdout
        print("   ✓ fish installed")

        returncode, stdout, stderr = run_ssh_test(base_url, "lazygit --version")
        assert returncode == 0
        print("   ✓ lazygit installed")

        returncode, stdout, stderr = run_ssh_test(base_url, "dust --version")
        assert returncode == 0
        print("   ✓ dust installed")

        returncode, stdout, stderr = run_ssh_test(base_url, "poetry --version")
        assert returncode == 0
        print("   ✓ poetry installed")

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
