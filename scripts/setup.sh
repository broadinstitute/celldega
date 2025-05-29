#!/bin/bash
# =============================================================================
# 🧬 Celldega Setup - Get started in 30 seconds
# =============================================================================

set -e

# =============================================================================
# Load Configuration and Utilities
# =============================================================================

# Get script directory and source shared configuration and utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
source "$SCRIPT_DIR/utils.sh"

# =============================================================================
# Main Setup (The Happy Path)
# =============================================================================

main_setup() {
    simple_banner "Setting up Celldega for you..."

    # Step 1: Check system requirements
    info "$MSG_SYSTEM_CHECK"

    # Check Python
    local python_cmd=""
    if command_exists python3; then
        python_cmd="python3"
    elif command_exists python; then
        python_cmd="python"
    else
        error "$ERR_PYTHON_NOT_FOUND"
        exit 1
    fi

    if ! check_python_version "$PYTHON_MIN_VERSION"; then
        warning "$ERR_PYTHON_OLD"
    fi

    # Check Node.js
    if ! command_exists node; then
        error "$ERR_NODE_NOT_FOUND"
        exit 1
    fi

    if ! check_node_version "$NODE_MIN_VERSION"; then
        warning "$ERR_NODE_OLD"
    fi

    # Check pnpm
    if ! command_exists pnpm; then
        error "$ERR_PNPM_NOT_FOUND"
        exit 1
    fi

    if ! check_pnpm_version "$PNPM_MIN_VERSION"; then
        warning "$ERR_PNPM_OLD"
    fi

    success "$MSG_SYSTEM_OK"

    # Step 2: Create Python environment
    info "$MSG_PYTHON_ENV_SETUP"

    # Create base directory if it doesn't exist
    mkdir -p "$VENV_BASE_DIR"

    if [ -d "$VENV_PATH" ]; then
        warning "Environment '$VENV_NAME' already exists - using it"
    else
        $python_cmd -m venv "$VENV_PATH"
        success "$MSG_PYTHON_ENV_CREATED"
    fi

    # Step 3: Install Python packages
    info "$MSG_PYTHON_PACKAGES"
    activate_python_env "$VENV_PATH"

    pip install $PIP_INSTALL_ARGS
    pip install -e "$PYTHON_PACKAGE_SPEC" --quiet
    success "$MSG_PYTHON_PACKAGES_INSTALLED"

    # Step 4: Install JavaScript packages
    info "$MSG_JS_PACKAGES"
    pnpm install $PNPM_INSTALL_ARGS
    success "$MSG_JS_PACKAGES_INSTALLED"

    # Step 5: Setup development tools
    info "$MSG_DEV_TOOLS"
    setup_precommit
    success "$MSG_DEV_TOOLS_READY"

    # Success!
    next_steps
}

# =============================================================================
# Status and Management Functions
# =============================================================================

show_status() {
    simple_banner "Celldega Environment Status"

    # Python check
    if command_exists python3; then
        echo "✅ Python: $(python3 --version)"
        if check_python_version "$PYTHON_MIN_VERSION"; then
            echo "✅ Version: Compatible (>= ${PYTHON_MIN_VERSION})"
        else
            echo "⚠️  Version: May be too old (< ${PYTHON_MIN_VERSION})"
        fi
    elif command_exists python; then
        echo "✅ Python: $(python --version)"
        if check_python_version "$PYTHON_MIN_VERSION"; then
            echo "✅ Version: Compatible (>= ${PYTHON_MIN_VERSION})"
        else
            echo "⚠️  Version: May be too old (< ${PYTHON_MIN_VERSION})"
        fi
    else
        echo "❌ Python: Not found"
    fi

    # Node check
    if command_exists node; then
        echo "✅ Node.js: $(node --version)"
        if check_node_version "$NODE_MIN_VERSION"; then
            echo "✅ Version: Compatible (>= ${NODE_MIN_VERSION})"
        else
            echo "⚠️  Version: May be too old (< ${NODE_MIN_VERSION})"
        fi
    else
        echo "❌ Node.js: Not found"
    fi

    # pnpm check
    if command_exists pnpm; then
        echo "✅ pnpm: $(pnpm --version)"
        if check_pnpm_version "$PNPM_MIN_VERSION"; then
            echo "✅ Version: Compatible (>= ${PNPM_MIN_VERSION})"
        else
            echo "⚠️  Version: May be too old (< ${PNPM_MIN_VERSION})"
        fi
    else
        echo "❌ pnpm: Not found"
    fi

    # Environment check
    if [ -d "$VENV_PATH" ]; then
        echo "✅ Python environment: Created"
        if [ -n "${VIRTUAL_ENV:-}" ]; then
            echo "✅ Environment: Active"
        else
            echo "💡 Environment: Run '$ACTIVATION_COMMAND' to activate"
        fi
    else
        echo "❌ Python environment: Not created"
    fi

    # Dependencies check
    if [ -d "node_modules" ]; then
        echo "✅ JavaScript packages: Installed"
    else
        echo "❌ JavaScript packages: Not installed"
    fi

    # Code quality check
    echo
    check_precommit_status

    echo
    if [ -d "$VENV_PATH" ] && [ -d "node_modules" ]; then
        success "Environment is ready! Run 'pnpm run dev' to start"
    else
        info "Run './scripts/setup.sh' to complete setup"
    fi
}

reset_environment() {
    warning "This will delete your current environment and all installed packages"
    if confirm "Continue?" "N"; then
        info "Cleaning up..."
        rm -rf "$VENV_PATH" "${CLEANUP_PATTERNS[@]}" 2>/dev/null || true
        success "Environment reset. Run './scripts/setup.sh' to reinstall"
    else
        info "Cancelled"
    fi
}

show_help() {
    echo "🧬 Celldega Setup"
    echo
    echo "Quick start:"
    echo "  ./scripts/setup.sh                    # Just works!"
    echo
    echo "Options:"
    echo "  ./scripts/setup.sh --status           # Check current setup"
    echo "  ./scripts/setup.sh --reset            # Clean install"
    echo "  ./scripts/setup.sh --verbose          # Show detailed output"
    echo "  ./scripts/setup.sh --help             # This help"
    echo
    echo "Requirements:"
    echo "  $HELP_REQUIREMENTS_PYTHON"
    echo "  $HELP_REQUIREMENTS_NODE"
    echo "  $HELP_REQUIREMENTS_PNPM"
    echo
    echo "Troubleshooting:"
    echo "  • Run from the project root directory"
    echo "  • Check ./scripts/README.md for more help"
}

# =============================================================================
# Verbose Mode (Advanced Users)
# =============================================================================

verbose_setup() {
    show_banner "Celldega Development Environment Setup"

    log_info "🚀 Setting up Celldega development environment..."

    # Check prerequisites with detailed output
    log_step "Checking system prerequisites"

    # Detailed Python check
    if command_exists python3; then
        log_info "Found python3: $(python3 --version)"
        if check_python_version "$PYTHON_MIN_VERSION"; then
            log_success "Python version is compatible"
        else
            log_warning "Python version may be too old"
        fi
    elif command_exists python; then
        log_info "Found python: $(python --version)"
        if check_python_version "$PYTHON_MIN_VERSION"; then
            log_success "Python version is compatible"
        else
            log_warning "Python version may be too old"
        fi
    else
        log_error "Python not found"
        exit 1
    fi

    # Detailed Node.js check
    if command_exists node; then
        log_info "Found Node.js: $(node --version)"
        if check_node_version "$NODE_MIN_VERSION"; then
            log_success "Node.js version is compatible"
        else
            log_warning "Node.js version may be too old"
        fi
    else
        log_error "Node.js not found"
        exit 1
    fi

    # Detailed pnpm check
    if command_exists pnpm; then
        log_info "Found pnpm: $(pnpm --version)"
        if check_pnpm_version "$PNPM_MIN_VERSION"; then
            log_success "pnpm version is compatible"
        else
            log_warning "pnpm version may be too old"
        fi
    else
        log_error "pnpm not found"
        exit 1
    fi

    # Create environment with detailed logging
    if [ -d "$VENV_PATH" ]; then
        log_warning "Virtual environment '$VENV_NAME' already exists"
        if confirm "Do you want to recreate it?" "N"; then
            log_info "Removing existing environment..."
            rm -rf "$VENV_PATH"
        else
            log_info "Using existing virtual environment"
        fi
    fi

    if [ ! -d "$VENV_PATH" ]; then
        # Create base directory if it doesn't exist
        mkdir -p "$VENV_BASE_DIR"

        run_command "Creating virtual environment '$VENV_NAME'" \
            python3 -m venv "$VENV_PATH" || python -m venv "$VENV_PATH"
    fi

    # Activate and install with detailed output
    log_step "Activating virtual environment"
    activate_python_env "$VENV_PATH"

    run_command "Upgrading pip" \
        pip install --upgrade pip

    run_command "Installing Python dependencies" \
        pip install -e "$PYTHON_PACKAGE_SPEC"

    run_command "Installing JavaScript dependencies" \
        pnpm install

    # Setup development tools
    log_step "Setting up development tools"
    if command_exists pre-commit; then
        run_command "Installing pre-commit hooks" \
            pre-commit install
    else
        log_warning "pre-commit not found, skipping hooks installation"
    fi

    log_success "🎉 Celldega development environment is ready!"
    log_info "$ACTIVATION_MSG"
}

# =============================================================================
# Script Entry Point
# =============================================================================

# Check we're in the right place
ensure_project_root

# Handle arguments
case "${1:-}" in
    --help|-h)
        show_help
        ;;
    --status)
        show_status
        ;;
    --reset)
        reset_environment
        ;;
    --verbose)
        export VERBOSE=true
        verbose_setup
        ;;
    "")
        main_setup
        ;;
    *)
        error "Unknown option: $1"
        echo "Run './scripts/setup.sh --help' for usage"
        exit 1
        ;;
esac
