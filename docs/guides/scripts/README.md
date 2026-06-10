# Scripts Directory

Helper scripts for SlideCue development, testing, and deployment.

## Directory Structure

```
scripts/
├── integration_tests/    # End-to-end milestone tests
│   ├── test_milestone2.py
│   ├── test_milestone4.py
│   ├── test_milestone5.py
│   ├── test_milestone5_simple.py
│   └── test_bullet_points.py
└── utilities/            # Development utilities
    ├── install_poppler.sh
    ├── quick_test.sh
    ├── test_card_highlight.sh
    └── test_swipe_feature.sh
```

## Quick Links

- **[Integration Tests](INTEGRATION_TESTS.md)** - Full milestone test suites
- **[Utilities](UTILITIES.md)** - Setup and dev helper scripts

## Usage

All scripts should be run from the project root directory:

```bash
# Integration tests (require backend running)
python scripts/integration_tests/test_milestone2.py

# Utility scripts
./scripts/utilities/install_poppler.sh
./scripts/utilities/quick_test.sh
```

## Prerequisites

Most scripts require:
- Backend server running (`http://localhost:8001`)
- Infrastructure services (PostgreSQL, Redis, MinIO)
- OpenAI API key configured

See individual README files for specific requirements.
