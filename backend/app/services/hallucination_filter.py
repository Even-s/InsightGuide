"""
Whisper 幻覺過濾服務

Whisper 在沒有清晰語音時會產生幻覺輸出，常見於：
- 背景噪音
- 沉默段落
- 非語音聲音

本服務提供多層檢測機制來過濾這些幻覺輸出。
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HallucinationFilter:
    """Whisper 幻覺檢測與過濾服務"""

    def __init__(self):
        """初始化幻覺過濾器"""

        # 第 1 層：已知幻覺短語黑名單（繁體中文 + 簡體中文 + 英文）
        self.hallucination_blacklist = {
            # 常見中文幻覺
            "謝謝觀看", "謝謝收看", "謝謝大家", "感謝觀看", "感謝收看",
            "请不吝点赞", "訂閱我的頻道", "订阅我的频道",
            "字幕由", "字幕制作",
            "我不想去", "我想回家", "我要回家", "我不要",
            "哈哈", "呵呵", "嗯嗯", "啊啊", "喔喔",

            # 簡體版本
            "谢谢观看", "谢谢收看", "谢谢大家", "感谢观看", "感谢收看",

            # 英文常見幻覺
            "Thanks for watching", "Thank you for watching",
            "Please subscribe", "Don't forget to subscribe",
            "Subtitles by", "Transcription by",
            "Amara.org", "Amara",

            # 測試/無意義語句
            "測試", "测试", "test", "testing",

            # 音效擬聲詞
            "咳咳", "嗯", "啊", "呃", "額",
        }

        # 只有這些較長、明確的垃圾字幕/幻覺短語允許「包含」比對。
        # 單字口語助詞如「啊」「嗯」「呃」只能整句精確匹配，否則會誤殺正常演講。
        polite_closing_phrases = {
            "謝謝大家", "感謝大家", "謝謝收看", "感謝收看",
            "谢谢大家", "感谢大家", "谢谢收看", "感谢收看",
        }

        self.partial_match_blacklist = {
            phrase
            for phrase in self.hallucination_blacklist
            if phrase not in polite_closing_phrases
            if len(phrase) >= 4
            or re.search(r"[A-Za-z]", phrase)
            or phrase in {"字幕由", "字幕制作", "訂閱我的頻道", "订阅我的频道"}
        }

        # 第 2 層：重複模式檢測（如 "哈哈哈哈"、"嗯嗯嗯"）
        self.repetition_patterns = [
            r"^(.{1,3})\1{2,}$",  # 1-3 字重複 3 次以上
            r"^(哈){2,}$",        # 哈哈...
            r"^(呵){2,}$",        # 呵呵...
            r"^(嗯){2,}$",        # 嗯嗯...
            r"^(啊){2,}$",        # 啊啊...
        ]

        # 第 3 層：語意無關短語（常見於 YouTube 字幕）
        self.semantic_blacklist_patterns = [
            r"字幕.*",
            r".*訂閱.*",
            r".*订阅.*",
            r".*like.*subscribe.*",
            r".*點讚.*",
            r".*点赞.*",
            r".*評論.*留言.*",
            r".*Amara.*",
        ]

        # 第 4 層：過短內容（可能是噪音）
        self.min_meaningful_length = 3

        # 第 5 層：統計追蹤（檢測高頻重複幻覺）
        self.transcript_frequency: Dict[str, int] = {}
        self.frequency_threshold = 3  # 同一句話出現 3 次以上視為幻覺

    def is_hallucination(
        self,
        transcript: str,
        enable_frequency_check: bool = True,
        context: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        檢測 transcript 是否為 Whisper 幻覺

        Args:
            transcript: 轉錄文字
            enable_frequency_check: 是否啟用頻率檢測（預設 True）
            context: 額外上下文（如 audio_duration, confidence 等）

        Returns:
            {
                "is_hallucination": bool,
                "reason": str,
                "confidence": float,  # 0-1
                "filter_layer": str   # 哪一層過濾器檢測到
            }
        """
        transcript = transcript.strip()

        # 空白檢查
        if not transcript:
            return {
                "is_hallucination": True,
                "reason": "Empty transcript",
                "confidence": 1.0,
                "filter_layer": "empty"
            }

        # 第 1 層：黑名單檢查（精確匹配）
        if transcript in self.hallucination_blacklist:
            logger.warning(f"[HallucinationFilter] Layer 1: Blacklist match: '{transcript}'")
            return {
                "is_hallucination": True,
                "reason": f"Known hallucination phrase: '{transcript}'",
                "confidence": 1.0,
                "filter_layer": "blacklist"
            }

        # 第 1.5 層：黑名單部分匹配（包含檢查）
        for phrase in self.partial_match_blacklist:
            if phrase in transcript:
                logger.warning(f"[HallucinationFilter] Layer 1.5: Blacklist partial match: '{phrase}' in '{transcript}'")
                return {
                    "is_hallucination": True,
                    "reason": f"Contains known hallucination: '{phrase}'",
                    "confidence": 0.9,
                    "filter_layer": "blacklist_partial"
                }

        # 第 2 層：重複模式檢測
        for pattern in self.repetition_patterns:
            if re.match(pattern, transcript):
                logger.warning(f"[HallucinationFilter] Layer 2: Repetition pattern: '{transcript}'")
                return {
                    "is_hallucination": True,
                    "reason": f"Repetitive pattern detected: '{transcript}'",
                    "confidence": 0.95,
                    "filter_layer": "repetition"
                }

        # 第 3 層：語意無關模式
        for pattern in self.semantic_blacklist_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                logger.warning(f"[HallucinationFilter] Layer 3: Semantic blacklist: '{transcript}'")
                return {
                    "is_hallucination": True,
                    "reason": f"Semantic blacklist pattern matched",
                    "confidence": 0.85,
                    "filter_layer": "semantic"
                }

        # 第 4 層：過短檢查（但排除單字元音效詞，它們已在黑名單）
        if len(transcript) < self.min_meaningful_length:
            # 如果已在黑名單，應該在 Layer 1 被抓到
            # 這裡只處理「不在黑名單但太短」的情況
            logger.warning(f"[HallucinationFilter] Layer 4: Too short: '{transcript}'")
            return {
                "is_hallucination": True,
                "reason": f"Transcript too short ({len(transcript)} chars)",
                "confidence": 0.8,
                "filter_layer": "too_short"
            }

        # 第 5 層：高頻重複檢測
        if enable_frequency_check:
            freq = self.transcript_frequency.get(transcript, 0)
            if freq >= self.frequency_threshold:
                logger.warning(f"[HallucinationFilter] Layer 5: High frequency: '{transcript}' (count: {freq})")
                return {
                    "is_hallucination": True,
                    "reason": f"Same transcript repeated {freq} times",
                    "confidence": 0.9,
                    "filter_layer": "high_frequency"
                }

        # 通過所有檢測，視為正常 transcript
        return {
            "is_hallucination": False,
            "reason": "Passed all filters",
            "confidence": 0.0,
            "filter_layer": None
        }

    def track_transcript(self, transcript: str):
        """追蹤 transcript 出現頻率（用於高頻檢測）"""
        transcript = transcript.strip()
        if transcript:
            self.transcript_frequency[transcript] = self.transcript_frequency.get(transcript, 0) + 1

    def reset_frequency_tracking(self):
        """重置頻率追蹤（如新開始一場簡報）"""
        self.transcript_frequency.clear()
        logger.info("[HallucinationFilter] Frequency tracking reset")

    def add_to_blacklist(self, phrase: str):
        """動態新增幻覺短語到黑名單"""
        self.hallucination_blacklist.add(phrase.strip())
        logger.info(f"[HallucinationFilter] Added to blacklist: '{phrase}'")

    def remove_from_blacklist(self, phrase: str):
        """從黑名單移除（如誤判）"""
        self.hallucination_blacklist.discard(phrase.strip())
        logger.info(f"[HallucinationFilter] Removed from blacklist: '{phrase}'")

    def get_stats(self) -> Dict[str, any]:
        """取得統計資訊"""
        return {
            "blacklist_size": len(self.hallucination_blacklist),
            "tracked_transcripts": len(self.transcript_frequency),
            "top_frequent": sorted(
                self.transcript_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


# Singleton instance
hallucination_filter = HallucinationFilter()
