"""
クエリ解析とコンテキスト理解モジュール
ユーザーの入力を詳細に分析し、検索精度を向上させる
"""
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import re
from loguru import logger


@dataclass
class QueryIntent:
    """クエリの意図を表すクラス"""
    original_query: str  # 元のクエリ
    normalized_query: str  # 正規化されたクエリ
    keywords: List[str]  # 重要キーワード
    synonyms: Dict[str, List[str]]  # 同義語マッピング
    query_type: str  # 質問タイプ（条件、手続き、定義など）
    context_keywords: List[str]  # コンテキストから抽出したキーワード


class QueryAnalyzer:
    """クエリを分析し、検索精度を向上させるクラス"""
    
    # よくある同義語・表記ゆれの辞書
    SYNONYM_DICT = {
        "有給": ["有給休暇", "有休", "年次有給休暇", "年休", "有給休暇"],
        "給与": ["給料", "賃金", "報酬", "給与", "サラリー"],
        "残業": ["時間外勤務", "時間外労働", "超過勤務", "残業"],
        "休暇": ["休み", "休暇", "お休み", "休日"],
        "申請": ["申し込み", "届出", "届け出", "申請", "手続き"],
        "締切": ["締め切り", "期限", "締切日", "締切", "デッドライン"],
        "勤務": ["労働", "仕事", "業務", "勤務", "ワーク"],
        "退職": ["辞職", "離職", "退社", "退職"],
        "産休": ["産前産後休暇", "産前産後休業", "出産休暇", "産休"],
        "育休": ["育児休暇", "育児休業", "育休"],
        "遅刻": ["遅れ", "遅参", "遅刻"],
        "早退": ["早引け", "早帰り", "早退"],
        "欠勤": ["休み", "欠席", "不在", "欠勤"],
        "振替": ["振り替え", "代休", "振替休日", "振替"],
        "賞与": ["ボーナス", "賞与金", "特別手当", "賞与"],
    }
    
    # クエリタイプを判定するパターン
    QUERY_PATTERNS = {
        "条件": ["条件", "場合", "とき", "資格", "要件", "必要"],
        "手続き": ["方法", "手順", "やり方", "申請", "どうやって", "どのように"],
        "定義": ["とは", "って何", "意味", "定義", "説明"],
        "期限": ["いつまで", "締切", "期限", "期日", "まで"],
        "金額": ["いくら", "金額", "額", "円", "料金", "費用"],
        "期間": ["期間", "どのくらい", "何日", "何ヶ月", "何年"],
        "可否": ["できる", "可能", "してもいい", "許可", "禁止"],
    }
    
    def __init__(self):
        """初期化"""
        self.context_history: List[str] = []  # 会話履歴
    
    def analyze(self, query: str, context: Optional[List[str]] = None) -> QueryIntent:
        """
        クエリを分析して検索に最適化された情報を返す
        
        Args:
            query: ユーザーの入力クエリ
            context: 会話の文脈（過去の質問など）
            
        Returns:
            QueryIntent: 分析結果
        """
        # コンテキストの更新
        if context:
            self.context_history = context
        
        # クエリの正規化
        normalized = self._normalize_query(query)
        
        # キーワード抽出
        keywords = self._extract_keywords(normalized)
        
        # 同義語展開
        synonyms = self._expand_synonyms(keywords)
        
        # クエリタイプ判定
        query_type = self._determine_query_type(normalized)
        
        # コンテキストからのキーワード抽出
        context_keywords = self._extract_context_keywords()
        
        logger.info(f"Query analyzed: {query} -> keywords={keywords}, type={query_type}")
        
        return QueryIntent(
            original_query=query,
            normalized_query=normalized,
            keywords=keywords,
            synonyms=synonyms,
            query_type=query_type,
            context_keywords=context_keywords
        )
    
    def _normalize_query(self, query: str) -> str:
        """
        クエリを正規化する（表記ゆれの統一）
        
        Args:
            query: 元のクエリ
            
        Returns:
            正規化されたクエリ
        """
        normalized = query
        
        # 全角英数を半角に
        normalized = self._zenkaku_to_hankaku(normalized)
        
        # カタカナ表記の統一（例：ヴァ→バ）
        normalized = normalized.replace("ヴァ", "バ").replace("ヴィ", "ビ")
        normalized = normalized.replace("ヴ", "ブ")
        
        # 句読点の統一
        normalized = normalized.replace("。", " ").replace("、", " ")
        normalized = normalized.replace("？", "?").replace("！", "!")
        
        # 連続スペースを単一スペースに
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized.strip()
    
    def _zenkaku_to_hankaku(self, text: str) -> str:
        """全角英数を半角に変換"""
        # 全角数字を半角に
        text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        # 全角英字を半角に
        text = text.translate(str.maketrans(
            'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
        ))
        return text
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        重要なキーワードを抽出
        
        Args:
            query: 正規化されたクエリ
            
        Returns:
            キーワードのリスト
        """
        keywords = []
        
        # 名詞と思われる単語を抽出（簡易版）
        # より高度な実装では形態素解析を使用
        patterns = [
            r'[一-龥ー]{2,}',  # 2文字以上の漢字・カタカナ
            r'[ァ-ヶー]{2,}',  # 2文字以上のカタカナ
            r'[a-zA-Z]+',  # 英単語
            r'\d+',  # 数字
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query)
            keywords.extend(matches)
        
        # ストップワードの除去
        stopwords = ['する', 'なる', 'ある', 'いる', 'れる', 'られる', 'こと', 'もの']
        keywords = [k for k in keywords if k not in stopwords]
        
        # 重複除去
        return list(dict.fromkeys(keywords))
    
    def _expand_synonyms(self, keywords: List[str]) -> Dict[str, List[str]]:
        """
        キーワードの同義語を展開
        
        Args:
            keywords: キーワードリスト
            
        Returns:
            同義語辞書
        """
        synonym_map = {}
        
        for keyword in keywords:
            synonyms = []
            
            # 完全一致の同義語を探す
            for base_word, synonym_list in self.SYNONYM_DICT.items():
                if keyword == base_word or keyword in synonym_list:
                    synonyms.extend(synonym_list)
                    synonyms.append(base_word)
            
            # 部分一致の同義語を探す（慎重に）
            for base_word, synonym_list in self.SYNONYM_DICT.items():
                if len(keyword) >= 2 and keyword in base_word:
                    synonyms.extend(synonym_list)
                    synonyms.append(base_word)
            
            # 重複除去と自分自身を除外
            synonyms = [s for s in set(synonyms) if s != keyword]
            
            if synonyms:
                synonym_map[keyword] = synonyms
        
        return synonym_map
    
    def _determine_query_type(self, query: str) -> str:
        """
        クエリのタイプを判定
        
        Args:
            query: 正規化されたクエリ
            
        Returns:
            クエリタイプ
        """
        query_lower = query.lower()
        
        for query_type, patterns in self.QUERY_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return query_type
        
        return "一般"  # デフォルト
    
    def _extract_context_keywords(self) -> List[str]:
        """
        会話履歴からコンテキストキーワードを抽出
        
        Returns:
            コンテキストキーワードのリスト
        """
        context_keywords = []
        
        # 直近3つの会話から重要語を抽出
        for query in self.context_history[-3:]:
            normalized = self._normalize_query(query)
            keywords = self._extract_keywords(normalized)
            context_keywords.extend(keywords[:2])  # 各クエリから上位2個
        
        # 重複除去
        return list(dict.fromkeys(context_keywords))
    
    def add_to_context(self, query: str):
        """
        会話履歴にクエリを追加
        
        Args:
            query: 追加するクエリ
        """
        self.context_history.append(query)
        # 履歴は最大10件まで保持
        if len(self.context_history) > 10:
            self.context_history.pop(0)