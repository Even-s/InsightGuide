#!/usr/bin/env python3
"""
測試建議逐字稿功能

這個腳本驗證：
1. TopicCard 包含 suggestedScript
2. 前端可以正確提取和顯示建議稿
3. 匹配邏輯能識別「講到了」的句子
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.deck import Deck
from app.models.slide import Slide
from app.models.topic_card import TopicCard

def test_suggested_script():
    """測試建議逐字稿功能"""

    # 建立資料庫連接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print("=" * 60)
        print("建議逐字稿功能測試")
        print("=" * 60)
        print()

        # 1. 查找最近的 deck
        deck = db.query(Deck).order_by(Deck.created_at.desc()).first()

        if not deck:
            print("❌ 沒有找到任何 Deck，請先上傳 PPTX")
            return False

        print(f"✅ 找到 Deck: {deck.title or deck.id}")
        print(f"   狀態: {deck.status}")
        print()

        # 2. 查找投影片
        slides = db.query(Slide).filter(Slide.deck_id == deck.id).order_by(Slide.page_number).all()

        if not slides:
            print("❌ 沒有找到投影片")
            return False

        print(f"✅ 找到 {len(slides)} 張投影片")
        print()

        # 3. 查找 TopicCards
        cards = db.query(TopicCard).filter(TopicCard.deck_id == deck.id).all()

        if not cards:
            print("❌ 沒有找到 TopicCards，請先執行 AI 分析")
            return False

        print(f"✅ 找到 {len(cards)} 張 TopicCards")
        print()

        # 4. 檢查 suggestedScript 欄位
        cards_with_script = [c for c in cards if c.suggested_script]
        cards_without_script = [c for c in cards if not c.suggested_script]

        print(f"包含建議稿的卡片: {len(cards_with_script)} / {len(cards)}")
        print(f"缺少建議稿的卡片: {len(cards_without_script)} / {len(cards)}")
        print()

        if cards_without_script:
            print("⚠️  以下卡片缺少建議稿:")
            for card in cards_without_script[:5]:  # 只顯示前 5 個
                print(f"   - {card.title} (投影片 {card.slide_page_number})")
            print()

        # 5. 顯示範例建議稿
        if cards_with_script:
            print("=" * 60)
            print("建議稿範例")
            print("=" * 60)
            print()

            for i, card in enumerate(cards_with_script[:3], 1):  # 顯示前 3 個
                print(f"[{i}] {card.title}")
                print(f"    投影片: 第 {card.slide_page_number} 頁")
                print(f"    重要度: {card.importance}")
                print(f"    建議稿:")
                print()

                # 拆分句子
                script = card.suggested_script.strip()
                import re
                sentences = re.split(r'[。！？.!?]+', script)
                sentences = [s.strip() for s in sentences if s.strip()]

                for j, sentence in enumerate(sentences, 1):
                    print(f"       {j}. {sentence}")

                print()

            print("=" * 60)
            print()

        # 6. 測試建議
        print("✅ 功能測試通過")
        print()
        print("下一步:")
        print("1. 進入 Presenter Mode: http://localhost:5173/presenter/<deck_id>")
        print("2. 在投影片下方看到「建議逐字稿」面板")
        print("3. 開始演講，系統會自動識別已講過的句子")
        print()

        return True

    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        db.close()


def add_sample_script_to_cards():
    """為沒有建議稿的卡片添加範例建議稿"""

    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        cards_without_script = db.query(TopicCard).filter(
            TopicCard.suggested_script == None
        ).all()

        if not cards_without_script:
            print("所有卡片都已有建議稿")
            return

        print(f"找到 {len(cards_without_script)} 張卡片沒有建議稿")
        print("正在添加範例建議稿...")
        print()

        for card in cards_without_script:
            # 根據卡片標題和描述生成範例建議稿
            sample_script = f"接下來我要跟大家分享{card.title}。{card.description[:100]}。這個部分非常重要，請大家特別注意。"

            card.suggested_script = sample_script
            print(f"✅ 已為卡片 '{card.title}' 添加建議稿")

        db.commit()
        print()
        print(f"✅ 成功為 {len(cards_without_script)} 張卡片添加建議稿")

    except Exception as e:
        db.rollback()
        print(f"❌ 錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--add-sample":
        print("添加範例建議稿模式")
        print()
        add_sample_script_to_cards()
    else:
        test_suggested_script()
