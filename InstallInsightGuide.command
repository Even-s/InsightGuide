#!/bin/bash
# One-click macOS bootstrap for a new InsightGuide development machine.

set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

bold() { printf "\033[1m%s\033[0m\n" "$1"; }
ok() { printf "   ✅ %s\n" "$1"; }
info() { printf "   %s\n" "$1"; }

pause_and_exit() {
    local status="$1"
    echo ""
    if [ "$status" -eq 0 ]; then
        bold "InsightGuide installation completed."
        echo "Edit backend/.env and set OPENAI_API_KEY before launching the app."
        echo "Then double-click InsightGuide.command to start all services."
    else
        bold "InsightGuide installation failed (exit code: $status)."
        echo "Review the error above, then run this command again."
    fi
    echo ""
    echo "Press Enter to close this window."
    read -r _
    exit "$status"
}

install_homebrew() {
    if command -v brew >/dev/null 2>&1; then
        ok "Homebrew is already installed"
        return 0
    fi

    info "Installing Homebrew. It may request your macOS password..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || return 1

    if [ -x /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -x /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    command -v brew >/dev/null 2>&1
}

install_formula() {
    local formula="$1"
    local label="$2"
    if brew list --formula "$formula" >/dev/null 2>&1; then
        ok "$label is already installed"
    else
        info "Installing $label..."
        brew install "$formula"
    fi
}

install_cask() {
    local cask="$1"
    local app_path="$2"
    local label="$3"
    if [ -d "$app_path" ] || brew list --cask "$cask" >/dev/null 2>&1; then
        ok "$label is already installed"
    else
        info "Installing $label..."
        brew install --cask "$cask"
    fi
}

wait_for_docker() {
    if docker info >/dev/null 2>&1; then
        ok "Docker Desktop is ready"
        return 0
    fi

    info "Opening Docker Desktop. Complete any first-run prompts if they appear..."
    open -a Docker || return 1
    for _ in $(seq 1 90); do
        if docker info >/dev/null 2>&1; then
            ok "Docker Desktop is ready"
            return 0
        fi
        sleep 2
    done

    echo "Docker Desktop did not become ready within 180 seconds." >&2
    return 1
}

main() {
    bold "InsightGuide one-click installation"
    echo ""

    if [ "$(uname -s)" != "Darwin" ]; then
        echo "This command supports macOS only." >&2
        return 1
    fi

    bold "1. Installing system dependencies"
    install_homebrew || return 1
    install_formula node "Node.js" || return 1
    install_formula python@3.11 "Python 3.11" || return 1
    install_cask docker-desktop /Applications/Docker.app "Docker Desktop" || return 1
    echo ""

    bold "2. Starting Docker Desktop"
    wait_for_docker || return 1
    echo ""

    bold "3. Installing project dependencies"
    ./insightguide.sh setup || return 1
}

main
pause_and_exit $?
