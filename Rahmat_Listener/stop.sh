#!/bin/bash
set -e

# --- CONFIGURATION ---
SERVICE_NAME="Rahmat_Listener"

echo "🛑 $SERVICE_NAME servisini to'xtatish..."

# Service ni to'xtatish
sudo systemctl stop "$SERVICE_NAME"

echo "✅ Service to'xtatildi."

# Agar avtomatik ishga tushishini ham o‘chirmoqchi bo‘lsangiz
read -p "❓ Service ni boot vaqtida ham o‘chirishni xohlaysizmi? (y/n): " disable_service

if [ "$disable_service" = "y" ]; then
    sudo systemctl disable "$SERVICE_NAME"
    echo "🚫 Service disable qilindi."
fi

echo "✔️ Tugadi."