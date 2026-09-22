#!/usr/bin/env bash
set -euo pipefail
if command -v pdftoppm >/dev/null && command -v tesseract >/dev/null && tesseract --list-langs 2>/dev/null | grep -qx spa && tesseract --list-langs 2>/dev/null | grep -qx eng; then
  exit 0
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng