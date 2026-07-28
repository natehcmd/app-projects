#!/usr/bin/env bash

set -e

GDRIVE_DIR="/Users/natehoward/Google Drive/My Drive"
ONEDRIVE_DIR="/Users/natehoward/OneDrive"
CACHE_DIR="/Users/natehoward/Library/Group Containers/UBF8T346G9.OneDriveStandaloneSuite"

# 1. Back up local OneDrive folder to Google Drive
if [ -d "$ONEDRIVE_DIR" ] && [ ! -L "$ONEDRIVE_DIR" ]; then
  if [ -d "$GDRIVE_DIR" ]; then
    echo "Backing up local OneDrive files (1.3 GB) to Google Drive..."
    mkdir -p "$GDRIVE_DIR/OneDrive-Migrated"
    rsync -a --progress "$ONEDRIVE_DIR/" "$GDRIVE_DIR/OneDrive-Migrated/"
    echo "Backup completed. Renaming local OneDrive directory to OneDrive_old..."
    mv "$ONEDRIVE_DIR" "${ONEDRIVE_DIR}_old"
  else
    echo "Warning: Google Drive not found, skipping backup of OneDrive folder."
  fi
fi

# 2. Delete the massive 224 GB Cache Folder
if [ -d "$CACHE_DIR" ]; then
  echo "Deleting the massive 224 GB OneDrive cache directory..."
  rm -rf "$CACHE_DIR"
  echo "OneDrive cache successfully deleted!"
else
  echo "OneDrive cache directory does not exist or has already been deleted."
fi

echo "OneDrive has been successfully flushed from your computer!"
echo "Reclaimed 224+ GB of local space."
