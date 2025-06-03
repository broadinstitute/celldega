#!/bin/bash
# =============================================================================
# Shared utilities for Celldega development scripts
# Source this file: source scripts/utils.sh
# =============================================================================

# Colors for output
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export PURPLE='\033[0;35m'
export CYAN='\033[0;36m'
export NC='\033[0m' # No Color

# =============================================================================
# Simple Logging (for user-friendly scripts)
# =============================================================================
info() { echo -e "${BLUE}💡 $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
step() { echo -e "${PURPLE}🔄 $1${NC}"; }

# =============================================================================
# Detailed Logging (for verbose/debug mode)
# =============================================================================
log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🔄 $1${NC}"; }
log_debug() {
    if [ "${DEBUG:-}" = "true" ]; then
        echo -e "${CYAN}🐛 $1${NC}"
    fi
}

# =============================================================================
# Basic Utilities
# =============================================================================
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

is_project_root() {
    local all_exist=true
    for file in "${PROJECT_FILES[@]}"; do
        if [ ! -f "$file" ]; then
            all_exist=false
            break
        fi
    done
    $all_exist
}

ensure_project_root() {
    if ! is_project_root; then
        error "Please run this script from the project root directory"
        info "Expected files: ${PROJECT_FILES[*]}"
        exit 1
    fi
}

# =============================================================================
# Environment Management
# =============================================================================
activate_python_env() {
    local venv_path="${1:-$VENV_PATH}"

    if [ -z "${VIRTUAL_ENV:-}" ]; then
        if [ -d "$venv_path" ]; then
            # Try Unix/Linux/macOS path first, then Windows
            if [ -f "$venv_path/bin/activate" ]; then
                source "$venv_path/bin/activate"
            elif [ -f "$venv_path/Scripts/activate" ]; then
                source "$venv_path/Scripts/activate"
            else
                error "Could not find activation script in $venv_path"
                return 1
            fi
        else
            error "Python environment '$venv_path' not found. Run ./scripts/setup.sh first"
            return 1
        fi
    fi
}

# =============================================================================
# Version Checks
# =============================================================================
check_python_version() {
    local required="${1:-$PYTHON_MIN_VERSION}"

    # Try python3 first, then python
    local python_cmd=""
    if command_exists python3; then
        python_cmd="python3"
    elif command_exists python; then
        python_cmd="python"
    else
        return 1
    fi

    local version=$($python_cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)

    if [ -z "$version" ]; then
        return 1
    fi

    # Simple version comparison
    if [ "$(printf '%s\n' "$required" "$version" | sort -V | head -n1)" = "$required" ]; then
        return 0
    else
        return 1
    fi
}

check_node_version() {
    local required="${1:-$NODE_MIN_VERSION}"

    if ! command_exists node; then
        return 1
    fi

    local version=$(node --version 2>/dev/null | sed 's/v//' | cut -d. -f1)

    if [ -z "$version" ]; then
        return 1
    fi

    if [ "$version" -ge "$required" ]; then
        return 0
    else
        return 1
    fi
}

check_npm_version() {
    local required="${1:-$NPM_MIN_VERSION}"

    if ! command_exists npm; then
        return 1
    fi

    local version=$(npm --version 2>/dev/null | cut -d. -f1)

    if [ -z "$version" ]; then
        return 1
    fi

    if [ "$version" -ge "$required" ]; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# UI Helpers
# =============================================================================
simple_banner() {
    local title="$1"
    echo
    echo -e "${BLUE}🧬 $title${NC}"
    echo
}

show_banner() {
    local title="$1"
    local width=60
    local padding=$(((width - ${#title}) / 2))

    echo
    echo -e "${CYAN}$(printf '%*s' $width | tr ' ' '=')"
    echo -e "$(printf '%*s' $padding)${title}$(printf '%*s' $padding)"
    echo -e "$(printf '%*s' $width | tr ' ' '=')${NC}"
    echo
}

next_steps() {
    echo
    success "🎉 Celldega is ready to use!"
    echo
    echo "Next steps:"
    echo "  1. Activate environment:  $ACTIVATION_COMMAND"
    echo "  2. Start developing:      npm run dev"
    echo "  3. Open notebooks:        jupyter lab notebooks/"
    echo
    echo "Need help? Run: ./scripts/setup.sh --help"
}

# =============================================================================
# User Interaction
# =============================================================================
confirm() {
    local prompt="${1:-Are you sure?}"
    local default="${2:-N}"

    if [ "$default" = "Y" ] || [ "$default" = "y" ]; then
        read -p "$prompt (Y/n): " -n 1 -r
        echo
        [[ $REPLY =~ ^[Nn]$ ]] && return 1
    else
        read -p "$prompt (y/N): " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || return 1
    fi
    return 0
}

# =============================================================================
# Command Execution
# =============================================================================
run_quiet() {
    local description="$1"
    shift

    if [ "${VERBOSE:-}" = "true" ]; then
        step "$description"
        "$@"
        if [ $? -eq 0 ]; then
            success "$description completed"
        else
            error "$description failed"
            return 1
        fi
    else
        if "$@" >/dev/null 2>&1; then
            return 0
        else
            error "$description failed"
            return 1
        fi
    fi
}

run_command() {
    local description="$1"
    shift

    log_step "$description"

    if [ "${VERBOSE:-}" = "true" ]; then
        "$@"
    else
        "$@" >/dev/null 2>&1
    fi

    if [ $? -eq 0 ]; then
        log_success "$description completed"
    else
        log_error "$description failed"
        return 1
    fi
}

# =============================================================================
# Pre-commit Setup
# =============================================================================
setup_precommit() {
    step "Setting up code quality checks..."

    if ! command_exists pre-commit; then
        info "Installing pre-commit..."
        pip install pre-commit --quiet
    fi

    if [ -f ".pre-commit-config.yaml" ]; then
        pre-commit install --quiet >/dev/null 2>&1
        success "Code quality checks ready"
    else
        warning "No pre-commit config found - skipping"
    fi
}

check_precommit_status() {
    echo "🔍 Code Quality Status:"

    if command_exists pre-commit; then
        echo "✅ pre-commit: $(pre-commit --version)"
    else
        echo "❌ pre-commit: Not installed"
    fi

    if [ -f ".pre-commit-config.yaml" ]; then
        echo "✅ Configuration: Found"

        if [ -f ".git/hooks/pre-commit" ]; then
            echo "✅ Hooks: Installed"
        else
            echo "⚠️  Hooks: Not installed (run 'pre-commit install')"
        fi
    else
        echo "❌ Configuration: Not found"
    fi
}
