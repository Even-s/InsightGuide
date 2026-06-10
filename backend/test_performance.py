#!/usr/bin/env python3
"""
Quick performance test for semantic understanding optimization.

Tests the speed of GPT-5.4-mini vs GPT-5.5 for semantic judgment.
Run this after optimization to verify improvement.

Usage:
    python test_performance.py
"""

import time
import asyncio
from openai import OpenAI
from app.core.config import settings

def test_semantic_judgment_speed():
    """Test semantic judgment response time with current model."""

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=10.0)
    model = settings.SEMANTIC_UNDERSTANDING_MODEL

    print(f"🧪 Testing semantic judgment speed with {model}")
    print("=" * 60)

    # Test utterance
    utterance = "脂肪細胞不只是用來儲存能量，它還能分泌激素來調節身體的代謝功能。"

    # Test topic card
    topic = {
        "title": "脂肪細胞的內分泌功能",
        "description": "解釋脂肪細胞除了儲存能量外，還具有內分泌功能",
        "semanticAnchors": ["內分泌功能", "激素分泌", "代謝調節"],
        "expectedKeywords": ["脂肪", "激素", "代謝"]
    }

    prompt = f"""請判斷以下逐字稿是否覆蓋了主題。

主題: {topic['title']}
描述: {topic['description']}
核心概念: {', '.join(topic['semanticAnchors'])}

逐字稿: {utterance}

以 JSON 格式回覆:
{{
    "is_covered": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "判斷理由"
}}"""

    # Run 3 tests
    times = []
    for i in range(3):
        print(f"\n📊 測試 {i+1}/3...")
        start = time.time()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是語義理解專家。只回覆 JSON 格式。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            elapsed = time.time() - start
            times.append(elapsed)

            result = response.choices[0].message.content
            print(f"   ⏱️  響應時間: {elapsed:.3f}s")
            print(f"   📝 結果: {result[:100]}...")

        except Exception as e:
            print(f"   ❌ 錯誤: {str(e)}")
            continue

    # Summary
    if times:
        avg_time = sum(times) / len(times)
        print("\n" + "=" * 60)
        print(f"✅ 測試完成")
        print(f"📈 平均響應時間: {avg_time:.3f}s")
        print(f"⚡ 最快響應: {min(times):.3f}s")
        print(f"🐌 最慢響應: {max(times):.3f}s")
        print(f"🎯 模型: {model}")

        # Performance benchmark
        if avg_time < 0.5:
            print(f"💚 性能評級: 極佳 (< 0.5s)")
        elif avg_time < 1.0:
            print(f"💙 性能評級: 良好 (0.5-1.0s)")
        elif avg_time < 2.0:
            print(f"💛 性能評級: 一般 (1.0-2.0s)")
        else:
            print(f"❤️  性能評級: 需優化 (> 2.0s)")

        print("\n💡 GPT-5.4-mini 目標: < 0.5s (極佳)")
        print("💡 GPT-5.5 預期: 1.5-3.0s (需優化)")
    else:
        print("\n❌ 所有測試都失敗了")

    print("=" * 60)


def test_token_optimization():
    """Test token usage optimization in prompts."""

    print("\n🧪 測試 Token 優化")
    print("=" * 60)

    # Old prompt (before optimization)
    old_prompt = """請為演講者生成下一句建議。

【當前投影片】
標題: 機器學習基礎
摘要: 介紹機器學習的基本概念、分類與應用
頁碼: 1

【演講者最近說的話】
句子1: 大家好，今天我們來講機器學習
句子2: 機器學習是人工智慧的一個重要分支
句子3: 它可以讓電腦從數據中學習
句子4: 不需要明確的程式指令
句子5: 現在機器學習已經被廣泛應用在各個領域

【已經講完的主題】
- 機器學習的定義: 詳細解釋什麼是機器學習，以及它與傳統程式設計的區別
- 機器學習的歷史: 從1950年代到現在的發展歷程
- 機器學習的重要性: 為什麼機器學習在現代科技中如此重要
- 機器學習的應用領域: 列舉各個產業中的實際應用案例
- 機器學習的未來趨勢: 預測未來5-10年的發展方向

【還沒講的重點】（優先度：must > should > optional）
- [must] 監督式學習: 詳細說明什麼是監督式學習，包括標記數據、訓練過程、常見演算法等
- [must] 非監督式學習: 解釋非監督式學習的概念，與監督式學習的差異，以及應用場景
- [must] 強化學習: 介紹強化學習的基本原理，獎勵機制，以及在遊戲AI中的應用
- [should] 深度學習: 簡要說明深度學習與傳統機器學習的關係，神經網路的概念
- [should] 特徵工程: 解釋為什麼特徵選擇很重要，如何進行特徵工程"""

    # New prompt (after optimization)
    new_prompt = """請為演講者生成下一句建議。

【當前投影片】
標題: 機器學習基礎
摘要: 介紹機器學習的基本概念、分類與應用
頁碼: 1

【演講者最近說的話】
不需要明確的程式指令
現在機器學習已經被廣泛應用在各個領域

【已經講完的主題】
- 機器學習的定義
- 機器學習的歷史
- 機器學習的重要性

【還沒講的重點】（優先度：must > should > optional）
- [must] 監督式學習
- [must] 非監督式學習
- [must] 強化學習"""

    # Rough token estimation (1 token ≈ 4 chars for Chinese)
    old_tokens = len(old_prompt) / 2  # Conservative estimate
    new_tokens = len(new_prompt) / 2

    print(f"📊 Prompt 長度對比:")
    print(f"   優化前: ~{int(old_tokens)} tokens ({len(old_prompt)} chars)")
    print(f"   優化後: ~{int(new_tokens)} tokens ({len(new_prompt)} chars)")
    print(f"   節省: {int(old_tokens - new_tokens)} tokens ({(1 - new_tokens/old_tokens)*100:.1f}%)")

    # Cost calculation
    input_cost_per_m = 0.75  # GPT-5.4-mini price
    old_cost = (old_tokens / 1_000_000) * input_cost_per_m
    new_cost = (new_tokens / 1_000_000) * input_cost_per_m

    print(f"\n💰 成本對比 (GPT-5.4-mini):")
    print(f"   優化前: ${old_cost:.6f} / 次")
    print(f"   優化後: ${new_cost:.6f} / 次")
    print(f"   每次演講生成 10 次建議:")
    print(f"      優化前: ${old_cost * 10:.5f}")
    print(f"      優化後: ${new_cost * 10:.5f}")
    print(f"      節省: ${(old_cost - new_cost) * 10:.5f}")

    print("=" * 60)


if __name__ == "__main__":
    print("\n🚀 InsightGuide 性能優化測試")
    print("=" * 60)
    print(f"📍 當前模型: {settings.SEMANTIC_UNDERSTANDING_MODEL}")
    print("=" * 60)

    # Test 1: Semantic judgment speed
    test_semantic_judgment_speed()

    # Test 2: Token optimization
    test_token_optimization()

    print("\n✅ 所有測試完成！")
    print("\n💡 提示:")
    print("   - 如果平均響應時間 < 0.5s，優化成功！")
    print("   - 如果平均響應時間 > 1.0s，可能需要檢查網路或 API 配置")
    print("   - Token 優化應該節省 40-50% 的輸入 token")
