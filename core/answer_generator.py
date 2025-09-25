"""
回答生成モジュール
検索結果から分かりやすい回答と根拠を生成
"""
from dataclasses import dataclass
from typing import List, Optional, Dict
import re
from loguru import logger
from pdf.advanced_search import SearchResult


@dataclass
class Answer:
    """生成された回答"""
    summary: str  # 要約された回答
    evidence_snippets: List[Dict]  # 根拠となる抜粋
    confidence_score: float  # 回答の確信度
    answer_type: str  # 回答タイプ（直接回答、関連情報、など）


class AnswerGenerator:
    """検索結果から回答を生成するクラス"""
    
    def __init__(self):
        """初期化"""
        self.template_patterns = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """回答テンプレートを定義"""
        return {
            "条件": "【条件について】\n{content}\n\n該当する場合の詳細は規程をご確認ください。",
            "手続き": "【手続き方法】\n{content}\n\n必要書類や詳細は担当部署にご確認ください。",
            "期限": "【期限・期日】\n{content}\n\n期限厳守でお願いします。",
            "金額": "【金額・費用】\n{content}\n\n詳細な計算方法は規程をご参照ください。",
            "定義": "【定義・説明】\n{content}",
            "可否": "【可否について】\n{content}\n\n個別の事情については担当部署にご相談ください。",
            "一般": "{content}"
        }
    
    def generate(self, search_results: List[SearchResult], query_type: str = "一般") -> Answer:
        """
        検索結果から回答を生成
        
        Args:
            search_results: 検索結果リスト
            query_type: クエリのタイプ
            
        Returns:
            生成された回答
        """
        if not search_results:
            return self._generate_no_result_answer()
        
        # 最も関連性の高い結果から回答を生成
        primary_result = search_results[0]
        
        # 根拠となる抜粋を作成
        evidence_snippets = self._create_evidence_snippets(search_results)
        
        # 要約を生成
        summary = self._generate_summary(search_results, query_type)
        
        # 確信度を計算
        confidence = self._calculate_confidence(search_results)
        
        # 回答タイプを判定
        answer_type = self._determine_answer_type(confidence, search_results)
        
        logger.info(f"Answer generated with confidence: {confidence:.2f}")
        
        return Answer(
            summary=summary,
            evidence_snippets=evidence_snippets,
            confidence_score=confidence,
            answer_type=answer_type
        )
    
    def _generate_no_result_answer(self) -> Answer:
        """検索結果がない場合の回答"""
        return Answer(
            summary="申し訳ございません。お問い合わせの内容に該当する情報が見つかりませんでした。\n"
                   "別の表現でお試しいただくか、担当部署に直接お問い合わせください。",
            evidence_snippets=[],
            confidence_score=0.0,
            answer_type="no_result"
        )
    
    def _create_evidence_snippets(self, results: List[SearchResult]) -> List[Dict]:
        """
        根拠となる抜粋を作成
        
        Args:
            results: 検索結果
            
        Returns:
            抜粋リスト
        """
        snippets = []
        
        for i, result in enumerate(results[:3]):  # 上位3件まで
            # キーワードをハイライト
            highlighted_text = self._highlight_keywords(
                result.text,
                result.matched_keywords
            )
            
            # 重要部分を抽出（最大300文字）
            excerpt = self._extract_relevant_portion(
                highlighted_text,
                result.matched_keywords,
                max_length=300
            )
            
            snippet = {
                "rank": i + 1,
                "file_name": result.file_name,
                "page_no": result.page_no,
                "excerpt": excerpt,
                "relevance_reason": result.relevance_reason,
                "score": result.score,
                "section": result.section
            }
            snippets.append(snippet)
        
        return snippets
    
    def _highlight_keywords(self, text: str, keywords: List[str]) -> str:
        """
        キーワードをハイライト
        
        Args:
            text: テキスト
            keywords: キーワードリスト
            
        Returns:
            ハイライトされたテキスト
        """
        highlighted = text
        
        # 実際のキーワードのみ抽出（同義語表記を除く）
        actual_keywords = []
        for kw in keywords:
            if "(" not in kw:
                actual_keywords.append(kw)
            else:
                # "単語(説明)" の形式から単語部分を抽出
                match = re.match(r"([^(]+)\(", kw)
                if match:
                    actual_keywords.append(match.group(1))
        
        # キーワードを長い順にソート（長いものから置換して誤置換を防ぐ）
        actual_keywords.sort(key=len, reverse=True)
        
        for keyword in actual_keywords:
            # 大文字小文字を無視して置換
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted = pattern.sub(f"**{keyword}**", highlighted)
        
        return highlighted
    
    def _extract_relevant_portion(self, text: str, keywords: List[str], max_length: int = 300) -> str:
        """
        テキストから関連部分を抽出
        
        Args:
            text: テキスト
            keywords: キーワード
            max_length: 最大文字数
            
        Returns:
            抽出された部分
        """
        if len(text) <= max_length:
            return text
        
        # キーワードが最初に出現する位置を探す
        first_keyword_pos = len(text)
        for keyword in keywords[:3]:  # 主要キーワード
            clean_keyword = keyword.split("(")[0] if "(" in keyword else keyword
            pos = text.lower().find(clean_keyword.lower())
            if pos >= 0 and pos < first_keyword_pos:
                first_keyword_pos = pos
        
        # キーワード周辺を抽出
        if first_keyword_pos < len(text):
            start = max(0, first_keyword_pos - 100)
            end = min(len(text), first_keyword_pos + max_length - 100)
            excerpt = text[start:end]
            
            # 文の途中で切れないように調整
            if start > 0:
                # 句読点を探す
                for sep in ["。", "、", "\n", " "]:
                    sep_pos = excerpt.find(sep)
                    if 0 < sep_pos < 50:
                        excerpt = excerpt[sep_pos + 1:]
                        break
                excerpt = "…" + excerpt
            
            if end < len(text):
                # 句読点を探す
                for sep in ["。", "、", "\n", " "]:
                    sep_pos = excerpt.rfind(sep)
                    if len(excerpt) - 50 < sep_pos < len(excerpt):
                        excerpt = excerpt[:sep_pos + 1]
                        break
                excerpt = excerpt + "…"
            
            return excerpt
        
        # キーワードが見つからない場合は先頭から抽出
        excerpt = text[:max_length]
        if len(text) > max_length:
            excerpt += "…"
        return excerpt
    
    def _generate_summary(self, results: List[SearchResult], query_type: str) -> str:
        """
        要約を生成
        
        Args:
            results: 検索結果
            query_type: クエリタイプ
            
        Returns:
            要約文
        """
        if not results:
            return ""
        
        primary_result = results[0]
        
        # 主要な情報を抽出
        key_info = self._extract_key_information(primary_result.text, primary_result.matched_keywords)
        
        # テンプレートに基づいて回答を構築
        template = self.template_patterns.get(query_type, self.template_patterns["一般"])
        
        # 複数の結果がある場合は統合
        if len(results) > 1 and results[1].score > results[0].score * 0.8:
            # 2番目の結果も重要な場合
            additional_info = self._extract_key_information(results[1].text, results[1].matched_keywords)
            if additional_info and additional_info != key_info:
                key_info += f"\n\nまた、{additional_info}"
        
        summary = template.format(content=key_info)
        
        # 注意事項を追加
        if query_type in ["条件", "手続き", "期限"]:
            summary += "\n\n※ 詳細は必ず原本の規程をご確認ください。"
        
        return summary
    
    def _extract_key_information(self, text: str, keywords: List[str]) -> str:
        """
        テキストから重要な情報を抽出
        
        Args:
            text: テキスト
            keywords: キーワード
            
        Returns:
            重要情報
        """
        # キーワード周辺の文を抽出
        sentences = self._split_into_sentences(text)
        relevant_sentences = []
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            # キーワードを含む文を優先
            for keyword in keywords[:3]:
                clean_keyword = keyword.split("(")[0] if "(" in keyword else keyword
                if clean_keyword.lower() in sentence_lower:
                    if sentence not in relevant_sentences:
                        relevant_sentences.append(sentence)
                    break
        
        # 最大3文まで
        key_sentences = relevant_sentences[:3]
        
        if not key_sentences:
            # キーワードを含む文が見つからない場合は先頭の文を使用
            key_sentences = sentences[:2]
        
        # 文を結合
        key_info = "".join(key_sentences)
        
        # 長すぎる場合は短縮
        if len(key_info) > 200:
            key_info = key_info[:200] + "…"
        
        return key_info
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        テキストを文に分割
        
        Args:
            text: テキスト
            
        Returns:
            文のリスト
        """
        # 句点で分割（ただし数字の後の句点は除く）
        sentences = re.split(r'(?<![0-9])。', text)
        
        # 空白文を除去して句点を戻す
        result = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                if not sentence.endswith("。"):
                    sentence += "。"
                result.append(sentence)
        
        return result
    
    def _calculate_confidence(self, results: List[SearchResult]) -> float:
        """
        回答の確信度を計算
        
        Args:
            results: 検索結果
            
        Returns:
            確信度（0-1）
        """
        if not results:
            return 0.0
        
        # 最高スコアを基準に正規化
        max_score = results[0].score
        if max_score == 0:
            return 0.0
        
        # 複数の要素から確信度を計算
        confidence = 0.0
        
        # 1. 最高スコアの絶対値（最大100と仮定）
        confidence += min(max_score / 100, 1.0) * 0.5
        
        # 2. マッチしたキーワード数
        keyword_count = len(results[0].matched_keywords)
        confidence += min(keyword_count / 5, 1.0) * 0.3
        
        # 3. 上位結果のスコア差（一貫性）
        if len(results) > 1:
            score_ratio = results[1].score / max_score
            consistency = 1.0 - score_ratio  # 差が大きいほど確信度高
            confidence += consistency * 0.2
        else:
            confidence += 0.2  # 結果が1つしかない場合
        
        return min(confidence, 1.0)
    
    def _determine_answer_type(self, confidence: float, results: List[SearchResult]) -> str:
        """
        回答タイプを判定
        
        Args:
            confidence: 確信度
            results: 検索結果
            
        Returns:
            回答タイプ
        """
        if not results:
            return "no_result"
        
        if confidence > 0.8:
            return "direct_answer"  # 直接回答
        elif confidence > 0.5:
            return "relevant_info"  # 関連情報
        else:
            return "partial_match"  # 部分的な一致