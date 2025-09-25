"""
インテリジェント回答生成モジュール
実際のPDF内容を解析して適切な回答を生成
"""
from typing import List, Optional, Dict, Any
import re
from loguru import logger


class IntelligentAnswerGenerator:
    """
    PDF内容から知的な回答を生成するクラス
    """
    
    def __init__(self):
        self.patterns = self._create_extraction_patterns()
    
    def _create_extraction_patterns(self) -> Dict[str, Dict[str, str]]:
        """
        情報抽出用の正規表現パターンを定義
        """
        return {
            "育児休業": {
                "期間": r"([\d一二三四五六七八九十]+歳(?:[\d一二三四五六七八九十]+か月)?(?:に満たない|まで|に達する))",
                "対象者": r"育児休業(?:の対象者|ができる).{0,50}(社員|従業員|契約社員)",
                "条件": r"(入社[\d一二三四五六七八九十]+年以上|雇用関係が継続|所定労働日数)",
                "除外対象": r"除外された.{0,50}(社員|入社[\d一二三四五六七八九十]+年未満|週間の所定労働日数が[\d一二三四五六七八九十]+日以下)",
                "申請": r"(申出|届出).{0,30}([\d一二三四五六七八九十]+か月前|[\d一二三四五六七八九十]+日前)",
            },
            "有給休暇": {
                "付与日数": r"(有給|年次|年休).{0,30}([\d一二三四五六七八九十]+日)",
                "繰越": r"(繰[越繰]|持[越ち]).{0,30}(可能|できる|翌年)",
                "最大保有": r"(最大|上限).{0,30}([\d一二三四五六七八九十]+日)",
                "取得条件": r"(付与|取得).{0,20}(条件|要件)",
            },
            "労働時間": {
                "所定": r"(所定|通常|標準).{0,20}(労働時間|勤務時間).{0,30}([\d一二三四五六七八九十]+時間)",
                "時間外上限": r"(時間外|残業).{0,20}(上限|限度|まで).{0,30}([\d一二三四五六七八九十]+時間)",
                "休憩": r"(休憩).{0,30}([\d一二三四五六七八九十]+分|[\d一二三四五六七八九十]+時間)",
                "勤務時間": r"(始業|終業|勤務).{0,20}([\d一二三四五六七八九十]+時)",
            },
            "給与": {
                "締日": r"(締[日め]|〆).{0,30}([\d一二三四五六七八九十]+日)",
                "支払日": r"(支[払給]|振込).{0,30}([\d一二三四五六七八九十]+日)",
                "賞与": r"(賞与|ボーナス).{0,50}([\d一二三四五六七八九十]+月|年[\d一二三四五六七八九十]+回)",
            },
            "退職": {
                "申出期間": r"(退職).{0,30}([\d一二三四五六七八九十]+[日月ヶ]前)",
                "手続き": r"(退職).{0,20}(手続|届|願)",
                "引継ぎ": r"(引[継き]|引渡).{0,50}",
            }
        }
    
    def extract_information(self, text: str, topic: str) -> Dict[str, str]:
        """
        テキストから特定トピックの情報を抽出
        
        Args:
            text: 検索対象テキスト
            topic: トピック（育児休業、有給休暇など）
            
        Returns:
            抽出された情報の辞書
        """
        extracted = {}
        
        if topic not in self.patterns:
            return extracted
        
        patterns = self.patterns[topic]
        
        for key, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                # 最も関連性の高いマッチを選択
                if isinstance(matches[0], tuple):
                    extracted[key] = " ".join(str(m) for m in matches[0] if m)
                else:
                    extracted[key] = matches[0]
        
        return extracted
    
    def identify_topic(self, query: str) -> Optional[str]:
        """
        クエリからトピックを特定
        
        Args:
            query: ユーザーのクエリ
            
        Returns:
            特定されたトピック
        """
        query_lower = query.lower()
        
        topic_keywords = {
            "育児休業": ["育児", "育休", "産休", "子育て", "出産"],
            "有給休暇": ["有給", "有休", "年休", "年次休暇"],
            "労働時間": ["労働時間", "勤務時間", "残業", "時間外", "所定"],
            "給与": ["給与", "給料", "賃金", "締日", "支払日", "賞与"],
            "退職": ["退職", "辞職", "離職", "退社"],
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return topic
        
        return None
    
    def analyze_negative_query(self, query: str, text: str) -> Dict[str, List[str]]:
        """
        否定的な質問（〜できない、対象外など）を分析
        
        Args:
            query: クエリ
            text: テキスト
            
        Returns:
            除外条件などの情報
        """
        result = {"exclusions": [], "conditions": []}
        
        # 除外パターンを探す
        exclusion_patterns = [
            r"次[のに掲げる].{0,50}(者|場合|とき)は.{0,20}(除く|除外|対象外|適用しない)",
            r"(ただし|但し).{0,100}(除く|除外|できない)",
            r"以下[のに該当].{0,50}場合.{0,20}(除く|除外|不可)",
            r"([\d一二三四五六七八九十]+).{0,10}(除外|対象外|適用しない)",
        ]
        
        for pattern in exclusion_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    result["exclusions"].append(" ".join(str(m) for m in match if m))
                else:
                    result["exclusions"].append(match)
        
        # 一般的な除外条件を探す
        common_exclusions = [
            ("雇用期間", r"雇用.{0,10}期間.{0,30}([\d一二三四五六七八九十]+[年月日]|未満|以[上下内])"),
            ("労働日数", r"(週|月).{0,10}(所定)?労働日.{0,20}([\d一二三四五六七八九十]+日)"),
            ("雇用形態", r"(日々雇用|日雇|臨時|試用期間)"),
        ]
        
        for label, pattern in common_exclusions:
            if re.search(pattern, text, re.IGNORECASE):
                result["conditions"].append(label)
        
        return result
    
    def generate_answer(
        self,
        query: str,
        hits: List[Any],  # SearchHitまたは互換オブジェクト
        context: Optional[str] = None
    ) -> str:
        """
        インテリジェントな回答を生成
        
        Args:
            query: ユーザーのクエリ
            hits: 検索結果
            context: 前の会話の文脈
            
        Returns:
            生成された回答
        """
        if not hits:
            return "申し訳ございません。該当する情報が見つかりませんでした。"
        
        best_hit = hits[0]
        text = best_hit.text
        
        # トピックを特定
        topic = self.identify_topic(query)
        if context and not topic:
            topic = self.identify_topic(context)
        
        # 否定的な質問かチェック
        is_negative = any(word in query for word in ["取れない", "できない", "対象外", "除外", "例外"])
        
        answer_parts = []
        
        if is_negative:
            # 除外条件を探す
            negative_info = self.analyze_negative_query(query, text)
            
            if negative_info["exclusions"] or negative_info["conditions"]:
                answer_parts.append(f"🚫 **{topic or '該当'}の除外条件・制限**\n")
                
                # テキストから具体的な除外条件を抽出
                for exclusion in negative_info["exclusions"]:
                    answer_parts.append(f"• {exclusion}")
                
                # 一般的な条件
                if negative_info["conditions"]:
                    answer_parts.append("\n**一般的な制限事項:**")
                    for condition in negative_info["conditions"]:
                        answer_parts.append(f"• {condition}に関する制限あり")
            else:
                # デフォルトの除外条件
                answer_parts.append(f"🚫 **一般的な除外条件**\n")
                answer_parts.append("※ 詳細は該当規程をご確認ください")
        
        else:
            # 通常の質問
            if topic:
                # トピックに応じた情報抽出
                extracted = self.extract_information(text, topic)
                
                # アイコンを選択
                icons = {
                    "育児休業": "👶",
                    "有給休暇": "🏖️",
                    "労働時間": "⏰",
                    "給与": "💰",
                    "退職": "📝"
                }
                icon = icons.get(topic, "📄")
                
                answer_parts.append(f"{icon} **{topic}について**\n")
                
                # 情報抽出を試みる
                extracted = self.extract_information(text, topic)
                
                # 抽出された情報があれば表示、なければ要約を作成
                if extracted:
                    # 抽出された情報を整形
                    for key, value in extracted.items():
                        if value and len(value) > 5:  # 短すぎる値は除外
                            formatted_key = key.replace("_", " ").title()
                            answer_parts.append(f"• {formatted_key}: {value}")
                
                # 要約も追加（抽出情報の補完として）
                summary = self._create_summary(text, query)
                if summary:
                    answer_parts.append(f"\n**詳細情報:**\n{summary}")
            else:
                # トピック不明の場合は要約
                summary = self._create_summary(text, query)
                answer_parts.append(f"📄 **関連情報**\n{summary}")
        
        # 回答を結合
        answer = "\n".join(answer_parts)
        
        # 注意書きを追加
        if not answer_parts or "詳細は" not in answer:
            answer += "\n\n※ 詳細は該当規程をご確認ください"
        
        return answer
    
    def _extract_additional_info(self, text: str, topic: str) -> str:
        """
        追加情報を抽出
        """
        # トピックごとの追加情報パターン
        additional_patterns = {
            "育児休業": [
                (r"申[請出].{0,30}([\d一二三四五六七八九十]+[日月ヶ]前)", "申請期限: {}"),
                (r"必要書類.{0,50}", "{}"),
            ],
            "有給休暇": [
                (r"取得単位.{0,30}(半日|時間|日)", "取得単位: {}"),
                (r"申請.{0,30}([\d一二三四五六七八九十]+日前)", "申請: {}"),
            ],
        }
        
        if topic not in additional_patterns:
            return ""
        
        info_parts = []
        for pattern, format_str in additional_patterns[topic]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    info_parts.append(format_str.format(match.group(1)))
                else:
                    info_parts.append(format_str.format(match.group(0)))
        
        return "\n".join(info_parts)
    
    def _create_summary(self, text: str, query: str) -> str:
        """
        テキストの要約を作成（改善版）
        """
        # より適切な文の分割
        import re
        sentences = re.split(r'[。\n]', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        # クエリから重要なキーワードを抽出
        from pdf.search import extract_keywords
        keywords = extract_keywords(query)
        
        # 関連度の高い文を抽出
        scored_sentences = []
        for sentence in sentences[:20]:  # 最初の20文をチェック
            score = 0
            for keyword in keywords:
                if keyword in sentence:
                    score += 1
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # スコア順にソート
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        if scored_sentences:
            # 最も関連度の高い2-3文を選択
            result_sentences = [s[1] for s in scored_sentences[:3]]
            # 元のテキストでの出現順に並べ替え
            result_sentences.sort(key=lambda s: text.find(s))
            return "。".join(result_sentences) + "。"
        else:
            # 関連文が見つからない場合は、規程の主要部分を抽出
            important_patterns = [
                r'第[\d一二三四五六七八九十]+条.*?ができる',
                r'希望する.*?とする',
                r'申出.*?できる',
                r'対象.*?とする'
            ]
            
            for pattern in important_patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    return match.group(0)[:200]
            
            # それでも見つからない場合は最初の文を返す
            return sentences[0] if sentences else text[:200]


# グローバルインスタンス
_answer_generator = None


def get_answer_generator() -> IntelligentAnswerGenerator:
    """回答生成器のインスタンスを取得"""
    global _answer_generator
    if _answer_generator is None:
        _answer_generator = IntelligentAnswerGenerator()
    return _answer_generator


def generate_intelligent_answer(
    query: str,
    hits: List[Any],  # SearchHitまたは互換オブジェクト
    context: Optional[str] = None
) -> str:
    """
    インテリジェントな回答を生成（エントリーポイント）
    """
    generator = get_answer_generator()
    return generator.generate_answer(query, hits, context)