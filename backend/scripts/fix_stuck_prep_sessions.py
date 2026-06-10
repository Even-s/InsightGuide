#!/usr/bin/env python3
"""
Utility script to fix prep sessions that are stuck in 'preparing' status
when their corresponding deck has already been analyzed.

This can happen when:
1. The worker was restarted during analysis
2. The prep session update code failed
3. The prep session was created before the auto-update feature was added

Usage:
    python scripts/fix_stuck_prep_sessions.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import datetime
from app.db.session import SessionLocal
from app.models.prep_session import PrepSession
from app.models.deck import Deck
from app.models.topic_card import TopicCard
from sqlalchemy import and_


def fix_stuck_prep_sessions(dry_run: bool = False):
    """
    Find and fix prep sessions that are stuck in 'preparing' status
    but have completed analysis.
    """
    db = SessionLocal()

    try:
        # Find all prep sessions in 'preparing' status with analyzed decks
        query = db.query(PrepSession, Deck).join(
            Deck, PrepSession.deck_id == Deck.id
        ).filter(
            and_(
                PrepSession.status == "preparing",
                Deck.status == "analyzed"
            )
        )

        stuck_sessions = query.all()

        if not stuck_sessions:
            print("✅ No stuck prep sessions found!")
            return 0

        print(f"\n🔍 Found {len(stuck_sessions)} stuck prep session(s):\n")

        fixed_count = 0

        for prep_session, deck in stuck_sessions:
            # Count topic cards to verify analysis is complete
            card_count = db.query(TopicCard).filter(
                TopicCard.deck_id == deck.id
            ).count()

            print(f"📊 Prep Session: {prep_session.id}")
            print(f"   Deck: {deck.id} ({deck.title})")
            print(f"   Deck Status: {deck.status}")
            print(f"   Topic Cards: {card_count}")
            print(f"   Deck Created: {deck.created_at}")
            print(f"   Deck Updated: {deck.updated_at}")
            print(f"   PrepSession Created: {prep_session.created_at}")
            print(f"   PrepSession Updated: {prep_session.updated_at}")

            if dry_run:
                print(f"   [DRY RUN] Would update status: preparing → ready\n")
            else:
                prep_session.status = "ready"
                prep_session.updated_at = datetime.utcnow()
                db.commit()
                print(f"   ✅ Updated status: preparing → ready\n")
                fixed_count += 1

        if dry_run:
            print(f"\n[DRY RUN] Would fix {len(stuck_sessions)} prep session(s)")
        else:
            print(f"\n✅ Successfully fixed {fixed_count} prep session(s)")

        return fixed_count

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return -1
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix prep sessions stuck in 'preparing' status"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without making changes'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Fix Stuck Prep Sessions")
    print("=" * 70)

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made\n")

    result = fix_stuck_prep_sessions(dry_run=args.dry_run)

    sys.exit(0 if result >= 0 else 1)


if __name__ == "__main__":
    main()
