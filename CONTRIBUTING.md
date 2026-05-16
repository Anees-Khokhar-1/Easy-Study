# Contributing to Easy-Study

## Before You Push

1. **Run tests locally:**
   ```bash
   pytest -v
   ```

2. **Format code:**
   ```bash
   black .
   isort .
   ```

3. **Check types:**
   ```bash
   mypy . --ignore-missing-imports
   ```

4. **Lint code:**
   ```bash
   flake8 .
   ```

## Pull Request Process
1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run all checks (see above)
4. Commit with clear messages
5. Push to GitHub
6. Create a Pull Request
7. Wait for CI/CD to pass ✅
8. Request review

## CI/CD Pipeline
Every push triggers our automated pipeline:

✅ Tests on Python 3.9-3.12
✅ Security scanning
✅ Code quality checks

All must pass before merging! 🛡️
