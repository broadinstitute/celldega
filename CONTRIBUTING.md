# Contributing to Celldega

Thank you for your interest in contributing to Celldega! 🧬

## What You Need

- **Python 3.10+** → [Download here](https://python.org/downloads/)
- **Node.js 16+** → [Download here](https://nodejs.org/)
- **pnpm 8+** → [Install guide](https://pnpm.io/installation)
- **Git** → [Download here](https://git-scm.com/)

## 🚀 Quick Start (one-time!)

```bash
# Clone Celldega repo
git clone https://github.com/broadinstitute/celldega.git
cd celldega

# Setup everything: Python venv, install dependencies, pre-commit hooks
bash ./scripts/setup.sh
```

That's it! Your development environment is ready. 🎉

## 🔄 Daily Development Workflow

### 1. Start Your Session

```bash
source dega/bin/activate    # Activate environment
pnpm run dev                # Start development server
```

### 2. Make Your Changes

- Write clear, descriptive code
- Add tests for new features
- Test in Jupyter: `jupyter lab examples/`

### 3. Before Committing

```bash
./scripts/test.sh           # Run all tests
git commit -m "feat: your amazing feature"
```

**That's the entire workflow!** Our automation handles formatting, linting, and quality checks.

## 🛠️ Project Configuration & Tooling

Understanding the project's tooling helps you contribute more effectively. Here's what's configured where:

| File/Directory                  | Purpose                  | Tools Configured                                        |
| ------------------------------- | ------------------------ | ------------------------------------------------------- |
| **🔄 CI/CD & Automation**       |
| `.github/workflows/ci.yml`      | Continuous Integration   | pytest, Jest, ESLint, Prettier, Ruff, Safety, Bandit    |
| `.github/dependabot.yml`        | Dependency updates       | Automated Python, pnpm, and GitHub Actions updates      |
| `.pre-commit-config.yaml`       | Git hooks                | Ruff (Python), Prettier, ESLint, basic file checks      |
| **🐍 Python Configuration**     |
| `pyproject.toml`                | Python package config    | pytest, Ruff (linting + formatting), build system       |
| **🌐 JavaScript Configuration** |
| `package.json`                  | JavaScript dependencies  | Jest (testing), ESLint (linting), Prettier (formatting) |
| `eslint.config.js`              | JavaScript linting rules | ESLint with import ordering, code quality rules         |
| `jest.setup.js`                 | Test environment setup   | Jest with jsdom, testing-library                        |
| **💻 Development Scripts**      |
| `scripts/setup.sh`              | Environment setup        | Python venv, pnpm install, pre-commit hooks             |
| `scripts/test.sh`               | Test runner              | pytest, Jest, linting checks                            |
| `scripts/utils.sh`              | Shared utilities         | Helper functions for scripts                            |
| **👷🏻 Build & Bundling**         |
| `build.js`                      | JavaScript bundling      | esbuild with WASM support                               |

### What Runs Where

**On Every Commit (Pre-commit Hooks):**

- ✅ Ruff formats and lints Python code
- ✅ Prettier formats JavaScript/JSON/YAML
- ✅ ESLint checks JavaScript code quality
- ✅ Basic file checks (trailing whitespace, merge conflicts)

**On Every Push/PR (CI Pipeline):**

- 🧪 **Testing**: pytest (Python), Jest (JavaScript)
- 🔍 **Code Quality**: Ruff, ESLint, Prettier checks
- 🔒 **Security**: Safety (Python deps), Bandit (code analysis)
- 📦 **Build**: Package building and installation tests
- 🚀 **Release**: Automated PyPI publishing on tags

## 🧪 Testing

### 1. Run Tests

```bash
./scripts/test.sh           # Run everything
./scripts/test.sh python    # Python tests only
./scripts/test.sh js        # JavaScript tests only
./scripts/test.sh coverage  # Generate coverage report
```

### 2. Writing Tests

**🐍 Python (pytest) - Add tests like this:**

```python
# tests/unit/test_my_feature.py
from celldega.utils import my_function

def test_my_function():
    result = my_function('input')
    assert result == 'expected'
```

**🌐 JavaScript (Jest) - Add tests like this:**

```javascript
// js/__tests__/myFeature.test.js
import { myFunction } from '../utils/myFeature.js';

test('should handle basic case', () => {
  expect(myFunction('input')).toBe('expected');
});
```

## 🎨 Code Style

**No need to worry about formatting!** Our pre-commit hooks automatically:

- ✅ Format Python code with Ruff
- ✅ Format JavaScript code with Prettier
- ✅ Fix linting issues
- ✅ Check for common mistakes

### Naming Conventions

- **Python**: `snake_case` functions, `PascalCase` classes
- **JavaScript**: `camelCase` functions, `PascalCase` classes
- **Files**: `my_module.py`, `myComponent.js`
- **Type Annotations**: Always add proper typing for better code clarity and IDE support

<details>
<summary><strong>Python Typing Examples</strong></summary>

```python
from typing import List, Optional, Dict, Any
import pandas as pd

def process_cell_data(
    cells: pd.DataFrame,
    cluster_labels: Optional[List[int]] = None,
    metadata: Dict[str, Any] = {}
) -> pd.DataFrame:
    """Process cell data with optional clustering information."""
    # Implementation here
    return processed_cells
```

</details>

<details>
<summary><strong>JavaScript JSDoc Examples</strong></summary>

```javascript
/**
 * Render cells on deck.gl layer with interactive selection
 * @param {Array<{x: number, y: number, cluster: number}>} cellData - Array of cell coordinates
 * @param {Object} options - Rendering options
 * @param {string} options.colorBy - Property to color cells by
 * @param {boolean} options.interactive - Enable cell selection
 * @returns {Promise<DeckGLLayer>} Configured deck.gl layer
 */
async function renderCellLayer(cellData, options = {}) {
  // Implementation here
  return layer;
}
```

</details>

<details>
<summary><strong>TypeScript Examples</strong></summary>

```typescript
interface CellData {
  x: number;
  y: number;
  cluster: number;
  [key: string]: any;
}

interface RenderOptions {
  colorBy?: string;
  interactive?: boolean;
  opacity?: number;
}

async function renderCellLayer(
  cellData: CellData[],
  options: RenderOptions = {}
): Promise<DeckGLLayer> {
  // Implementation here
  return layer;
}
```

</details>

## 📝 Commit Message Structure

Use these prefixes:

```bash
# STRUCTURE: "activity(module): ..."

git commit -m "feat(deck-gl): implement interactive cell selection widget" # New Feature
git commit -m "optim(deck-gl): optimize WebGL shader compilation for speed" # Optimization
git commit -m "fix(deck-gl): resolve memory leak in large dataset rendering" # Bug fix
git commit -m "hotfix(deck-gl): 🔴 resolve data loading issue"       # Hot bug fix (needs urgent rework -> create GitHub/Jira issue)
git commit -m "docs(deck-gl): add WebGL troubleshooting guide for users" # Documentation
git commit -m "test(deck-gl): add integration tests for widget lifecycle" # tests
git commit -m "infra(jest): configure coverage reporting for CI pipeline" # Infrastructure

```

## 🐛 Reporting Issues

**Found a bug?** Use our issue templates:

- 🐛 **Bug Report**: Include your environment and steps to reproduce
- 🎁 **Feature Request**: Describe what you'd like to see
- 📚 **Documentation**: Suggest improvements to docs or examples

## 💡 Contribution Ideas

### For Biology Researchers

- 🧬 Add example datasets from your research
- 📊 Create tutorial notebooks
- 📝 Improve documentation with domain expertise
- 🧪 Test with real-world data and report issues

### For Developers

- ⚡ Optimize performance for large datasets
- 🎨 Improve visualization components
- 🔧 Add new analysis algorithms
- 🌐 Enhance web integration

### For Everyone

- 📖 Fix typos and improve clarity
- 🧪 Add tests for edge cases
- 🎯 Improve user experience
- 🤝 Help others in discussions

## 🆘 Getting Help

**Stuck?** Here's how to get unstuck:

### Quick Fixes

```bash
./scripts/setup.sh --status    # Check what's wrong
./scripts/setup.sh --reset     # Nuclear option - fresh start
./scripts/setup.sh --verbose   # See detailed output
```

<details>
<summary><strong>Common Issues</strong></summary>

**"Permission denied"**

```bash
chmod +x scripts/*.sh
```

**"Python/Node.js/pnpm not found"**

- Install from links above
- Check versions: `python --version`, `node --version`, `pnpm --version`

**"pnpm: command not found"**

```bash
npm install -g pnpm
# or
corepack enable
```

**"Import errors"**

```bash
./scripts/setup.sh             # Reinstall dependencies
```

**"Tests failing"**

```bash
./scripts/test.sh --verbose    # See detailed error messages
```

**"node_modules missing"**

```bash
pnpm install                   # Reinstall JavaScript dependencies
```

</details>

### Still Stuck?

- 💬 [GitHub Discussions](https://github.com/broadinstitute/celldega/discussions) - Ask questions
- 🐛 [GitHub Issues](https://github.com/broadinstitute/celldega/issues) - Report bugs
- 📧 Contact maintainers directly

## 🏗️ Development Environment Details

<details>
<summary>Click for advanced setup options</summary>

### Custom Environment Name

```bash
bash ./scripts/setup.sh --env-name my-celldega-env
```

### Development Server Options

```bash
pnpm run dev                # Standard development
pnpm run dev:watch         # Watch mode with hot reload
pnpm run build             # Production build
pnpm run serve             # Serve production build
```

### Testing Options

```bash
pytest tests/unit/         # Specific test directory
pytest -k "test_clustering" # Tests matching pattern
pytest --cov-report=html   # HTML coverage report
pnpm run test:js:watch     # JavaScript tests in watch mode
```

### pnpm Commands

```bash
pnpm install               # Install all dependencies
pnpm install --frozen-lockfile  # Install from lockfile (CI)
pnpm run test:js          # Run JavaScript tests
pnpm run lint:js          # Lint JavaScript code
pnpm run format:js        # Format JavaScript code
pnpm outdated             # Check for outdated packages
pnpm update               # Update dependencies
```

### VS Code Setup

Install these extensions for the best experience:

- **Python** - Core Python support
- **Ruff** - Python linting and formatting
- **ESLint** - JavaScript linting
- **Prettier** - Code formatting
- **Jupyter** - Notebook support

</details>

## 🏆 Recognition

Contributors are celebrated in:

- 📋 `CONTRIBUTORS.md` file
- 📈 GitHub contributors graph
- 📰 Release notes for significant contributions
- 🎉 Special mentions in community updates

## 🌟 Pro Tips

1. **Start small** - Fix documentation or add a simple test first
2. **Ask early** - Use Discussions to validate ideas before coding
3. **Test thoroughly** - Include edge cases and error conditions
4. **Document changes** - Help future contributors understand your work
5. **Be patient** - We review all contributions carefully
6. **Use pnpm efficiently** - It's faster than npm and saves disk space!

## 🤝 Code of Conduct

We're building something amazing together! Please be:

- 🤝 **Respectful** - Everyone was new once
- 🌍 **Inclusive** - Welcome diverse perspectives
- 🏗️ **Constructive** - Focus on solutions
- 🎓 **Educational** - Help others learn

---

**Ready to contribute?** Fork the repo and dive in! We can't wait to see what you build. 🚀

_Need help?_ Don't hesitate to reach out - we're here to help you succeed!
