#!/usr/bin/env bash

set -e

GDRIVE_DIR="/Users/natehoward/Google Drive/My Drive"

# Check if Google Drive is mounted
if [ ! -d "$GDRIVE_DIR" ]; then
  echo "Error: Google Drive is not mounted or path not found at: $GDRIVE_DIR"
  exit 1
fi

migrate_contents_only() {
  local src="$1"
  local dest_name="$2"
  local dest="$GDRIVE_DIR/$dest_name"

  echo "------------------------------------------------"
  echo "Processing contents of system folder: $src -> $dest"

  if [ ! -d "$src" ]; then
    echo "Skipping: $src is not a directory or does not exist."
    return 0
  fi

  # 1. Copy contents to Google Drive
  echo "Copying files to Google Drive..."
  mkdir -p "$dest"
  rsync -a --progress --exclude=".localized" "$src/" "$dest/"

  # 2. Iterate over each item in the directory
  echo "Migrating individual directories and files..."
  
  # Enable dotglob to match hidden files (excluding . and ..)
  shopt -s dotglob
  for item in "$src"/*; do
    # Skip if no match
    [ -e "$item" ] || continue
    
    local name=$(basename "$item")
    # Skip standard system localized config files or .DS_Store
    if [ "$name" = ".localized" ] || [ "$name" = ".DS_Store" ]; then
      continue
    fi

    local target_item="$dest/$name"
    
    if [ -L "$item" ]; then
      echo "  Skipping: $name is already a symlink."
      continue
    fi

    echo "  Migrating $name..."
    # Rename original
    mv "$item" "${item}_old"
    # Link
    ln -s "$target_item" "$item"
  done
  shopt -u dotglob

  echo "Successfully migrated contents of $src to $dest!"
}

migrate_folder() {
  local src="$1"
  local dest_name="$2"
  local dest="$GDRIVE_DIR/$dest_name"

  echo "------------------------------------------------"
  echo "Processing: $src -> $dest"

  if [ -L "$src" ]; then
    echo "Skipping: $src is already a symlink."
    return 0
  fi

  if [ ! -d "$src" ]; then
    echo "Skipping: $src is not a directory or does not exist."
    return 0
  fi

  # 1. Copy to Google Drive
  echo "Copying files to Google Drive..."
  mkdir -p "$dest"
  rsync -a --progress "$src/" "$dest/"

  # 2. Rename original to backup (to make sure it's safe)
  echo "Renaming original to backup..."
  mv "$src" "${src}_old"

  # 3. Create symlink
  echo "Creating symlink..."
  ln -s "$dest" "$src"

  echo "Successfully migrated $src to $dest!"
}

# Run migrations
# Backups is already done (will be skipped safely)
migrate_folder "/Users/natehoward/Backups" "Mac-Backups"

# System folders (migrate contents and link children)
migrate_contents_only "/Users/natehoward/Documents" "Mac-Documents"
migrate_contents_only "/Users/natehoward/Downloads" "Mac-Downloads"

# Screenshots inside Pictures (since Pictures contains Photos Library)
migrate_folder "/Users/natehoward/Pictures/Screenshots" "Mac-Screenshots"

echo "------------------------------------------------"
echo "All migrations completed successfully!"
echo "Please verify everything works, then you can delete the '_old' backup directories manually."
