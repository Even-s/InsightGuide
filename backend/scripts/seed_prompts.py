"""Seed prompt templates from current codebase into the prompt registry."""
import sys
sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.services.prompt_registry_service import prompt_registry_service
from app.services.prompt_seed_data import PROMPT_SEEDS as PROMPTS


def seed():
    db = SessionLocal()
    try:
        for p in PROMPTS:
            prompt_registry_service.seed_template(
                db,
                key=p["key"],
                name=p["name"],
                category=p["category"],
                system_prompt=p["system_prompt"],
                user_prompt_template=p.get("user_prompt_template"),
                description=p.get("description"),
                model=p.get("model"),
                risk_level=p.get("risk_level", "medium"),
                service_file=p.get("service_file"),
                service_function=p.get("service_function"),
                input_variables=p.get("input_variables"),
                output_format=p.get("output_format"),
            )
            print(f"  Seeded: {p['key']}")
        print(f"\nDone. {len(PROMPTS)} prompts seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
