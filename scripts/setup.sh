#!/bin/bash
# =============================================================================
# 🧬 Celldega Setup - Get started in 30 seconds
# =============================================================================

set -e

# Get script directory and source utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# =============================================================================
# Main Setup (The Happy Path)
# =============================================================================

main_setup() {
    simple_banner "Setting up Celldega for you..."

    # Step 1: Check system requirements
    info "Checking your system..."

    # Check Python
    local python_cmd=""
    if command_exists python3; then
        python_cmd="python3"
    elif command_exists python; then
        python_cmd="python"
    else
        error "Python not found. Please install Python 3.10+ from python.org"
        exit 1
    fi

    if ! check_python_version "3.10"; then
        warning "Python version may be too old. Please ensure you have Python 3.10+"
    fi

    # Check Node.js
    if ! command_exists node; then
        error "Node.js not found. Please install Node.js 16+ from nodejs.org"
        exit 1
    fi

    if ! check_node_version "16"; then
        warning "Node.js version may be too old. Please ensure you have Node.js 16+"
    fi

    success "System looks good!"

    # Step 2: Create Python environment
    info "Setting up Python environment..."

    if [ -d "dega" ]; then
        warning "Environment 'dega' already exists - using it"
    else
        $python_cmd -m venv dega
        success "Created Python environment"
    fi

    # Step 3: Install Python packages
    info "Installing Python packages..."
    activate_python_env "dega"

    pip install --upgrade pip --quiet
    pip install -e ".[dev]" --quiet
    success "Python packages installed"

    # Step 4: Install JavaScript packages
    info "Installing JavaScript packages..."
    npm install --silent
    success "JavaScript packages installed"

    # Step 5: Setup development tools
    info "Setting up development tools..."
    setup_precommit
    success "Development tools ready"

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
        if check_python_version "3.10"; then
            echo "✅ Version: Compatible (>= 3.10)"
        else
            echo "⚠️  Version: May be too old (< 3.10)"
        fi
    elif command_exists python; then
        echo "✅ Python: $(python --version)"
        if check_python_version "3.10"; then
            echo "✅ Version: Compatible (>= 3.10)"
        else
            echo "⚠️  Version: May be too old (< 3.10)"
        fi
    else
        echo "❌ Python: Not found"
    fi

    # Node check
    if command_exists node; then
        echo "✅ Node.js: $(node --version)"
        if check_node_version "16"; then
            echo "✅ Version: Compatible (>= 16)"
        else
            echo "⚠️  Version: May be too old (< 16)"
        fi
    else
        echo "❌ Node.js: Not found"
    fi

    # Environment check
    if [ -d "dega" ]; then
        echo "✅ Python environment: Created"
        if [ -n "${VIRTUAL_ENV:-}" ]; then
            echo "✅ Environment: Active"
        else
            echo "💡 Environment: Run 'source dega/bin/activate' to activate"
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
    if [ -d "dega" ] && [ -d "node_modules" ]; then
        success "Environment is ready! Run 'npm run dev' to start"
    else
        info "Run './scripts/setup.sh' to complete setup"
    fi
}

reset_environment() {
    warning "This will delete your current environment and all installed packages"
    if confirm "Continue?" "N"; then
        info "Cleaning up..."
        rm -rf dega node_modules .pytest_cache htmlcov .coverage 2>/dev/null || true
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
    echo "  • Python 3.10+ (https://python.org)"
    echo "  • Node.js 16+ (https://nodejs.org)"
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
        if check_python_version "3.10"; then
            log_success "Python version is compatible"
        else
            log_warning "Python version may be too old"
        fi
    elif command_exists python; then
        log_info "Found python: $(python --version)"
        if check_python_version "3.10"; then
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
        if check_node_version "16"; then
            log_success "Node.js version is compatible"
        else
            log_warning "Node.js version may be too old"
        fi
    else
        log_error "Node.js not found"
        exit 1
    fi

    # Create environment with detailed logging
    if [ -d "dega" ]; then
        log_warning "Virtual environment 'dega' already exists"
        if confirm "Do you want to recreate it?" "N"; then
            log_info "Removing existing environment..."
            rm -rf "dega"
        else
            log_info "Using existing virtual environment"
        fi
    fi

    if [ ! -d "dega" ]; then
        run_command "Creating virtual environment 'dega'" \
            python3 -m venv dega || python -m venv dega
    fi

    # Activate and install with detailed output
    log_step "Activating virtual environment"
    activate_python_env "dega"

    run_command "Upgrading pip" \
        pip install --upgrade pip

    run_command "Installing Python dependencies" \
        pip install -e ".[dev]"

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
    log_info "Activate environment with: source dega/bin/activate"
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
