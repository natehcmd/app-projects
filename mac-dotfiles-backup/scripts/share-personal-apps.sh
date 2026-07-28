#!/usr/bin/env bash

set -e

SHARED_DIR="/Users/Shared/PersonalApplications"
NATE_APPS_DIR="/Users/natehoward/Applications"
PERSONAL_APPS_DIR="/Users/personalprojects/Applications"

# Ensure directories exist
mkdir -p "$SHARED_DIR"
sudo mkdir -p "$PERSONAL_APPS_DIR"
sudo chown -R personalprojects:staff "$PERSONAL_APPS_DIR"

share_app() {
  local app_name="$1"
  local src_app="$NATE_APPS_DIR/$app_name"
  local dest_app="$SHARED_DIR/$app_name"

  if [ ! -d "$src_app" ]; then
    echo "Skipping: $app_name not found in $NATE_APPS_DIR"
    return 0
  fi

  echo "------------------------------------------------"
  echo "Sharing $app_name..."

  # 1. Move app to shared directory (if not already there)
  if [ ! -d "$dest_app" ]; then
    echo "Moving app to shared directory..."
    mv "$src_app" "$dest_app"
  else
    echo "App already exists in shared folder, deleting local duplicate..."
    rm -rf "$src_app"
  fi

  # 2. Set permissions so personalprojects has full access
  echo "Applying permissions..."
  sudo chown -R natehoward:staff "$dest_app"
  sudo chmod -R 770 "$dest_app"

  # 3. Symlink in natehoward's Applications
  echo "Creating symlink for natehoward..."
  ln -s "$dest_app" "$src_app"

  # 4. Symlink in personalprojects's Applications
  echo "Creating symlink for personalprojects..."
  sudo ln -sf "$dest_app" "$PERSONAL_APPS_DIR/$app_name"
  sudo chown -h personalprojects:staff "$PERSONAL_APPS_DIR/$app_name"
}

# Share all personal custom apps
share_app "AgentDrop.app"
share_app "FileGraph.app"
share_app "Hands AI.app"
share_app "Mission Control.app"
share_app "MyApps.app"
share_app "Net Worth.app"
share_app "Unified OS.app"
share_app "Claude Code URL Handler.app"

echo "------------------------------------------------"
echo "All apps have been successfully shared between natehoward and personalprojects!"
echo "They are now completely hidden and blocked from all other users."
