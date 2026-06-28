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
# uv-based Python environment helpers
#
# The Python env is built with uv on a standalone CPython (never Anaconda's).
# A venv created from Anaconda's interpreter drags in Anaconda's native libs
# (e.g. libgio), which collide with the GDAL/GLib bundled by the geo wheels
# (geopandas/pyogrio) and crash scanpy/geopandas at runtime. uv's
# --python-preference only-managed guarantees a clean, self-contained base.
# =============================================================================

# Create (or reuse) the uv-managed virtual environment.
create_python_env() {
    mkdir -p "$VENV_BASE_DIR"

    if [ -d "$VENV_PATH" ]; then
        # Recreate if the existing env was built on Anaconda (the GLib/GDAL crash
        # cause); otherwise reuse it.
        if grep -qiE "anaconda|miniconda|/conda" "$VENV_PATH/pyvenv.cfg" 2>/dev/null; then
            warning "Existing '$VENV_NAME' env is Anaconda-based - recreating on a clean Python"
            rm -rf "$VENV_PATH"
        else
            warning "Environment '$VENV_NAME' already exists - using it"
            return 0
        fi
    fi

    uv venv "$VENV_PATH" --python "$PYTHON_VERSION" --python-preference only-managed
    success "$MSG_PYTHON_ENV_CREATED"
}

# Install the package (+ dev extras) into the env with uv.
install_python_packages() {
    activate_python_env "$VENV_PATH"
    uv pip install -e "$PYTHON_PACKAGE_SPEC"
    success "$MSG_PYTHON_PACKAGES_INSTALLED"
}

# Register a Jupyter kernel for this env so notebooks run on it (not Anaconda's
# base kernel). Non-fatal if ipykernel is unavailable.
register_jupyter_kernel() {
    if python -m ipykernel install --user --name "$VENV_NAME" \
        --display-name "$KERNEL_DISPLAY_NAME" >/dev/null 2>&1; then
        success "Registered Jupyter kernel '$KERNEL_DISPLAY_NAME'"
    else
        warning "Could not register Jupyter kernel (ipykernel missing?) - skipping"
    fi
}

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

    # Check npm
    if ! command_exists npm; then
        error "$ERR_NPM_NOT_FOUND"
        exit 1
    fi

    if ! check_npm_version "$NPM_MIN_VERSION"; then
        warning "$ERR_NPM_OLD"
    fi

    # Check uv (builds the Python env on a clean, standalone Python)
    if ! command_exists uv; then
        error "$ERR_UV_NOT_FOUND"
        exit 1
    fi

    success "$MSG_SYSTEM_OK"

    # Step 2: Create Python environment (uv + standalone Python, not Anaconda)
    info "$MSG_PYTHON_ENV_SETUP"
    create_python_env

    # Step 3: Install Python packages with uv, then register a Jupyter kernel
    info "$MSG_PYTHON_PACKAGES"
    install_python_packages
    register_jupyter_kernel

    # Step 4: Install JavaScript packages
    info "$MSG_JS_PACKAGES"
    npm install $NPM_INSTALL_ARGS
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

    # uv check
    if command_exists uv; then
        echo "✅ uv: $(uv --version)"
    else
        echo "❌ uv: Not found (install: curl -LsSf https://astral.sh/uv/install.sh | sh)"
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

    # npm check
    if command_exists npm; then
        echo "✅ npm: $(npm --version)"
        if check_npm_version "$NPM_MIN_VERSION"; then
            echo "✅ Version: Compatible (>= ${NPM_MIN_VERSION})"
        else
            echo "⚠️  Version: May be too old (< ${NPM_MIN_VERSION})"
        fi
    else
        echo "❌ npm: Not found"
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
        success "Environment is ready! Run 'npm run dev' to start"
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
    echo "  $HELP_REQUIREMENTS_NPM"
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

    # Detailed npm check
    if command_exists npm; then
        log_info "Found npm: $(npm --version)"
        if check_npm_version "$NPM_MIN_VERSION"; then
            log_success "npm version is compatible"
        else
            log_warning "npm version may be too old"
        fi
    else
        log_error "npm not found"
        exit 1
    fi

    # Detailed uv check
    if command_exists uv; then
        log_info "Found uv: $(uv --version)"
    else
        log_error "uv not found"
        echo "$ERR_UV_NOT_FOUND"
        exit 1
    fi

    # Create environment with detailed logging
    if [ -d "$VENV_PATH" ]; then
        log_warning "Virtual environment '$VENV_NAME' already exists"
        if grep -qiE "anaconda|miniconda|/conda" "$VENV_PATH/pyvenv.cfg" 2>/dev/null; then
            log_warning "It is Anaconda-based (the GLib/GDAL crash cause) - recreating"
            rm -rf "$VENV_PATH"
        elif confirm "Do you want to recreate it?" "N"; then
            log_info "Removing existing environment..."
            rm -rf "$VENV_PATH"
        else
            log_info "Using existing virtual environment"
        fi
    fi

    if [ ! -d "$VENV_PATH" ]; then
        # Create base directory if it doesn't exist
        mkdir -p "$VENV_BASE_DIR"

        run_command "Creating virtual environment '$VENV_NAME' (uv, standalone Python)" \
            uv venv "$VENV_PATH" --python "$PYTHON_VERSION" --python-preference only-managed
    fi

    # Activate and install with detailed output
    log_step "Activating virtual environment"
    activate_python_env "$VENV_PATH"

    run_command "Installing Python dependencies (uv)" \
        uv pip install -e "$PYTHON_PACKAGE_SPEC"

    run_command "Registering Jupyter kernel '$KERNEL_DISPLAY_NAME'" \
        python -m ipykernel install --user --name "$VENV_NAME" --display-name "$KERNEL_DISPLAY_NAME"

    run_command "Installing JavaScript dependencies" \
        npm install

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
