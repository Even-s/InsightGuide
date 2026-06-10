"""
Clear all presentation data from the database.
WARNING: This will delete all decks, slides, topic cards, sessions, and utterances.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.deck import Deck
from app.models.slide import Slide
from app.models.topic_card import TopicCard
from app.models.prep_session import PrepSession
from app.models.presentation_session import PresentationSession, PresentationCardState
from app.models.utterance import Utterance


def clear_all_data():
    """Clear all presentation data from the database."""
    db = SessionLocal()

    try:
        # Count before deletion
        deck_count = db.query(Deck).count()
        slide_count = db.query(Slide).count()
        card_count = db.query(TopicCard).count()
        prep_session_count = db.query(PrepSession).count()
        presentation_session_count = db.query(PresentationSession).count()
        card_state_count = db.query(PresentationCardState).count()
        utterance_count = db.query(Utterance).count()

        print("目前資料庫中的數據:")
        print(f"  - Decks: {deck_count}")
        print(f"  - Slides: {slide_count}")
        print(f"  - TopicCards: {card_count}")
        print(f"  - PrepSessions: {prep_session_count}")
        print(f"  - PresentationSessions: {presentation_session_count}")
        print(f"  - PresentationCardStates: {card_state_count}")
        print(f"  - Utterances: {utterance_count}")
        print()

        # Delete in order to respect foreign key constraints
        print("開始清除資料...")

        # Delete utterances first
        deleted = db.query(Utterance).delete()
        print(f"✓ 已刪除 {deleted} 筆 Utterances")

        # Delete card states
        deleted = db.query(PresentationCardState).delete()
        print(f"✓ 已刪除 {deleted} 筆 PresentationCardStates")

        # Delete presentation sessions
        deleted = db.query(PresentationSession).delete()
        print(f"✓ 已刪除 {deleted} 筆 PresentationSessions")

        # Delete prep sessions
        deleted = db.query(PrepSession).delete()
        print(f"✓ 已刪除 {deleted} 筆 PrepSessions")

        # Delete topic cards
        deleted = db.query(TopicCard).delete()
        print(f"✓ 已刪除 {deleted} 筆 TopicCards")

        # Delete slides
        deleted = db.query(Slide).delete()
        print(f"✓ 已刪除 {deleted} 筆 Slides")

        # Delete decks
        deleted = db.query(Deck).delete()
        print(f"✓ 已刪除 {deleted} 筆 Decks")

        # Commit all deletions
        db.commit()
        print()
        print("✅ 所有資料已成功清除！")

    except Exception as e:
        db.rollback()
        print(f"❌ 錯誤: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("⚠️  警告: 此操作將刪除所有投影片、卡片和相關數據！")
    print()

    # Confirm before deletion
    response = input("確定要繼續嗎? (輸入 'YES' 確認): ")

    if response.strip() == "YES":
        clear_all_data()
    else:
        print("操作已取消")
