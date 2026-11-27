#!/usr/bin/env bash
# Instala (ou reinstala) o ambiente do projeto.
set -e
cd "$(dirname "$0")"

echo "==> Criando ambiente virtual (.venv)..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip

echo "==> Instalando PyTorch (CPU)..."
.venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo "==> Instalando demais dependências..."
.venv/bin/pip install -r requirements.txt

echo ""
echo "✅ Pronto! Execute ./abrir.sh para iniciar."
