#!/bin/bash


SCRIPT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

pushd "$SCRIPT_DIR" || exit 1
docker compose ps
popd || exit 1


