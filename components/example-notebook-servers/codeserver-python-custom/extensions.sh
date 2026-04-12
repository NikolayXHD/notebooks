#!/bin/bash

set -e

EXTENSIONS_DIR="/opt/vscode-extensions"

# Collect all .vsix files
args=()
for vsix in "$EXTENSIONS_DIR"/*.vsix; do
    if [[ -f "$vsix" ]]; then
        args+=(--install-extension "$vsix")
    fi
done

if [[ ${#args[@]} -eq 0 ]]; then
    echo "No .vsix files found in $EXTENSIONS_DIR"
    exit 0
fi

# Install extensions
code-server "${args[@]}" --force && code-server --list-extensions --show-versions