# Flask Auto-Start Setup Guide

This guide explains how to automatically start the Flask servers (bfc, diarix, vd) when you open a terminal on macOS or Linux.

## Overview

The solution includes:
- **`start_flask_servers.sh`** - Robust launcher script with port conflict detection
- **`zsh_aliases`** - Shell configuration for auto-start on terminal open
- Graceful process management (no forceful killing of all Python processes)
- Port availability checking before starting servers

## Features

✅ **Port Conflict Detection** - Checks if ports are in use before starting
✅ **Smart Restart** - Only starts servers if they're not already running
✅ **Graceful Shutdown** - Uses SIGTERM before SIGKILL
✅ **Process Tracking** - Maintains PID files to track running processes
✅ **Logging** - All server output goes to `.flask_logs/`
✅ **Cross-Platform** - Works on macOS and Linux

## Port Configuration

The Flask servers run on:
- **bfc** → port 5034
- **diarix** → port 5030
- **vd** → port 5005

## Manual Usage

### Start all servers
```bash
./start_flask_servers.sh
# or
./start_flask_servers.sh start
```

### Check server status
```bash
./start_flask_servers.sh check
# or
./start_flask_servers.sh status
```

### Stop all servers
```bash
./start_flask_servers.sh stop
```

### Restart all servers
```bash
./start_flask_servers.sh restart
```

### View logs
```bash
tail -f .flask_logs/bfc.log
tail -f .flask_logs/diarix.log
tail -f .flask_logs/vd.log
```

## Automatic Startup on Terminal Open

### macOS (zsh - default since Catalina)

Add this to your `~/.zshrc`:

```bash
# Auto-start Flask servers
source ~/monad/zsh_aliases
```

Or find the exact path:
```bash
export MONAD_ROOT="/path/to/monad/repo"
source $MONAD_ROOT/zsh_aliases
```

### macOS (bash)

Add this to your `~/.bash_profile`:

```bash
# Auto-start Flask servers
source ~/monad/zsh_aliases
```

### Linux (zsh or bash)

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export MONAD_ROOT="$HOME/monad"
source $MONAD_ROOT/zsh_aliases
```

## How It Works

1. **On Terminal Open**: The shell sources `zsh_aliases`
2. **Auto-Check**: The script checks if servers are running using stored PIDs
3. **Smart Start**: If any server isn't running, it starts them in background
4. **No Conflict**: Before starting, it verifies the port isn't in use
5. **Logging**: All output goes to `.flask_logs/` directory

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error:

```bash
# Check which process is using the port
# macOS:
lsof -i :5034

# Linux:
ss -tuln | grep 5034

# Kill it if needed
kill -9 <PID>

# Then restart servers
./start_flask_servers.sh restart
```

### Servers Not Starting

Check the logs:
```bash
cat .flask_logs/bfc.log
cat .flask_logs/diarix.log
cat .flask_logs/vd.log
```

### Virtual Environments Issues

If you get venv errors, you may need to ensure dependencies are installed:

```bash
# For each project:
cd projects/bfc && pip install -r requirements.txt
cd ../diarix && pip install -r requirements.txt
cd ../vd && pip install -r requirements.txt
```

### Disable Auto-Start

If you don't want auto-start on terminal open, simply:
1. Remove the `source ~/monad/zsh_aliases` line from `~/.zshrc`
2. Or comment it out

You can still manually start servers with:
```bash
cd ~/monad
./start_flask_servers.sh
```

## PID and Log Files

- **PIDs**: `.flask_pids/` - Contains `.pid` files for each server
- **Logs**: `.flask_logs/` - Contains `.log` files for each server

These directories are created automatically.

## Comparison to Old Setup

| Feature | Old (`lau.sh`) | New (`start_flask_servers.sh`) |
|---------|---|---|
| Port conflict detection | ❌ | ✅ |
| Graceful shutdown | ❌ | ✅ |
| Check status | ❌ | ✅ |
| Process tracking | ❌ | ✅ |
| Cross-platform | Limited | ✅ macOS/Linux |
| Safe process cleanup | ❌ (pkill -9) | ✅ (SIGTERM first) |
| Auto-start without forcing | ❌ (kills all) | ✅ (checks first) |

## For PR Reviewers

This implementation:
1. ✅ Solves port conflicts issue
2. ✅ Prevents uncontrolled killing of Flask apps
3. ✅ Works reliably on macOS Terminal
4. ✅ Backward compatible (old `lau.sh` still available)
5. ✅ Production-ready with proper error handling
6. ✅ Easy to use and understand
