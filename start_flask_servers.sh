#!/bin/bash
#
# Flask Multi-App Launcher
# Starts bfc, diarix, and vd Flask servers with port conflict detection
# and graceful process management for macOS/Linux.
#
# Usage:
#   ./start_flask_servers.sh              # Start all servers
#   ./start_flask_servers.sh --check      # Check if servers are running
#   ./start_flask_servers.sh --stop       # Stop all servers
#   ./start_flask_servers.sh --restart    # Restart all servers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"
PID_DIR="${REPO_ROOT}/.flask_pids"
LOG_DIR="${REPO_ROOT}/.flask_logs"

# Apps configuration: app_name:port:directory
declare -A APPS=(
  [bfc]="5034:${REPO_ROOT}/projects/bfc"
  [diarix]="5030:${REPO_ROOT}/projects/diarix"
  [vd]="5005:${REPO_ROOT}/projects/vd"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Ensure directories exist
mkdir -p "$PID_DIR" "$LOG_DIR"

# Helper: Check if port is in use
port_in_use() {
  local port=$1
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    lsof -i "tcp:$port" &>/dev/null && return 0 || return 1
  else
    # Linux
    ss -tuln 2>/dev/null | grep -q ":$port " && return 0 || return 1
  fi
}

# Helper: Check if process is running
pid_is_running() {
  local pid=$1
  kill -0 "$pid" 2>/dev/null && return 0 || return 1
}

# Helper: Get PID from pidfile
get_stored_pid() {
  local app=$1
  local pidfile="${PID_DIR}/${app}.pid"
  if [[ -f "$pidfile" ]]; then
    cat "$pidfile"
  fi
}

# Helper: Check if app is running
app_is_running() {
  local app=$1
  local stored_pid=$(get_stored_pid "$app")
  
  if [[ -z "$stored_pid" ]]; then
    return 1
  fi
  
  if pid_is_running "$stored_pid"; then
    return 0
  else
    # PID exists but process not running, clean up
    rm -f "${PID_DIR}/${app}.pid"
    return 1
  fi
}

# Helper: Kill app gracefully
kill_app() {
  local app=$1
  local stored_pid=$(get_stored_pid "$app")
  
  if [[ -z "$stored_pid" ]]; then
    return 0
  fi
  
  if pid_is_running "$stored_pid"; then
    echo -e "${YELLOW}Stopping $app (PID: $stored_pid)...${NC}"
    kill -TERM "$stored_pid" 2>/dev/null || true
    
    # Wait up to 5 seconds for graceful shutdown
    local count=0
    while pid_is_running "$stored_pid" && [[ $count -lt 5 ]]; do
      sleep 1
      ((count++))
    done
    
    # Force kill if still running
    if pid_is_running "$stored_pid"; then
      echo -e "${YELLOW}Force killing $app (PID: $stored_pid)...${NC}"
      kill -KILL "$stored_pid" 2>/dev/null || true
    fi
  fi
  
  rm -f "${PID_DIR}/${app}.pid"
}

# Start a single app
start_app() {
  local app=$1
  local port_and_dir="${APPS[$app]}"
  local port="${port_and_dir%:*}"
  local app_dir="${port_and_dir#*:}"
  
  # Check if already running
  if app_is_running "$app"; then
    echo -e "${GREEN}✓ $app is already running (PID: $(get_stored_pid "$app"), port $port)${NC}"
    return 0
  fi
  
  # Check for port conflicts
  if port_in_use "$port"; then
    echo -e "${RED}✗ Port $port is already in use (possibly by another process)${NC}"
    return 1
  fi
  
  # Check if directory and app.py exist
  if [[ ! -d "$app_dir" ]]; then
    echo -e "${RED}✗ App directory not found: $app_dir${NC}"
    return 1
  fi
  
  if [[ ! -f "$app_dir/app.py" ]]; then
    echo -e "${RED}✗ app.py not found in: $app_dir${NC}"
    return 1
  fi
  
  # Start the app
  echo -e "${YELLOW}Starting $app on port $port...${NC}"
  
  cd "$app_dir" || return 1
  
  # Ensure venv exists
  if [[ ! -d ".venv" ]]; then
    echo -e "${YELLOW}Creating virtual environment for $app...${NC}"
    python3 -m venv .venv || return 1
  fi
  
  # Activate venv and install requirements if needed
  source .venv/bin/activate
  if [[ -f "requirements.txt" ]]; then
    pip install -q -r requirements.txt 2>/dev/null || true
  fi
  
  # Start Flask app in background
  if [[ "$app" == "bfc" ]]; then
    PORT=$port python app.py > "${LOG_DIR}/${app}.log" 2>&1 &
  else
    python app.py > "${LOG_DIR}/${app}.log" 2>&1 &
  fi
  
  local new_pid=$!
  echo "$new_pid" > "${PID_DIR}/${app}.pid"
  
  # Give it a moment to start and verify
  sleep 2
  
  if pid_is_running "$new_pid"; then
    echo -e "${GREEN}✓ $app started successfully (PID: $new_pid, port $port)${NC}"
    return 0
  else
    echo -e "${RED}✗ Failed to start $app. Check log: ${LOG_DIR}/${app}.log${NC}"
    cat "${LOG_DIR}/${app}.log" | tail -10
    rm -f "${PID_DIR}/${app}.pid"
    return 1
  fi
}

# Start all apps
start_all() {
  echo "Starting Flask servers..."
  local failed=0
  
  for app in bfc diarix vd; do
    if ! start_app "$app"; then
      ((failed++))
    fi
  done
  
  if [[ $failed -eq 0 ]]; then
    echo -e "${GREEN}All servers started successfully!${NC}"
    echo ""
    echo "Access your apps at:"
    echo "  bfc:    http://127.0.0.1:5034"
    echo "  diarix: http://127.0.0.1:5030"
    echo "  vd:     http://127.0.0.1:5005"
    echo ""
    echo "Logs: $LOG_DIR"
    return 0
  else
    echo -e "${RED}Failed to start $failed server(s)${NC}"
    return 1
  fi
}

# Check status of all apps
check_status() {
  echo "Flask server status:"
  local all_running=true
  
  for app in bfc diarix vd; do
    local port_and_dir="${APPS[$app]}"
    local port="${port_and_dir%:*}"
    
    if app_is_running "$app"; then
      local pid=$(get_stored_pid "$app")
      echo -e "${GREEN}✓ $app is running (PID: $pid, port $port)${NC}"
    else
      echo -e "${RED}✗ $app is NOT running (port $port)${NC}"
      all_running=false
    fi
  done
  
  echo ""
  if $all_running; then
    echo -e "${GREEN}All servers are running!${NC}"
    return 0
  else
    echo -e "${YELLOW}Some servers are not running${NC}"
    return 1
  fi
}

# Stop all apps
stop_all() {
  echo "Stopping Flask servers..."
  
  for app in bfc diarix vd; do
    kill_app "$app"
  done
  
  echo -e "${GREEN}All servers stopped${NC}"
}

# Restart all apps
restart_all() {
  stop_all
  sleep 1
  start_all
}

# Main
case "${1:-start}" in
  start)
    start_all
    ;;
  check|status)
    check_status
    ;;
  stop)
    stop_all
    ;;
  restart)
    restart_all
    ;;
  *)
    echo "Usage: $0 [start|check|stop|restart]"
    echo ""
    echo "  start   - Start all Flask servers (default)"
    echo "  check   - Check status of servers"
    echo "  stop    - Stop all Flask servers"
    echo "  restart - Restart all Flask servers"
    exit 1
    ;;
esac
