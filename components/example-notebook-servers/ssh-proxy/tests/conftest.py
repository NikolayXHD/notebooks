import os
import time
from pathlib import Path

import httpx
import pytest
import requests
from testcontainers.core.container import DockerContainer

TESTS_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = TESTS_DIR.parent
IMAGE_NAME = "ssh-proxy:test"
CONTAINER_NAME = "ssh-proxy-test-pytest"
AUTH_COOKIE = "test-session-token"


def _build_image():
    dockerfile = PROJECT_DIR / "Dockerfile"
    cmd = [
        "docker", "build",
        "-f", str(dockerfile),
        "--build-arg",
        f"BASE_IMG=ghcr.io/kubeflow/kubeflow/notebook-servers/base:sha-28140b7620a1b0f5e46c4c7dbddcda12148099dc-dirty",
        "--tag", str(IMAGE_NAME),
        str(PROJECT_DIR),
    ]
    result = os.system(" ".join(cmd))
    if result != 0:
        raise RuntimeError(f"Failed to build image (exit code {result})")


def _image_exists():
    result = os.popen(f"docker image inspect {IMAGE_NAME} 2>/dev/null").read().strip()
    return bool(result)


def _container_running():
    result = os.popen(
        f"docker inspect -f '{{{{.State.Running}}}}' {CONTAINER_NAME} 2>/dev/null"
    ).read().strip()
    return result == "true"


def _wait_for_health(base_url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base_url}/", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(0.5)
    return False


def _get_container_url(container):
    host = container.get_container_host_ip()
    port = container.get_exposed_port(8888)
    return f"http://{host}:{port}"


@pytest.fixture(scope="session")
def image():
    if not _image_exists():
        _build_image()
    yield IMAGE_NAME


@pytest.fixture(scope="session")
def container_info(image):
    if _container_running():
        os.system(f"docker stop {CONTAINER_NAME} >/dev/null 2>&1")
        os.system(f"docker rm {CONTAINER_NAME} >/dev/null 2>&1")

    c = DockerContainer(image, name=CONTAINER_NAME)
    c.with_exposed_ports(8888)
    c.with_env("NB_PREFIX", "/ssh-proxy/")
    c.start()

    base_url = _get_container_url(c)

    if not _wait_for_health(base_url):
        c.stop()
        raise RuntimeError(f"Server did not become ready within 30s")

    class Info:
        def __init__(self, base_url, name, container):
            self.base_url = base_url
            self.name = name
            self.container = container

        def refresh(self):
            self.base_url = _get_container_url(self.container)

    info = Info(base_url, CONTAINER_NAME, c)
    yield info

    c.stop()


@pytest.fixture()
def client(container_info):
    return httpx.Client(
        base_url=container_info.base_url,
        timeout=15,
        cookies={"authservice_session": AUTH_COOKIE},
    )


@pytest.fixture()
def unauthenticated_client(container_info):
    return httpx.Client(base_url=container_info.base_url, timeout=15)
