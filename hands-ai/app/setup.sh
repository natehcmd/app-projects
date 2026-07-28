#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Installing Electron dependencies..."
npm install
echo "Launching Hands AI app..."
npm start
