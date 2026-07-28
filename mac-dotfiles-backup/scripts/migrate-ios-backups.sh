#!/usr/bin/env bash

set -e

SOURCE_DIR="/Users/natehoward/Library/Application Support/MobileSync/Backup"
GDRIVE_DIR="/Users/natehoward/Google Drive/My Drive"
DEST_DIR="$GDRIVE_DIR/Mac-iOS-Backups"

# Check if Google Drive is mounted
if [ ! -d "$GDRIVE_DIR" ]; then
  echo "Error: Google Drive is not mounted or path not found at: $GDRIVE_DIR"
  exit 1
fi

if [ -L "$SOURCE_DIR" ]; then
  echo "Error: $SOURCE_DIR is already a symlink."
  exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: $SOURCE_DIR does not exist."
  exit 1
fi

echo "Starting migration of iOS Backups (158 GB)..."
echo "Copying files to Google Drive (this may take a while, please wait)..."
mkdir -p "$DEST_DIR"

# Perform copy using rsync (safe, resumable)
rsync -a --progress "$SOURCE_DIR/" "$DEST_DIR/"

echo "Copy completed successfully! Creating symlink..."
# Rename original to old backup safety buffer
mv "$SOURCE_DIR" "${SOURCE_DIR}_old"

# Link it
ln -s "$DEST_DIR" "$SOURCE_DIR"

echo "------------------------------------------------"
echo "Migration completed successfully!"
echo "Please verify everything works, then you can delete the local old backups to free up 158 GB:"
echo "rm -rf \"${SOURCE_DIR}_old\""
