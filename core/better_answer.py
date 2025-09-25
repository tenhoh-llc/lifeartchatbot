"""
改善された回答生成モジュール
より分かりやすく、根拠明確な回答を生成
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import re
from loguru import logger


@dataclass
class StructuredAnswer:
    """構造化された回答"""
    main_answer: str  # メインの回答（簡潔に）
    details: List[str]  # 詳細ポイント
    evidence: str  # 根拠テキスト（整形済み）
    source: str  # 出典
    confidence: float  # 確信度


class BetterAnswerGenerator:
    """改善された回答生成器"""
    
    def __init__(self):
        self.patterns = self._init_patterns()
    
    def _init_patterns(self) -> Dict[str, List[tuple]]:
        """パターン定義"""
        return {
            "育児休業": [
                (r"育児休業.{0,20}([\d一二三四五六七八九十]+歳.{0,10}まで)", "対象期間"),
                (r"申[出請].{0,20}([\d一二三四五六七八九十]+[日月]前)", "申請時期"),
                (r"([\d一二三四五六七八九十]+回.{0,10}分割|分割.{0,10}[\d一二三四五六七八九十]+回)", "分割取得"),
                (r"育児休業.{0,30}(取得|利用|申請)(.{0,50}条件|.{0,50}要件)", "取得条件"),
                (r"(給付金|手当).{0,30}([\d０-９]+[％%])", "給付金"),
            ],
            "有給休暇": [
                (r"有給休暇.{0,20}([\d一二三四五六七八九十]+日)", "付与日数"),
                (r"繰[越繰].{0,20}([\d一二三四五六七八九十]+日|[\d一二三四五六七八九十]+年)", "繰越"),
                (r"(半日|時間単位).{0,10}取得", "取得単位"),
                (r"申[請出].{0,20}([\d一二三四五六七八九十]+日前)", "申請期限"),
            ],
            "残業": [
                (r"時間外.{0,20}(月.{0,10}[\d一二三四五六七八九十]+時間|年.{0,10}[\d一二三四五六七八九十]+時間)", "上限時間"),
                (r"(36協定|三六協定)", "36協定"),
                (r"割増.{0,20}([\d０-９]+[％%])", "割増率"),
            ],
            "給与": [
                (r"(毎月|月).{0,10}([\d一二三四五六七八九十]+日).{0,10}締", "締日"),
                (r"(毎月|月).{0,10}([\d一二三四五六七八九十]+日).{0,10}支[払給]", "支給日"),
                (r"賞与.{0,30}([\d一二三四五六七八九十]+月|年[\d一二三四五六七八九十]+回)", "賞与"),
            ]
        }
    
    def generate(self, query: str, search_results: List[Any]) -> StructuredAnswer:
        """
        構造化された回答を生成
        
        Args:
            query: ユーザーの質問
            search_results: 検索結果
            
        Returns:
            構造化された回答
        """
        if not search_results:
            return self._no_result_answer()
        
        # 最も関連性の高い結果を使用
        best_result = search_results[0]
        text = best_result.text
        
        # トピックを判定
        topic = self._identify_topic(query)
        
        # 重要な情報を抽出
        key_points = self._extract_key_points(text, topic, query)
        
        # メイン回答を生成
        main_answer = self._create_main_answer(key_points, topic, query)
        
        # 詳細ポイントを整理
        details = self._create_detail_points(key_points, text, query)
        
        # 根拠テキストを整形
        evidence = self._format_evidence(text, query, max_length=400)
        
        # 出典情報
        source = f"{best_result.file_name} - ページ {best_result.page_no}"
        if hasattr(best_result, 'section') and best_result.section:
            source = f"{best_result.file_name} - {best_result.section}"
        
        # 確信度計算
        confidence = self._calculate_confidence(key_points, best_result.score if hasattr(best_result, 'score') else 50)
        
        return StructuredAnswer(
            main_answer=main_answer,
            details=details,
            evidence=evidence,
            source=source,
            confidence=confidence
        )
    
    def _identify_topic(self, query: str) -> Optional[str]:
        """トピック判定"""
        query_lower = query.lower()
        
        topics = {
            "育児休業": ["育児", "育休", "産休", "子育て"],
            "有給休暇": ["有給", "有休", "年休", "年次"],
            "残業": ["残業", "時間外", "超過勤務"],
            "給与": ["給与", "給料", "賃金", "ボーナス", "賞与"],
        }
        
        for topic, keywords in topics.items():
            if any(kw in query_lower for kw in keywords):
                return topic
        
        return None
    
    def _extract_key_points(self, text: str, topic: Optional[str], query: str) -> Dict[str, str]:
        """重要ポイントを抽出"""
        points = {}
        
        if not topic:
            # トピックが不明な場合は汎用的な抽出
            return self._extract_generic_points(text, query)
        
        patterns = self.patterns.get(topic, [])
        
        for pattern, label in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                # マッチした内容を整理
                if match.groups():
                    value = match.group(1) if match.group(1) else match.group(0)
                else:
                    value = match.group(0)
                
                # 前後の文脈を少し含める
                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()
                
                # 句読点で適切に切る
                if start > 0:
                    first_period = context.find("。")
                    if 0 < first_period < 30:
                        context = context[first_period + 1:]
                
                points[label] = self._clean_text(context)
        
        return points
    
    def _extract_generic_points(self, text: str, query: str) -> Dict[str, str]:
        """汎用的なポイント抽出"""
        points = {}
        
        # 数値を含む重要そうな部分を抽出
        number_patterns = [
            (r"([\d一二三四五六七八九十]+[日月年時間].{0,30})", "期間・期限"),
            (r"([\d０-９]+[％%].{0,30})", "割合・率"),
            (r"第([\d一二三四五六七八九十]+条.{0,50})", "該当条文"),
        ]
        
        for pattern, label in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                points[label] = self._clean_text(matches[0])
        
        return points
    
    def _create_main_answer(self, key_points: Dict[str, str], topic: Optional[str], query: str) -> str:
        """メイン回答を生成"""
        if not key_points:
            return "ご質問の内容について、規程文書から明確な記載を見つけることができませんでした。"
        
        # トピックごとのテンプレート
        templates = {
            "育児休業": "育児休業は、{対象期間}取得可能です。{申請時期}に申請が必要です。",
            "有給休暇": "有給休暇は{付与日数}付与されます。{繰越}の繰越が可能です。",
            "残業": "時間外労働は{上限時間}が上限となっています。",
            "給与": "給与は{締日}締め、{支給日}支給です。",
        }
        
        if topic and topic in templates:
            template = templates[topic]
            
            # テンプレートに値を埋める
            for key in key_points:
                placeholder = f"{{{key}}}"
                if placeholder in template:
                    template = template.replace(placeholder, key_points[key])
            
            # 埋められなかったプレースホルダーを処理
            template = re.sub(r'\{[^}]+\}', '', template)
            template = re.sub(r'。+', '。', template)
            template = re.sub(r'、+', '、', template)
            
            return template.strip()
        
        # テンプレートがない場合は要点を列挙
        if len(key_points) == 1:
            return f"ご質問について、{list(key_points.values())[0]}"
        else:
            main_point = list(key_points.values())[0]
            return f"ご質問について、{main_point}"
    
    def _create_detail_points(self, key_points: Dict[str, str], text: str, query: str) -> List[str]:
        """詳細ポイントを作成"""
        details = []
        
        for label, content in key_points.items():
            # ラベルを日本語に変換
            label_jp = self._translate_label(label)
            details.append(f"【{label_jp}】{content}")
        
        # 追加の関連情報を探す
        additional_info = self._find_additional_info(text, query)
        if additional_info:
            details.extend(additional_info)
        
        return details[:5]  # 最大5個まで
    
    def _translate_label(self, label: str) -> str:
        """ラベルを日本語に変換"""
        translations = {
            "対象期間": "対象期間",
            "申請時期": "申請時期",
            "分割取得": "分割取得",
            "取得条件": "取得条件",
            "給付金": "給付金",
            "付与日数": "付与日数",
            "繰越": "繰越",
            "取得単位": "取得単位",
            "申請期限": "申請期限",
            "上限時間": "上限時間",
            "36協定": "36協定",
            "割増率": "割増賃金率",
            "締日": "締日",
            "支給日": "支給日",
            "賞与": "賞与",
            "期間・期限": "期間・期限",
            "割合・率": "割合・率",
            "該当条文": "該当条文",
        }
        return translations.get(label, label)
    
    def _find_additional_info(self, text: str, query: str) -> List[str]:
        """追加情報を探す"""
        info = []
        
        # 「ただし」「なお」などの追加情報を探す
        additional_patterns = [
            r"ただし[、。](.{0,100}[。])",
            r"なお[、。](.{0,100}[。])",
            r"※(.{0,100}[。\n])",
        ]
        
        for pattern in additional_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:2]:  # 最大2個
                cleaned = self._clean_text(match)
                if len(cleaned) > 10:
                    info.append(f"※ {cleaned}")
        
        return info
    
    def _format_evidence(self, text: str, query: str, max_length: int = 400) -> str:
        """根拠テキストを整形"""
        # クエリに関連する部分を中心に抽出
        query_keywords = self._extract_keywords(query)
        
        # キーワードが最初に出現する位置を探す
        best_position = len(text)
        for keyword in query_keywords:
            pos = text.lower().find(keyword.lower())
            if 0 <= pos < best_position:
                best_position = pos
        
        if best_position == len(text):
            best_position = 0
        
        # 前後のテキストを取得
        start = max(0, best_position - 100)
        end = min(len(text), best_position + max_length - 100)
        
        evidence = text[start:end]
        
        # 文の区切りで調整
        if start > 0:
            first_period = evidence.find("。")
            if 0 < first_period < 50:
                evidence = evidence[first_period + 1:]
            evidence = "..." + evidence
        
        if end < len(text):
            last_period = evidence.rfind("。")
            if len(evidence) - 50 < last_period:
                evidence = evidence[:last_period + 1]
            else:
                evidence = evidence + "..."
        
        # キーワードをハイライト
        for keyword in query_keywords[:3]:
            evidence = re.sub(
                f"({re.escape(keyword)})",
                r"**\1**",
                evidence,
                flags=re.IGNORECASE
            )
        
        return evidence.strip()
    
    def _extract_keywords(self, query: str) -> List[str]:
        """クエリからキーワードを抽出"""
        # 助詞などを除去
        stopwords = ["について", "とは", "ですか", "ください", "教えて", "の", "を", "に", "は", "が", "で"]
        
        keywords = []
        for word in re.split(r'[、。\s]', query):
            word = word.strip()
            if word and word not in stopwords and len(word) > 1:
                keywords.append(word)
        
        return keywords
    
    def _clean_text(self, text: str) -> str:
        """テキストをクリーニング"""
        # 余分な空白を削除
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', ' ', text)
        
        # 記号の調整
        text = text.replace("。。", "。")
        text = text.replace("、、", "、")
        
        return text.strip()
    
    def _calculate_confidence(self, key_points: Dict[str, str], score: float) -> float:
        """確信度を計算"""
        confidence = 0.0
        
        # キーポイント数による確信度
        point_confidence = min(len(key_points) * 0.2, 0.6)
        confidence += point_confidence
        
        # スコアによる確信度
        score_confidence = min(score / 100, 0.4)
        confidence += score_confidence
        
        return min(confidence, 1.0)
    
    def _no_result_answer(self) -> StructuredAnswer:
        """結果なしの回答"""
        return StructuredAnswer(
            main_answer="申し訳ございません。ご質問に関連する情報が見つかりませんでした。",
            details=["別のキーワードでお試しください", "より具体的な用語を使用してみてください"],
            evidence="",
            source="",
            confidence=0.0
        )


def format_answer_for_display(answer: StructuredAnswer) -> str:
    """表示用に回答をフォーマット"""
    parts = []
    
    # メイン回答
    parts.append(f"📝 **{answer.main_answer}**\n")
    
    # 詳細ポイント
    if answer.details:
        parts.append("📋 **詳細情報:**")
        for detail in answer.details:
            parts.append(f"  {detail}")
    
    # 根拠（短く表示）
    if answer.evidence:
        parts.append("\n🔍 **根拠となる規程文書の記載:**")
        parts.append(f"> {answer.evidence[:300]}...")
    
    # 出典
    if answer.source:
        parts.append(f"\n📚 出典: {answer.source}")
    
    return "\n".join(parts)