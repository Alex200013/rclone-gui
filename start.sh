#!/bin/bash
# RcloneGUI - Script de lancement
# Usage: ./start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Vérifier rclone
if ! command -v rclone &> /dev/null; then
    echo ""
    echo "⚠️  rclone n'est pas installé !"
    echo "Installez-le avec :"
    echo "  sudo apt install rclone"
    echo "  ou: curl https://rclone.org/install.sh | sudo bash"
    echo ""
fi

# Vérifier Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 requis !"
    exit 1
fi

# Créer le venv si pas encore fait
if [ ! -d ".venv" ]; then
    echo "🔧 Création de l'environnement virtuel..."
    python3 -m venv .venv

    # python3-venv pas installé ?
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Impossible de créer le venv."
        echo "   Installez python3-venv d'abord :"
        echo "   sudo apt install python3-venv python3-full"
        exit 1
    fi
fi

# Activer le venv
source .venv/bin/activate

# Installer Flask dans le venv si besoin
if ! python3 -c "import flask" &> /dev/null; then
    echo "📦 Installation de Flask dans le venv..."
    pip install flask --quiet
fi

# Ouvrir le navigateur après 1.5s
(sleep 1.5 && xdg-open http://localhost:7458 2>/dev/null || \
              open http://localhost:7458 2>/dev/null || \
              echo "→ Ouvrez manuellement: http://localhost:7458") &

echo ""
echo "╔══════════════════════════════════╗"
echo "║       RcloneGUI  démarré !       ║"
echo "║   → http://localhost:7458        ║"
echo "║   Ctrl+C pour arrêter            ║"
echo "╚══════════════════════════════════╝"
echo ""

python3 app.py
