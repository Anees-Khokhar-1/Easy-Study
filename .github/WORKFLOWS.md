# CI/CD Workflows

## Python CI/CD Pipeline

This workflow automatically runs on every push to `main` and pull requests.

### Jobs

#### 1. **Test** (Matrix: Python 3.9, 3.10, 3.11, 3.12)
- Sets up Python environment
- Installs dependencies
- Runs code formatting check (Black)
- Runs import sorting (isort)
- Runs type checking (mypy)
- Runs linting (Flake8)
- Runs unit tests with coverage (pytest)
- Uploads coverage to Codecov

#### 2. **Security**
- Runs Bandit for security vulnerabilities
- Checks dependencies with Safety

#### 3. **Code Quality**
- Runs Pylint for code analysis
- Analyzes complexity with Radon
- Generates maintainability index

#### 4. **Notify**
- Reports final workflow status

### View Results

- Actions Dashboard: https://github.com/Anees-Khokhar-1/Easy-Study/actions
- Latest Workflow: https://github.com/Anees-Khokhar-1/Easy-Study/actions/workflows/python-ci.yml

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Run linting
flake8 .

# Run type checking
mypy . --ignore-missing-imports

# Run security scan
bandit -r .
```

### Requirements
- Python 3.9+
- pytest
- black
- isort
- mypy
- flake8
- bandit
- safety
- pylint
- radon

All are auto-installed by the workflow.
