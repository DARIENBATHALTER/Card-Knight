#!/usr/bin/env bash
# Build a self-contained CardKnight package for Steam Deck (Linux x86_64).
# Run this ON THE STEAM DECK (or any Linux x86_64 machine).
#
# One-time bootstrap (only needed the first time):
#   curl -sS https://bootstrap.pypa.io/get-pip.py | python3 - --user
#   python3 -m pip install pyinstaller pygame --user
#
# Then just run:
#   bash build_deck.sh
#
# Output: dist/CardKnight/   ← copy this whole folder anywhere and run ./CardKnight

set -e
cd "$(dirname "$0")"

echo "Building CardKnight for Steam Deck..."
python3 -m PyInstaller --clean CardKnight.spec

echo ""
echo "Done!  Package is at: dist/CardKnight/"
echo "To run: dist/CardKnight/CardKnight"
