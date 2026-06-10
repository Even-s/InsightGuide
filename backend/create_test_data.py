"""
創建測試資料用於測試動態建議逐字稿生成器

這個腳本會創建：
1. 一個測試用的 Deck
2. 兩張 Slides
3. 每張 Slide 的 TopicCards
4. 一個 PresentationSession
5. 一些測試用的 Utterances
"""

import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.insert(0, '/Users/cfh00914977/Project/InsightGuide/backend')

from app.db.session import SessionLocal
from app.models.user import User
from app.models.deck import Deck
from app.models.slide import Slide
from app.models.topic_card import TopicCard
from app.models.prep_session import PrepSession
from app.models.presentation_session import PresentationSession, PresentationCardState
from app.models.utterance import Utterance
import uuid


def create_test_data():
    """創建完整的測試資料"""

    db = SessionLocal()

    try:
        print("🚀 開始創建測試資料...\n")

        # 0. 創建或查找測試用戶
        user_id = "test_user"
        existing_user = db.query(User).filter(User.email == "test@example.com").first()
        if existing_user:
            user_id = existing_user.id
            print(f"✅ 使用現有測試用戶: {user_id}\n")
        else:
            user = User(
                id=user_id,
                email="test@example.com",
                hashed_password="hashed_password_placeholder",
                created_at=datetime.utcnow()
            )
            db.add(user)
            db.flush()
            print(f"✅ 創建測試用戶: {user_id}\n")

        # 1. 創建 Deck
        deck_id = f"deck_{uuid.uuid4().hex[:8]}"
        deck = Deck(
            id=deck_id,
            user_id=user_id,
            title="2026年5月科技股分析",
            source_file_url=f"http://localhost:9000/insightguide-uploads/{deck_id}/tech_stocks_2026.pdf",
            pdf_file_url=f"http://localhost:9000/insightguide-uploads/{deck_id}/tech_stocks_2026.pdf",
            status="processed",
            created_at=datetime.utcnow()
        )
        db.add(deck)
        db.flush()
        print(f"✅ 創建 Deck: {deck_id}")
        print(f"   標題: {deck.title}\n")

        # 2. 創建 Slide 1
        slide1_id = f"slide_{uuid.uuid4().hex[:8]}"
        slide1 = Slide(
            id=slide1_id,
            deck_id=deck_id,
            page_number=1,
            title="5月26日熱門股票期貨數據",
            extracted_text="股票期貨數據 交易量 漲幅 跌幅",
            ai_summary="展示2026年5月26日的熱門股票期貨數據，包括交易量、漲幅和跌幅等關鍵指標",
            image_url=f"http://localhost:9000/insightguide-uploads/{deck_id}/slide_1.png",
            created_at=datetime.utcnow()
        )
        db.add(slide1)
        db.flush()
        print(f"✅ 創建 Slide 1: {slide1_id}")
        print(f"   標題: {slide1.title}\n")

        # 3. 創建 Slide 1 的 TopicCards
        cards_slide1 = []

        # Card 1.1: 數據概覽 (will mark as covered)
        card1_1_id = f"card_{uuid.uuid4().hex[:8]}"
        card1_1 = TopicCard(
            id=card1_1_id,
            deck_id=deck_id,
            slide_id=slide1_id,
            slide_page_number=1,
            title="數據概覽",
            description="介紹5月26日熱門股票期貨的整體數據情況",
            importance="must",
            status="active",
            short_prompt="從交易量到漲幅跌幅，各種數據",
            suggested_script="今天我們來看一下5月26日的熱門股票期貨數據，從交易量到漲幅和跌幅，各種數據一應俱全",
            coverage_rule={
                "semanticAnchors": ["股票期貨數據", "交易量", "漲幅", "跌幅", "數據齊全"],
                "expectedKeywords": ["數據", "交易量", "漲幅", "跌幅"],
                "mustMentionFacts": [],
                "thresholds": {"covered": 0.70, "probably_covered": 0.55},
                "scoringWeights": {"semantic": 0.55, "keyword": 0.25, "fact": 0.20}
            },
            created_at=datetime.utcnow()
        )
        db.add(card1_1)
        cards_slide1.append(card1_1)

        # Card 1.2: 力積電技術
        card1_2_id = f"card_{uuid.uuid4().hex[:8]}"
        card1_2 = TopicCard(
            id=card1_2_id,
            deck_id=deck_id,
            slide_id=slide1_id,
            slide_page_number=1,
            title="力積電 3D AI Foundry 技術",
            description="力積電在 Computex 展示的先進 3D AI 封裝技術",
            importance="must",
            status="active",
            short_prompt="力積電的 3D AI 技術展示",
            suggested_script="接下來我們聚焦在力積電，他們在最近的 Computex 展示了非常先進的 3D AI Foundry 技術",
            coverage_rule={
                "semanticAnchors": ["力積電", "Computex", "3D AI", "先進技術", "封裝技術"],
                "expectedKeywords": ["力積電", "3D", "AI", "技術"],
                "mustMentionFacts": [],
                "thresholds": {"covered": 0.70, "probably_covered": 0.55},
                "scoringWeights": {"semantic": 0.55, "keyword": 0.25, "fact": 0.20}
            },
            created_at=datetime.utcnow()
        )
        db.add(card1_2)
        cards_slide1.append(card1_2)

        # Card 1.3: 高階封裝市場
        card1_3_id = f"card_{uuid.uuid4().hex[:8]}"
        card1_3 = TopicCard(
            id=card1_3_id,
            deck_id=deck_id,
            slide_id=slide1_id,
            slide_page_number=1,
            title="AI 高階封裝市場布局",
            description="力積電進入 AI 高階封裝市場的策略與基礎",
            importance="should",
            status="active",
            short_prompt="力積電的市場策略",
            suggested_script="這將為力積電進一步進入 AI 高階封裝市場打下堅實基礎",
            coverage_rule={
                "semanticAnchors": ["高階封裝", "市場", "AI 封裝", "基礎", "布局"],
                "expectedKeywords": ["封裝", "市場", "AI"],
                "mustMentionFacts": [],
                "thresholds": {"covered": 0.70, "probably_covered": 0.55},
                "scoringWeights": {"semantic": 0.55, "keyword": 0.25, "fact": 0.20}
            },
            created_at=datetime.utcnow()
        )
        db.add(card1_3)
        cards_slide1.append(card1_3)

        db.flush()
        print(f"✅ 創建 {len(cards_slide1)} 個 TopicCards:")
        for card in cards_slide1:
            print(f"   [{card.importance}] {card.title}")
        print()

        # 4. 創建 PrepSession
        prep_session_id = f"prep_{uuid.uuid4().hex[:8]}"
        prep_session = PrepSession(
            id=prep_session_id,
            deck_id=deck_id,
            user_id=user_id,
            status="ready",
            created_at=datetime.utcnow()
        )
        db.add(prep_session)
        db.flush()
        print(f"✅ 創建 PrepSession: {prep_session_id}\n")

        # 5. 創建 PresentationSession
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        session = PresentationSession(
            id=session_id,
            deck_id=deck_id,
            prep_session_id=prep_session_id,
            user_id=user_id,
            status="presenting",
            current_slide_id=slide1_id,
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        db.add(session)
        db.flush()
        print(f"✅ 創建 PresentationSession: {session_id}")
        print(f"   狀態: {session.status}\n")

        # 6. 創建 PresentationCardStates
        for card in cards_slide1:
            state = PresentationCardState(
                id=f"state_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                topic_card_id=card.id,
                status="pending",  # 先都設為 pending
                confidence=None,
                evidence=None,
                created_at=datetime.utcnow()
            )
            db.add(state)

        db.flush()
        print(f"✅ 創建 {len(cards_slide1)} 個 CardStates (all pending)\n")

        # 7. 創建測試 Utterances（模擬演講者已經說過的話）
        utterances = [
            "大家好",
            "今天我們要來看一下科技股的最新動態",
            "我們來看一下五月二十六日的熱門股票期貨數據",
            "從交易量到漲幅和跌幅各種數據都有",
            "這些數據能幫助我們快速了解市場動態"
        ]

        for i, text in enumerate(utterances):
            utterance = Utterance(
                id=f"utt_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                slide_id=slide1_id,
                transcript=text,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.add(utterance)

        db.flush()
        print(f"✅ 創建 {len(utterances)} 個 Utterances:")
        for i, text in enumerate(utterances, 1):
            print(f"   {i}. {text}")
        print()

        # 8. 將第一張卡片標記為 covered（模擬已經講完）
        first_card_state = db.query(PresentationCardState).filter(
            PresentationCardState.session_id == session_id,
            PresentationCardState.topic_card_id == card1_1_id
        ).first()

        if first_card_state:
            first_card_state.status = "covered"
            first_card_state.confidence = 0.88
            first_card_state.covered_at = datetime.utcnow()
            first_card_state.evidence = {
                "matchedTranscript": "從交易量到漲幅和跌幅各種數據都有",
                "semanticScore": 0.85,
                "keywordScore": 0.92,
                "factScore": 0.90,
                "finalScore": 0.88
            }
            db.flush()
            print(f"✅ 將第一張卡片標記為 covered (模擬已講完)\n")

        # Commit all changes
        db.commit()

        print("=" * 60)
        print("🎉 測試資料創建成功！\n")

        print("📋 測試資訊：")
        print(f"   Deck ID:    {deck_id}")
        print(f"   Slide ID:   {slide1_id}")
        print(f"   Session ID: {session_id}")
        print()

        print("🧪 現在可以測試 Script Plan API：")
        print(f"   curl -X POST http://localhost:8001/api/script-plan/{session_id}/generate \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print("     -d '{\"num_sentences\": 12, \"force_regenerate\": true}' | jq .")
        print()

        print("💡 預期結果：")
        print("   - 生成完整智慧題詞規劃")
        print("   - 依照主題卡片順序安排 12 句題詞")
        print("   - 回傳目前 cursor 與 progress 狀態")
        print()

        return {
            "deck_id": deck_id,
            "slide_id": slide1_id,
            "session_id": session_id,
            "card_ids": [c.id for c in cards_slide1]
        }

    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    result = create_test_data()
    print("✅ 完成！")
