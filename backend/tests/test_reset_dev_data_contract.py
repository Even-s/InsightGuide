"""Clean baseline reset script contracts."""

from pathlib import Path


def test_reset_dev_data_recreates_single_clean_demo_project_seed():
    script = Path("scripts/reset_dev_data.py").read_text(encoding="utf-8")

    assert "DEFAULT_DEMO_PROJECT_ID" in script
    assert "ensure_demo_project()" in script
    assert "--skip-demo-project" in script
    assert "ensure_default_user()" in script

    main_body = script.split("def main() -> None:", 1)[1]
    assert main_body.index("ensure_default_user()") < main_body.index("ensure_demo_project()")
