#!/bin/bash
# =============================================================================
# Shared Configuration Constants for Celldega Development Scripts
# Source this file: source scripts/config.sh
# =============================================================================

# =============================================================================
# Virtual Environment Configuration
# =============================================================================
readonly VENV_BASE_DIR="."
readonly VENV_NAME="dega"
readonly VENV_PATH="${VENV_BASE_DIR}/${VENV_NAME}"
# Display name for the registered Jupyter kernel so notebooks run on this env.
readonly KERNEL_DISPLAY_NAME="Python (${VENV_NAME})"

# =============================================================================
# Version Requirements
# =============================================================================
# Matches requires-python>=3.11 in pyproject.toml (point-cloud dependency stack).
readonly PYTHON_MIN_VERSION="3.11"
# Python the uv-managed env is built on. uv fetches a standalone CPython for
# this version (never Anaconda's), avoiding native-library (GLib/GDAL) clashes.
readonly PYTHON_VERSION="3.12"
readonly NODE_MIN_VERSION="16"
readonly NPM_MIN_VERSION="8"

# =============================================================================
# Download URLs
# =============================================================================
readonly PYTHON_DOWNLOAD_URL="https://python.org/downloads/"
readonly UV_DOWNLOAD_URL="https://docs.astral.sh/uv/getting-started/installation/"
readonly NODE_DOWNLOAD_URL="https://nodejs.org/"
readonly NPM_DOWNLOAD_URL="https://docs.npmjs.com/downloading-and-installing-node-js-and-npm"
readonly GIT_DOWNLOAD_URL="https://git-scm.com/"

# =============================================================================
# Package Installation Configuration
# =============================================================================
readonly PIP_INSTALL_ARGS="--upgrade pip --quiet"
readonly NPM_INSTALL_ARGS="--silent"
readonly PYTHON_PACKAGE_SPEC=".[dev,pre,multimodal]"

# =============================================================================
# Test Configuration
# =============================================================================
readonly DEFAULT_TEST_PATH="tests/"
readonly PYTHON_COV_TARGET="src/celldega"
readonly COVERAGE_REPORT_FILE="htmlcov/index.html"

# =============================================================================
# File and Directory Patterns
# =============================================================================
readonly PROJECT_FILES=("pyproject.toml" "package.json")
readonly CLEANUP_PATTERNS=("node_modules" ".pytest_cache" "htmlcov" ".coverage")

# =============================================================================
# npm Script Names
# =============================================================================
readonly NPM_TEST_JS_SCRIPT="test:js"
readonly NPM_LINT_JS_SCRIPT="lint:js"

# =============================================================================
# Common Messages
# =============================================================================
readonly MSG_SYSTEM_CHECK="Checking your system..."
readonly MSG_PYTHON_ENV_SETUP="Setting up Python environment..."
readonly MSG_PYTHON_PACKAGES="Installing Python packages..."
readonly MSG_JS_PACKAGES="Installing JavaScript packages..."
readonly MSG_DEV_TOOLS="Setting up development tools..."
readonly MSG_PYTHON_TESTS="Running Python tests..."
readonly MSG_JS_TESTS="Running JavaScript tests..."
readonly MSG_CODE_QUALITY="Checking code quality..."

# =============================================================================
# Error Messages
# =============================================================================
readonly ERR_PYTHON_NOT_FOUND="Python not found. Please install Python ${PYTHON_MIN_VERSION}+ from ${PYTHON_DOWNLOAD_URL}"
readonly ERR_UV_NOT_FOUND="uv not found. Install it with one of:
  curl -LsSf https://astral.sh/uv/install.sh | sh
  brew install uv
  pipx install uv
  More info: ${UV_DOWNLOAD_URL}"
readonly ERR_NODE_NOT_FOUND="Node.js not found. Please install Node.js ${NODE_MIN_VERSION}+ from ${NODE_DOWNLOAD_URL}"
readonly ERR_NPM_NOT_FOUND="npm not found. Please install npm:
  npm comes with Node.js installation
  More info: ${NPM_DOWNLOAD_URL}"
readonly ERR_PYTHON_OLD="Python version may be too old. Please ensure you have Python ${PYTHON_MIN_VERSION}+"
readonly ERR_NODE_OLD="Node.js version may be too old. Please ensure you have Node.js ${NODE_MIN_VERSION}+"
readonly ERR_NPM_OLD="npm version may be too old. Please ensure you have npm ${NPM_MIN_VERSION}+"
readonly ERR_PYTEST_NOT_FOUND="pytest not found. Run ./scripts/setup.sh to install dependencies"
readonly ERR_PACKAGE_JSON_NOT_FOUND="package.json not found"

# =============================================================================
# Success Messages
# =============================================================================
readonly MSG_SYSTEM_OK="System looks good!"
readonly MSG_PYTHON_ENV_CREATED="Created Python environment"
readonly MSG_PYTHON_PACKAGES_INSTALLED="Python packages installed"
readonly MSG_JS_PACKAGES_INSTALLED="JavaScript packages installed"
readonly MSG_DEV_TOOLS_READY="Development tools ready"
readonly MSG_PYTHON_TESTS_PASSED="Python tests passed"
readonly MSG_JS_TESTS_PASSED="JavaScript tests passed"
readonly MSG_CODE_QUALITY_PASSED="All code quality checks passed"
readonly MSG_ALL_TESTS_PASSED="🎉 All tests passed! Your code is ready"

# =============================================================================
# Help Text Components
# =============================================================================
readonly HELP_REQUIREMENTS_PYTHON="• Python ${PYTHON_MIN_VERSION}+ (${PYTHON_DOWNLOAD_URL})"
readonly HELP_REQUIREMENTS_NODE="• Node.js ${NODE_MIN_VERSION}+ (${NODE_DOWNLOAD_URL})"
readonly HELP_REQUIREMENTS_NPM="• npm ${NPM_MIN_VERSION}+ (${NPM_DOWNLOAD_URL})"
readonly HELP_REQUIREMENTS_GIT="• Git (${GIT_DOWNLOAD_URL})"

# =============================================================================
# Activation Instructions
# =============================================================================
readonly ACTIVATION_COMMAND="source ${VENV_PATH}/bin/activate"
readonly ACTIVATION_MSG="Activate environment with: ${ACTIVATION_COMMAND}"
