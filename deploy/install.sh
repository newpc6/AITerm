#!/bin/bash

set -e

echo "========================================"
echo "AITerm Installation Script"
echo "========================================"
echo ""

CONDA_ENV_NAME="aiterm"
INSTALL_DIR="/path/to/aiterm"

read -p "Enter installation directory [default: /opt/aiterm]: " custom_dir
if [ -n "$custom_dir" ]; then
    INSTALL_DIR="$custom_dir"
fi

read -p "Enter conda environment name [default: aiterm]: " custom_env
if [ -n "$custom_env" ]; then
    CONDA_ENV_NAME="$custom_env"
fi

echo ""
echo "Installation settings:"
echo "  - Directory: $INSTALL_DIR"
echo "  - Conda env: $CONDA_ENV_NAME"
echo ""

read -p "Continue? [y/N]: " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo "[1/5] Creating conda environment..."
if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    echo "Environment '$CONDA_ENV_NAME' already exists. Skipping..."
else
    conda create -n $CONDA_ENV_NAME python=3.10 -y
fi

echo ""
echo "[2/5] Activating environment..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $CONDA_ENV_NAME

echo ""
echo "[3/5] Installing dependencies..."
pip install -r backend/requirements.txt

echo ""
echo "[4/5] Copying configuration..."
if [ ! -f "backend/configs/app.json" ]; then
    cp backend/configs/app.json.bak backend/configs/app.json
    echo "Configuration file created. Please edit backend/configs/app.json with your settings."
fi

echo ""
echo "[5/5] Initializing database..."
python init_scripts/init_all.py

echo ""
echo "========================================"
echo "Installation completed!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit backend/configs/app.json with your database and LLM settings"
echo "2. Run: python main.py"
echo ""
echo "To install as systemd service:"
echo "  sudo cp deploy/aiterm.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable aiterm"
echo "  sudo systemctl start aiterm"
echo ""
