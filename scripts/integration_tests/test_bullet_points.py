#!/usr/bin/env python3
"""Test bullet point generation feature."""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.bullet_point_service import bullet_point_service

# Test cases
test_scripts = [
    {
        "name": "機器學習介紹",
        "script": """
今天我要介紹機器學習的基本概念。機器學習是人工智慧的一個分支，
它主要包含三大類型：監督式學習、非監督式學習和強化學習。
監督式學習需要標註數據，像是分類和回歸問題。
非監督式學習則是處理無標註數據，例如聚類分析。
強化學習則是透過與環境互動來學習最佳策略。
"""
    },
    {
        "name": "產品發布",
        "script": """
我們很高興宣布推出全新的產品 XYZ。這個產品解決了客戶在數據分析上的痛點，
提供了即時的數據可視化功能，支援多種數據源的整合，
並且有非常直觀的用戶界面。我們預計這將大幅提升團隊的工作效率。
"""
    },
    {
        "name": "季度報告",
        "script": """
本季度我們的營收成長了25%，達到新的里程碑。
主要增長來自於新產品線和海外市場的擴展。
我們成功開發了三個新客戶，並與現有客戶簽訂了續約合同。
團隊規模也擴大到50人，研發投入增加了40%。
"""
    }
]

def test_bullet_generation():
    """Test bullet point generation."""
    print("=" * 60)
    print("測試演講重點列點生成功能")
    print("=" * 60)
    print()

    for i, test in enumerate(test_scripts, 1):
        print(f"\n[測試 {i}] {test['name']}")
        print("-" * 60)
        print(f"口語內容:")
        print(test['script'].strip())
        print()

        try:
            bullet_points = bullet_point_service.generate_bullet_points(
                test['script'],
                max_points=5
            )

            print(f"✅ 生成的演講重點 ({len(bullet_points)} 個):")
            for idx, point in enumerate(bullet_points, 1):
                print(f"  {idx}. {point}")

        except Exception as e:
            print(f"❌ 錯誤: {str(e)}")

        print()

if __name__ == "__main__":
    test_bullet_generation()
    print("=" * 60)
    print("測試完成！")
    print("=" * 60)
