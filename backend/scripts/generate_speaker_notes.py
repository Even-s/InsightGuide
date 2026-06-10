"""
Generate speaker notes for slides from TopicCard suggested scripts.
"""

import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.models.slide import Slide
from app.models.topic_card import TopicCard
from sqlalchemy import func


def generate_speaker_notes():
    """Generate speaker notes from topic cards for all slides."""
    db = SessionLocal()

    try:
        # Get all slides that have topic cards
        slides_with_cards = db.query(Slide.id).join(TopicCard).group_by(Slide.id).all()
        slide_ids = [s[0] for s in slides_with_cards]

        print(f"找到 {len(slide_ids)} 張有 TopicCard 的投影片")

        updated_count = 0

        for slide_id in slide_ids:
            slide = db.query(Slide).filter(Slide.id == slide_id).first()
            if not slide:
                continue

            # Get all topic cards for this slide, ordered by order_index
            cards = db.query(TopicCard).filter(
                TopicCard.slide_id == slide_id
            ).order_by(TopicCard.order_index).all()

            # Combine suggested scripts
            speaker_notes_parts = []

            for i, card in enumerate(cards, 1):
                if card.suggested_script and card.suggested_script.strip():
                    # Add card title and script
                    importance_marker = "【重點】" if card.importance == "must" else "【建議】"
                    speaker_notes_parts.append(
                        f"{importance_marker} {card.title}\n{card.suggested_script.strip()}"
                    )

            if speaker_notes_parts:
                # Combine all parts with double newline
                speaker_notes = "\n\n".join(speaker_notes_parts)

                # Update slide
                slide.speaker_notes = speaker_notes
                updated_count += 1

                print(f"✓ 投影片 {slide.page_number}: 已生成演講稿 ({len(cards)} 張卡片, {len(speaker_notes)} 字元)")
            else:
                print(f"✗ 投影片 {slide.page_number}: 無可用的建議講稿")

        # Commit all changes
        db.commit()
        print(f"\n成功更新 {updated_count} 張投影片的演講稿")

    except Exception as e:
        db.rollback()
        print(f"錯誤: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_speaker_notes()
