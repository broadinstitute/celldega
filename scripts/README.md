# 🧬 Celldega Development Scripts

**Get started in 30 seconds:**

```bash
./scripts/setup.sh
source dega/bin/activate
pnpm run dev
```

That's it! 🎉

## What You Need

- **Python 3.10+** → [Download here](https://python.org/downloads/)
- **Node.js 16+** → [Download here](https://nodejs.org/)
- **pnpm 8+** → [Install guide](https://pnpm.io/installation)

## 🗂️ Scripts Overview

| Script     | What it does              | When to use            |
| ---------- | ------------------------- | ---------------------- |
| `setup.sh` | **Gets everything ready** | First time setup       |
| `test.sh`  | **Runs your tests**       | Before submitting work |

## Quick Commands

```bash
./scripts/setup.sh              # Set up everything
./scripts/setup.sh --status     # Check what's installed
./scripts/test.sh               # Run all tests
```

## Daily Workflow

```bash
# Start your work session
source dega/bin/activate
pnpm run dev

# Before committing your work
./scripts/test.sh
```

## ❤️‍🩹 Common Issues & Solutions

**"Permission denied"?**

```bash
chmod +x scripts/*.sh
```

**"Command not found"?**

- Make sure Python, Node.js, and pnpm are installed
- Check you're in the right folder (should see `pyproject.toml`)

**Something broken?**

```bash
./scripts/setup.sh --reset     # Clean slate
./scripts/setup.sh             # Fresh setup
```

**Need more details?**

```bash
./scripts/setup.sh --verbose   # See everything that happens
./scripts/test.sh --verbose    # Detailed test output
```

## 😎 For Advanced Users

<details>
<summary>Click to see advanced options</summary>

### Full Test Options

```bash
./scripts/test.sh python          # Python tests only
./scripts/test.sh js              # JavaScript tests only
./scripts/test.sh lint            # Code quality checks
./scripts/test.sh coverage       # Generate coverage report
./scripts/test.sh python tests/unit/  # Run specific directory
```

### Setup Options

```bash
./scripts/setup.sh --status      # Check environment status
./scripts/setup.sh --reset       # Clean install
./scripts/setup.sh --verbose     # Show all details
```

### Debugging

```bash
export VERBOSE=true              # Show detailed output
export DEBUG=true                # Show debug information
```

### pnpm Commands

```bash
pnpm install                     # Install dependencies
pnpm run dev                     # Start development server
pnpm run build                   # Build for production
pnpm run test:js                 # Run JavaScript tests
pnpm run lint:js                 # Lint JavaScript code
```

</details>

---

**🆘 Still stuck?** Check the main project README or ask for help!
