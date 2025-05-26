# Contributing to Celldega

Thank you for your interest in contributing to Celldega! 🧬

## 🚀 Quick Start (30 seconds)

```bash
git clone https://github.com/your-username/celldega.git
cd celldega
./scripts/setup.sh
source dega/bin/activate
npm run dev
```

That's it! Your development environment is ready. 🎉

## What You Need

- **Python 3.10+** → [Download here](https://python.org/downloads/)
- **Node.js 16+** → [Download here](https://nodejs.org/)
- **Git** → [Download here](https://git-scm.com/)

## 🔄 Daily Development Workflow

### 1. Start Your Session
```bash
source dega/bin/activate    # Activate environment
npm run dev                 # Start development server
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

## 🧪 Testing Made Simple

```bash
./scripts/test.sh           # Run everything
./scripts/test.sh python    # Python tests only
./scripts/test.sh js        # JavaScript tests only
./scripts/test.sh coverage  # Generate coverage report
```

### Writing Tests

**Python (pytest)**
```python
# tests/unit/test_my_feature.py
from celldega.utils import my_function

def test_my_function():
    result = my_function('input')
    assert result == 'expected'
```

**JavaScript (Jest)**
```javascript
// js/__tests__/myFeature.test.js
import { myFunction } from '../utils/myFeature.js';

test('should handle basic case', () => {
  expect(myFunction('input')).toBe('expected');
});
```

## 🎨 Code Style (Automatic)

**No need to worry about formatting!** Our pre-commit hooks automatically:
- ✅ Format Python code with Ruff
- ✅ Format JavaScript code with Prettier
- ✅ Fix linting issues
- ✅ Check for common mistakes

Just write code and commit - we'll make it pretty.

### Naming Conventions
- **Python**: `snake_case` functions, `PascalCase` classes
- **JavaScript**: `camelCase` functions, `PascalCase` classes
- **Files**: `my_module.py`, `myComponent.js`

## 📝 Commit Messages

Use these prefixes for automatic versioning:

```bash
git commit -m "feat: add new clustering algorithm"     # New feature
git commit -m "fix: resolve data loading issue"       # Bug fix
git commit -m "docs: update API documentation"        # Documentation
git commit -m "test: add unit tests for visualization" # Tests
```

## 🐛 Reporting Issues

**Found a bug?** Use our issue templates:

- 🐛 **Bug Report**: Include your environment and steps to reproduce
- ✨ **Feature Request**: Describe what you'd like to see
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

### Common Issues

**"Permission denied"**
```bash
chmod +x scripts/*.sh
```

**"Python/Node.js not found"**
- Install from links above
- Check versions: `python --version`, `node --version`

**"Import errors"**
```bash
./scripts/setup.sh             # Reinstall dependencies
```

**"Tests failing"**
```bash
./scripts/test.sh --verbose    # See detailed error messages
```

### Still Stuck?
- 💬 [GitHub Discussions](https://github.com/broadinstitute/celldega/discussions) - Ask questions
- 🐛 [GitHub Issues](https://github.com/broadinstitute/celldega/issues) - Report bugs
- 📧 Contact maintainers directly

## 🏗️ Development Environment Details

<details>
<summary>Click for advanced setup options</summary>

### Custom Environment Name
```bash
./scripts/setup.sh --env-name my-celldega-env
```

### Development Server Options
```bash
npm run dev                 # Standard development
npm run dev:watch          # Watch mode with hot reload
npm run build              # Production build
npm run serve              # Serve production build
```

### Testing Options
```bash
pytest tests/unit/         # Specific test directory
pytest -k "test_clustering" # Tests matching pattern
pytest --cov-report=html   # HTML coverage report
npm run test:js:watch      # JavaScript tests in watch mode
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

## 🤝 Code of Conduct

We're building something amazing together! Please be:
- 🤝 **Respectful** - Everyone was new once
- 🌍 **Inclusive** - Welcome diverse perspectives
- 🏗️ **Constructive** - Focus on solutions
- 🎓 **Educational** - Help others learn

---

**Ready to contribute?** Fork the repo and dive in! We can't wait to see what you build. 🚀

*Need help?* Don't hesitate to reach out - we're here to help you succeed!
