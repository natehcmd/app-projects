const fs = require('fs');
const path = require('path');

// Configuration
const WATCH_DIRS = [
  '/Users/natehoward/Projects',
  '/Users/natehoward/Desktop',
  '/Users/natehoward/Documents',
  '/Users/natehoward/scripts'
];

const BASE_DIR = '/Users/natehoward/.agent-safeguard';
const BACKUP_DIR = path.join(BASE_DIR, 'backups');
const LOG_FILE = path.join(BASE_DIR, 'safeguard.log');

const IGNORE_PATTERNS = [
  /[\\/]node_modules[\\/]/,
  /[\\/]\.git[\\/]/,
  /[\\/]\.DS_Store$/,
  /[\\/]dist[\\/]/,
  /[\\/]build[\\/]/,
  /[\\/]\.build[\\/]/,
  /[\\/]\.xcodeproj[\\/]/,
  /[\\/]\.xcworkspace[\\/]/,
  /[\\/]\.swiftpm[\\/]/,
  /[\\/]\.idea[\\/]/,
  /[\\/]\.vscode[\\/]/,
  /[\\/]\.next[\\/]/,
  /[\\/]\.cache[\\/]/,
  /\.log$/,
  /\.db$/
];

const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

// Ensure directories exist
if (!fs.existsSync(BASE_DIR)) fs.mkdirSync(BASE_DIR, { recursive: true });
if (!fs.existsSync(BACKUP_DIR)) fs.mkdirSync(BACKUP_DIR, { recursive: true });

function log(msg) {
  const time = new Date().toISOString();
  const line = `[${time}] ${msg}\n`;
  try {
    fs.appendFileSync(LOG_FILE, line);
  } catch (e) {
    console.error('Failed to write to log file:', e.message);
  }
  console.log(line.trim());
}

// Track file operations in progress to prevent infinite loop loops
const activeOperations = new Set();
// Track debouncing timers
const timers = new Map();

function shouldIgnore(filePath) {
  if (filePath.startsWith(BASE_DIR)) return true;
  for (const pattern of IGNORE_PATTERNS) {
    if (pattern.test(filePath)) return true;
  }
  return false;
}

function getBackupPath(originalPath) {
  const relPath = path.relative('/Users/natehoward', originalPath);
  return path.join(BACKUP_DIR, relPath);
}

// Performs a backup copy of a file
function backupFile(originalPath) {
  if (shouldIgnore(originalPath)) return;

  // Verify it's a file and within size limits
  try {
    const stats = fs.statSync(originalPath);
    if (!stats.isFile()) return; // Don't backup directories directly (handled via children)
    if (stats.size > MAX_FILE_SIZE) {
      log(`SKIPPED (TOO LARGE): ${originalPath} (${(stats.size / 1024 / 1024).toFixed(2)} MB)`);
      return;
    }
  } catch (e) {
    return; // File might have been deleted before we stat'd it
  }

  const backupPath = getBackupPath(originalPath);

  try {
    fs.mkdirSync(path.dirname(backupPath), { recursive: true });
    
    // Copy the file
    activeOperations.add(backupPath);
    fs.copyFileSync(originalPath, backupPath);
    // Keep in set briefly to let FS events settle
    setTimeout(() => activeOperations.delete(backupPath), 200);

    log(`BACKED UP: ${originalPath}`);
  } catch (err) {
    log(`ERROR BACKING UP ${originalPath}: ${err.message}`);
    activeOperations.delete(backupPath);
  }
}

// Restores a single file or a directory structure
function restorePath(originalPath) {
  if (shouldIgnore(originalPath)) return;
  const backupPath = getBackupPath(originalPath);

  if (!fs.existsSync(backupPath)) {
    log(`DELETED (NO BACKUP AVAILABLE): ${originalPath}`);
    return;
  }

  try {
    const backupStats = fs.statSync(backupPath);
    
    if (backupStats.isFile()) {
      log(`DELETION DETECTED: Restoring file ${originalPath}`);
      fs.mkdirSync(path.dirname(originalPath), { recursive: true });
      
      activeOperations.add(originalPath);
      fs.copyFileSync(backupPath, originalPath);
      setTimeout(() => activeOperations.delete(originalPath), 500);
      
      log(`RESTORED FILE: ${originalPath}`);
    } else if (backupStats.isDirectory()) {
      log(`DELETION DETECTED: Restoring directory ${originalPath}`);
      restoreDirectoryRecursive(backupPath, originalPath);
    }
  } catch (err) {
    log(`ERROR RESTORING ${originalPath}: ${err.message}`);
    activeOperations.delete(originalPath);
  }
}

function restoreDirectoryRecursive(srcDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(srcDir, entry.name);
    const destPath = path.join(destDir, entry.name);

    if (entry.isDirectory()) {
      restoreDirectoryRecursive(srcPath, destPath);
    } else if (entry.isFile()) {
      activeOperations.add(destPath);
      fs.copyFileSync(srcPath, destPath);
      setTimeout(() => activeOperations.delete(destPath), 500);
      log(`RESTORED CHILD: ${destPath}`);
    }
  }
}

// Initialize backups for existing files on startup (non-blocking)
function initializeBackups() {
  log("Initializing baseline backups for watched directories...");
  let count = 0;
  
  function scan(dir) {
    if (shouldIgnore(dir)) return;
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          scan(fullPath);
        } else if (entry.isFile()) {
          const backupPath = getBackupPath(fullPath);
          if (!fs.existsSync(backupPath)) {
            backupFile(fullPath);
            count++;
          }
        }
      }
    } catch (e) {
      log(`ERROR SCANNING ${dir}: ${e.message}`);
    }
  }

  WATCH_DIRS.forEach(dir => {
    if (fs.existsSync(dir)) scan(dir);
  });
  
  log(`Baseline backup completed. Backed up ${count} new files.`);
}

// Start watching
WATCH_DIRS.forEach(watchDir => {
  if (!fs.existsSync(watchDir)) {
    log(`Watch directory does not exist, skipping: ${watchDir}`);
    return;
  }

  log(`Watching for changes in: ${watchDir}`);

  fs.watch(watchDir, { recursive: true }, (eventType, filename) => {
    if (!filename) return;

    const fullPath = path.join(watchDir, filename);
    if (activeOperations.has(fullPath)) return;
    if (shouldIgnore(fullPath)) return;

    // Debounce to allow multiple fast FS events to settle (e.g. editor saves, temp files)
    if (timers.has(fullPath)) {
      clearTimeout(timers.get(fullPath));
    }

    const timer = setTimeout(() => {
      timers.delete(fullPath);
      
      const exists = fs.existsSync(fullPath);
      if (exists) {
        backupFile(fullPath);
      } else {
        restorePath(fullPath);
      }
    }, 300); // 300ms debounce window

    timers.set(fullPath, timer);
  });
});

// Run baseline backup scan
initializeBackups();

log("Agent Safeguard Daemon successfully started.");
