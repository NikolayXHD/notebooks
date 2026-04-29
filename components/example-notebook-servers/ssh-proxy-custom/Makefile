#
# This Makefile is templated, the following targets are provided:
#  - Current Architecture:
#     - docker-build:     build the docker image
#     - docker-build-dep: build the docker image (and any base images)
#     - docker-push:      push the docker image
#     - docker-push-dep:  push the docker image (and any base images)
#  - Multi-Architecture:
#     - docker-build-multi-arch:          build the docker image
#     - docker-build-multi-arch-dep:      build the docker image (and any base images)
#     - docker-build-push-multi-arch:     build AND push the docker image
#     - docker-build-push-multi-arch-dep: build AND push the docker image (and any base images)
#

GIT_COMMIT     := $(shell git rev-parse HEAD)
GIT_TREE_STATE := $(shell test -n "`git status --porcelain`" && echo "-dirty" || echo "")

REGISTRY ?= ghcr.io/kubeflow/kubeflow/notebook-servers
TAG      ?= sha-$(GIT_COMMIT)$(GIT_TREE_STATE)

IMAGE_NAME := ssh-proxy-custom

BASE_IMAGE         := $(REGISTRY)/ssh-proxy:$(TAG)
BASE_IMAGE_FOLDERS := ssh-proxy

CACHE_IMAGE ?= ghcr.io/kubeflow/kubeflow/notebook-servers/build-cache
CACHE_TAG   ?= $(IMAGE_NAME)

ARCH ?= linux/amd64

include ../common.mk
