# Utility Scripts

Helper scripts for development, testing, and setup.

## Setup Scripts

### install_poppler.sh

Installs Poppler utilities (required for PDF processing).

```bash
./scripts/utilities/install_poppler.sh
```

Installs:
- On macOS: Uses Homebrew
- On Ubuntu/Debian: Uses apt
- On other Linux: Uses conda

## Testing Scripts

### quick_test.sh

Quick smoke test for API endpoints.

```bash
./scripts/utilities/quick_test.sh
```

Tests basic API connectivity and health checks.

### test_card_highlight.sh

Tests the card highlight feature in presenter mode.

```bash
./scripts/utilities/test_card_highlight.sh
```

Verifies that topic cards are properly highlighted when matched.

### test_swipe_feature.sh

Tests the swipe/slide navigation feature.

```bash
./scripts/utilities/test_swipe_feature.sh
```

Tests slide navigation controls and transitions.

## Notes

- All scripts should be run from the project root directory
- Some scripts require the backend to be running
- Check individual script headers for specific requirements
