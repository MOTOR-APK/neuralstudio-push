#!/usr/bin/env bash
# Abre o NeuralStudio (gerador de imagens local) no navegador.
cd "$(dirname "$0")" || exit 1
exec .venv/bin/python servidor.py
