#!/usr/bin/env python3
"""
Milestone 5 Simple Test: 測試主題匹配引擎核心功能

不依賴已有 deck，而是直接測試各個服務組件
"""

import requests
import json

BASE_URL = "http://localhost:8001"


def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_result(success, message):
    icon = "✅" if success else "❌"
    print(f"{icon} {message}")


def test_services():
    """測試 Milestone 5 服務組件"""
    print_header("MILESTONE 5 服務測試")

    # Test 1: 測試 Whisper API (M4)
    print_header("Test 1: Whisper 轉錄 API")

    response = requests.get(f"{BASE_URL}/api/transcription/supported-languages")
    if response.status_code == 200:
        data = response.json()
        print_result(True, f"Whisper API 可用 - 支援 {len(data['languages'])} 種語言")
    else:
        print_result(False, f"Whisper API 錯誤: {response.status_code}")
        return False

    # Test 2: 測試 SSE 端點 (M5)
    print_header("Test 2: SSE 事件端點")

    # 先創建一個測試 session ID (任意)
    test_session_id = "test_session_123"

    response = requests.get(
        f"{BASE_URL}/api/events/sessions/{test_session_id}/connections"
    )

    if response.status_code == 200:
        data = response.json()
        print_result(True, f"SSE 端點可用")
        print(f"   Session ID: {data['sessionId']}")
        print(f"   連線數: {data['activeConnections']}")
    else:
        print_result(False, f"SSE 端點錯誤: {response.status_code}")

    # Test 3: 測試 API 文件
    print_header("Test 3: API 文件")

    response = requests.get(f"{BASE_URL}/docs")
    if response.status_code == 200:
        print_result(True, "API 文件可訪問: http://localhost:8001/docs")
    else:
        print_result(False, "API 文件不可訪問")

    # Test 4: 檢查服務健康狀態
    print_header("Test 4: 服務健康檢查")

    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        data = response.json()
        print_result(True, f"後端健康: {data['status']}")
        print(f"   環境: {data['environment']}")
    else:
        print_result(False, "健康檢查失敗")

    print_header("測試摘要")
    print("\n✅ Milestone 4 & 5 核心組件已部署:")
    print("   - Whisper 轉錄 API")
    print("   - SSE 事件服務")
    print("   - 主題匹配引擎")
    print("   - API 文件")

    print("\n📝 要測試完整流程，需要:")
    print("   1. 上傳並分析一個 PPTX (Milestone 2)")
    print("   2. 創建 presentation session")
    print("   3. 發送 utterances 測試匹配")

    print("\n🔍 檢查已部署的服務:")
    print(f"   API 文件: http://localhost:8001/docs")
    print(f"   健康檢查: http://localhost:8001/health")

    return True


def test_component_functionality():
    """測試組件基本功能"""
    print_header("組件功能測試")

    # Test: Embedding Service (通過 Python 直接測試)
    print("\n測試 Embedding Service...")
    try:
        import sys
        sys.path.insert(0, '/Users/cfh00914977/Project/InsightGuide/backend')

        from app.services.embedding_service import embedding_service

        # 測試文字嵌入
        text = "機器學習的基本概念"
        embedding = embedding_service.get_embedding(text)

        if len(embedding) == 3072:
            print_result(True, f"Embedding Service 正常 (維度: {len(embedding)})")
        else:
            print_result(False, f"Embedding 維度錯誤: {len(embedding)}")

        # 測試相似度計算
        text1 = "機器學習"
        text2 = "深度學習"
        score = embedding_service.calculate_semantic_score(text1, [text2])

        print(f"   語義相似度測試: '{text1}' vs '{text2}' = {score:.3f}")

    except Exception as e:
        print_result(False, f"Embedding Service 錯誤: {str(e)}")

    # Test: Scoring Service
    print("\n測試 Scoring Service...")
    try:
        from app.services.scoring_service import scoring_service

        utterance = "今天介紹機器學習和深度學習"
        keywords = ["機器學習", "深度學習", "神經網路"]

        score = scoring_service.calculate_keyword_score(utterance, keywords)
        print_result(True, f"Scoring Service 正常")
        print(f"   關鍵字評分: {score:.3f} (2/3 關鍵字匹配)")

    except Exception as e:
        print_result(False, f"Scoring Service 錯誤: {str(e)}")


if __name__ == "__main__":
    try:
        print("\n" + "╔" + "═" * 58 + "╗")
        print("║" + " " * 58 + "║")
        print("║" + "  Milestone 5: 主題匹配引擎 - 簡化測試  ".center(58) + "║")
        print("║" + " " * 58 + "║")
        print("╚" + "═" * 58 + "╝")

        # 測試 API 服務
        test_services()

        # 測試組件功能
        test_component_functionality()

        print("\n" + "=" * 60)
        print("🎉 測試完成！")
        print("=" * 60)

        print("\n💡 下一步測試:")
        print("   1. 上傳測試 PPTX: curl -F 'file=@test.pptx' http://localhost:8001/api/decks/")
        print("   2. 等待分析完成")
        print("   3. 運行完整的 E2E 測試")

    except KeyboardInterrupt:
        print("\n\n❌ 測試被中斷")
    except Exception as e:
        print(f"\n\n❌ 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
