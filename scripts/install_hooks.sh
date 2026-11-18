#!/bin/sh
# Installe les hooks versionnes du depot dans .git/hooks.
# A lancer une fois par clone : bash scripts/install_hooks.sh
set -e
cd "$(dirname "$0")/.."
mkdir -p .git/hooks
cp scripts/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
echo "[+] Hook pre-commit installe : les CSS minifies sont"
echo "    regeneres automatiquement a chaque commit CSS."
