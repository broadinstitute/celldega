#!/bin/bash
# =============================================================================
# 🧪 Celldega Testing - Run your tests with confidence
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
# Test Functions
# =============================================================================

run_python_tests() {
    local test_path="${1:-$DEFAULT_TEST_PATH}"
    local with_coverage="${2:-false}"

    step "$MSG_PYTHON_TESTS"

    # Ensure we're in the Python environment
    activate_python_env "$VENV_PATH"

    if ! command_exists pytest; then
        error "$ERR_PYTEST_NOT_FOUND"
        exit 1
    fi

    if [ "$with_coverage" = "true" ]; then
        pytest "$test_path" \
            --cov="$PYTHON_COV_TARGET" \
            --cov-report=html \
            --cov-report=term \
            -v
    else
        pytest "$test_path" -v
    fi

    success "$MSG_PYTHON_TESTS_PASSED"
}

run_js_tests() {
    step "$MSG_JS_TESTS"

    if [ ! -f "package.json" ]; then
        error "$ERR_PACKAGE_JSON_NOT_FOUND"
        exit 1
    fi

    # Check if test script exists
    if npm run | grep -q "$NPM_TEST_JS_SCRIPT"; then
        npm run "$NPM_TEST_JS_SCRIPT"
        success "$MSG_JS_TESTS_PASSED"
    else
        warning "No JavaScript test script found in package.json"
        info "Available npm scripts:"
        npm run 2>/dev/null | grep -E "^\s+" || echo "  No scripts found"
    fi
}

run_linting() {
    step "$MSG_CODE_QUALITY"

    local issues=0

    # Python linting
    if command_exists ruff; then
        if ruff check src/ --quiet && ruff format --check src/ --quiet; then
            success "Python code looks good"
        else
            warning "Python linting issues found"
            issues=1
        fi
    else
        warning "Ruff not found - install with: pip install ruff"
    fi

    # JavaScript linting
    if npm run | grep -q "$NPM_LINT_JS_SCRIPT"; then
        if npm run "$NPM_LINT_JS_SCRIPT" --silent; then
            success "JavaScript code looks good"
        else
            warning "JavaScript linting issues found"
            issues=1
        fi
    else
        warning "No JavaScript linting script found"
    fi

    if [ $issues -eq 0 ]; then
        success "$MSG_CODE_QUALITY_PASSED"
    fi
}

run_all_tests() {
    simple_banner "Running all tests..."

    run_python_tests
    run_js_tests
    run_linting

    echo
    success "$MSG_ALL_TESTS_PASSED"
}

run_coverage() {
    simple_banner "Running tests with coverage..."

    run_python_tests "$DEFAULT_TEST_PATH" "true"

    if [ -f "$COVERAGE_REPORT_FILE" ]; then
        echo
        success "Coverage report generated: $COVERAGE_REPORT_FILE"

        # Try to open coverage report
        if command_exists open; then
            open "$COVERAGE_REPORT_FILE"
        elif command_exists xdg-open; then
            xdg-open "$COVERAGE_REPORT_FILE"
        else
            info "Open $COVERAGE_REPORT_FILE in your browser to view the report"
        fi
    fi
}

# =============================================================================
# Verbose Mode (Advanced Users)
# =============================================================================

verbose_all_tests() {
    show_banner "Celldega Testing Suite"

    log_info "🧪 Running comprehensive test suite..."

    # Ensure we're in the right place
    ensure_project_root

    # Check if environment is ready
    if [ -z "${VIRTUAL_ENV:-}" ]; then
        log_warning "No virtual environment detected"
        if [ -d "$VENV_PATH" ]; then
            log_info "Activating $VENV_NAME virtual environment..."
            activate_python_env "$VENV_PATH"
        else
            log_error "No virtual environment found. Please run ./scripts/setup.sh first"
            exit 1
        fi
    fi

    # Install test dependencies if needed
    if ! command_exists pytest; then
        log_info "Installing test dependencies..."
        pip install -e "$PYTHON_PACKAGE_SPEC"
    fi

    # Run tests with detailed output
    run_command "Running Python tests" \
        pytest "$DEFAULT_TEST_PATH" -v

    # Run JavaScript tests
    log_step "Running JavaScript tests"
    if npm run | grep -q "$NPM_TEST_JS_SCRIPT"; then
        npm run "$NPM_TEST_JS_SCRIPT"
        log_success "JavaScript tests completed"
    else
        log_warning "No JavaScript test script found"
    fi

    # Run linting
    log_step "Running code quality checks"

    if command_exists ruff; then
        run_command "Running Python linting" \
            ruff check src/
        run_command "Checking Python formatting" \
            ruff format --check src/
    else
        log_warning "ruff not found, skipping Python linting"
    fi

    if npm run | grep -q "$NPM_LINT_JS_SCRIPT"; then
        run_command "Running JavaScript linting" \
            npm run "$NPM_LINT_JS_SCRIPT"
    else
        log_warning "No JavaScript linting script found"
    fi

    log_success "🎉 All tests completed successfully!"
}

# =============================================================================
# Help and Usage
# =============================================================================

show_help() {
    echo "🧪 Celldega Testing"
    echo
    echo "Quick commands:"
    echo "  ./scripts/test.sh                     # Run all tests"
    echo "  ./scripts/test.sh python             # Python tests only"
    echo "  ./scripts/test.sh js                 # JavaScript tests only"
    echo "  ./scripts/test.sh lint               # Code quality checks"
    echo "  ./scripts/test.sh coverage           # Tests with coverage report"
    echo
    echo "Options:"
    echo "  ./scripts/test.sh --verbose          # Detailed output"
    echo "  ./scripts/test.sh --help             # This help"
    echo
    echo "Examples:"
    echo "  ./scripts/test.sh python tests/unit/ # Run specific test directory"
    echo
    echo "Pro tip: Run tests before committing your work!"
}

# =============================================================================
# Script Entry Point
# =============================================================================

# Check we're in the right place
ensure_project_root

# Handle arguments
case "${1:-}" in
    "" | "all")
        run_all_tests
        ;;
    "python")
        if [ -n "$2" ]; then
            run_python_tests "$2"
        else
            run_python_tests
        fi
        ;;
    "js" | "javascript")
        run_js_tests
        ;;
    "lint")
        run_linting
        ;;
    "coverage")
        run_coverage
        ;;
    "--verbose")
        export VERBOSE=true
        verbose_all_tests
        ;;
    "--help" | "-h" | "help")
        show_help
        ;;
    *)
        error "Unknown command: $1"
        echo "Run './scripts/test.sh --help' for usage"
        exit 1
        ;;
esac
