# Contributing to Celldega

Thank you for your interest in contributing to Celldega! 🎉

## 🚀 Quick Start

1. **Fork & Clone**
   ```bash
   git clone https://github.com/your-username/celldega.git
   cd celldega
   ```

2. **Setup Development Environment**
   ```bash
   python -m venv dega
   source dega/bin/activate  # Windows: dega\Scripts\activate
   pip install -e ".[dev]"
   npm install
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

4. **Verify Setup**
   ```bash
   npm test && npm run lint
   ```

## 🔄 Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-amazing-feature
   ```

2. **Make your changes**
   - Write code with clear, descriptive commits
   - Follow existing code style (auto-formatted on save)
   - Add tests for new functionality

3. **Test your changes**
   ```bash
   npm test           # Run all tests
   npm run lint       # Check code quality
   npm run format     # Format code
   ```

4. **Commit with conventional commits**
   ```bash
   git commit -m "feat: add amazing new feature"
   git commit -m "fix: resolve issue with data loading"
   git commit -m "docs: update API documentation"
   ```

### Pre-commit Automation

Our pre-commit hooks automatically:
- ✅ Format Python code with Ruff
- ✅ Format JavaScript code with Prettier
- ✅ Lint both languages
- ✅ Check for merge conflicts
- ✅ Fix trailing whitespace

If pre-commit finds issues, it will fix them automatically. Just review and commit again.

## 🧪 Testing

### Running Tests

```bash
# All tests
npm test

# JavaScript only
npm run test:js
npm run test:js:watch    # Watch mode

# Python only
pytest
pytest --cov=src/celldega --cov-report=html
```

### Writing Tests

#### JavaScript (Jest)
```javascript
// js/__tests__/myFeature.test.js
import { myFunction } from '../utils/myFeature.js';

describe('myFunction', () => {
  test('should handle basic case', () => {
    expect(myFunction('input')).toBe('expected');
  });
});
```

#### Python (pytest)
```python
# tests/unit/test_my_feature.py
import pytest
from celldega.utils import my_function

def test_my_function():
    result = my_function('input')
    assert result == 'expected'
```

## 📋 Code Style

### Automatic Formatting
- **Python**: Ruff (4 spaces, double quotes)
- **JavaScript**: Prettier + ESLint (2 spaces, double quotes)

Both languages auto-format on save in VS Code.

### Naming Conventions
- **Python**: `snake_case` for functions/variables, `PascalCase` for classes
- **JavaScript**: `camelCase` for functions/variables, `PascalCase` for classes
- **Files**: `snake_case.py`, `camelCase.js`

## 🐛 Reporting Issues

Use our issue templates:
- **Bug Report**: Include environment, reproduction steps, error messages
- **Feature Request**: Describe the feature and use case
- **Documentation**: Improvements to docs or examples

## 📚 Documentation

- Update docstrings for new Python functions
- Update JSDoc comments for new JavaScript functions
- Add examples to relevant notebooks
- Update README if needed

## 🚀 Release Process

We use semantic versioning and automated releases:
- `feat:` → minor version bump
- `fix:` → patch version bump
- `BREAKING CHANGE:` → major version bump

## 💡 Tips for Success

1. **Start small** - Fix a bug or add a small feature first
2. **Ask questions** - Use GitHub Discussions for design questions
3. **Check existing issues** - Someone might be working on something similar
4. **Test thoroughly** - Include edge cases and error conditions
5. **Document changes** - Help others understand your contribution

## 🏆 Recognition

Contributors are recognized in:
- `CONTRIBUTORS.md` file
- GitHub contributors graph
- Release notes for significant contributions

## 🤝 Code of Conduct

Be respectful, inclusive, and constructive. We're building something amazing together!

---

**Need help?** Open a [GitHub Discussion](https://github.com/broadinstitute/celldega/discussions) or reach out to the maintainers.
