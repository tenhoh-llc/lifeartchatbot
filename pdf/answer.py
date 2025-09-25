"""
質問に対する直接的な回答を生成するモジュール
抜粋から要点を抽出して、わかりやすい回答を作成
"""
from typing import List, Optional
from pdf.search import SearchHit
from pdf.snippet import Snippet


def generate_answer(query: str, hits: List[SearchHit], snippet: Snippet, context: str = None) -> str:
    """
    検索結果から質問に対する直接的な回答を生成
    
    Args:
        query: ユーザーの質問
        hits: 検索結果
        snippet: 抜粋
        context: 前の会話の文脈
    
    Returns:
        わかりやすい回答文
    """
    if not hits:
        return "申し訳ございません。該当する情報が見つかりませんでした。"
    
    best_hit = hits[0]
    text = best_hit.text.lower()
    query_lower = query.lower()
    
    # 文脈を考慮した回答の判定
    is_negative_query = any(word in query_lower for word in ["取れない", "できない", "対象外", "除外", "例外", "不可"])
    is_condition_query = any(word in query_lower for word in ["条件", "要件", "資格", "対象"])
    
    # 育児休業の文脈かどうか
    is_ikuji_context = context and "育" in context
    
    # キーワードベースの回答生成
    answers = []
    
    # 時間外勤務・残業
    if any(word in query_lower for word in ["時間外", "残業", "overtime"]):
        if "時間外勤務" in text or "残業" in text:
            # テキストから数値を抽出
            import re
            monthly = re.search(r'月(\d+)時間', best_hit.text)
            yearly = re.search(r'年(\d+)時間', best_hit.text)
            
            if monthly and yearly:
                answers.append(f"📋 **時間外勤務の上限**")
                answers.append(f"• 月間上限: {monthly.group(1)}時間")
                answers.append(f"• 年間上限: {yearly.group(1)}時間")
                answers.append(f"• 特別な事情がある場合は労使協定により延長可能です")
    
    # 有給休暇
    elif any(word in query_lower for word in ["有給", "有休", "年休"]):
        if "有給" in text or "有休" in text:
            import re
            days = re.search(r'年間(\d+)日', best_hit.text)
            max_days = re.search(r'最大(\d+)日', best_hit.text)
            
            if days:
                answers.append(f"🏖️ **有給休暇について**")
                answers.append(f"• 年間付与日数: {days.group(1)}日")
                if max_days:
                    answers.append(f"• 最大保有日数: {max_days.group(1)}日（繰越含む）")
                answers.append(f"• 翌年度への繰越が可能です")
    
    # 給与・給料
    elif any(word in query_lower for word in ["給与", "給料", "賃金", "支払"]):
        if "給与" in text or "給料" in text:
            import re
            closing = re.search(r'締日.*?(\d+)日', best_hit.text)
            payment = re.search(r'支払.*?(\d+)日', best_hit.text)
            
            if closing or payment:
                answers.append(f"💰 **給与支払について**")
                if closing:
                    answers.append(f"• 締日: 毎月{closing.group(1)}日")
                if payment:
                    answers.append(f"• 支払日: 翌月{payment.group(1)}日")
                answers.append(f"• 支払日が休日の場合は前営業日に支払")
    
    # 育児休業関連の質問を詳細に処理
    elif any(word in query_lower for word in ["育児", "育休", "産休"]) or is_ikuji_context:
        # 否定的な質問（取れない人、対象外など）
        if is_negative_query or "対象外" in text or "除外" in text:
            # テキストから対象外条件を探す
            import re
            exclusions = []
            
            # よくある除外パターンを探す
            if "雇用期間" in text or "１年未満" in text:
                exclusions.append("• 雇用期間が1年未満の従業員")
            if "有期雇用" in text or "期間" in text:
                exclusions.append("• 有期雇用で契約期間が限定されている場合")
            if "日々雇用" in text:
                exclusions.append("• 日々雇用の従業員")
            if "週" in text and ("２日" in text or "3日" in text):
                exclusions.append("• 週の所定労働日数が2日以下の従業員")
            
            if exclusions:
                answers.append(f"🚫 **育児休業を取得できない場合**")
                answers.extend(exclusions)
                answers.append("※ 詳細は育児介護休業規程をご確認ください")
            else:
                # 一般的な除外条件を提示
                answers.append(f"🚫 **一般的に育児休業を取得できない場合**")
                answers.append(f"• 雇用期間が1年未満")
                answers.append(f"• 1年以内に雇用関係が終了する予定")
                answers.append(f"• 週の所定労働日数が2日以下")
                answers.append(f"※ 正確な条件は育児介護休業規程をご確認ください")
        else:
            # 通常の育児休業の説明
            answers.append(f"👶 **育児休業について**")
            answers.append(f"• 基本期間: 子が1歳に達するまで")
            answers.append(f"• 延長可能: 最大2歳まで（保育園に入れない等の事情がある場合）")
            answers.append(f"• 申請は人事部まで")
    
    # 時短勤務
    elif any(word in query_lower for word in ["時短", "短時間", "時間短縮"]):
        if "時短" in text or "短時間" in text:
            answers.append(f"⏰ **時短勤務制度**")
            answers.append(f"• 対象: 3歳未満の子を養育する社員")
            answers.append(f"• 勤務時間: 1日6時間")
            answers.append(f"• 申請は上長と人事部へ")
    
    # デフォルト回答
    if not answers:
        # 抜粋から最初の1文を取得
        first_sentence = best_hit.text.split("。")[0] if "。" in best_hit.text else best_hit.text[:100]
        answers.append(f"📄 **関連情報**")
        answers.append(first_sentence + "。")
    
    return "\n".join(answers)


def format_full_answer(
    query: str,
    answer: str,
    snippet: Snippet,
    source: SearchHit
) -> dict:
    """
    完全な回答をフォーマット
    
    Returns:
        dict: 回答、根拠、出典を含む辞書
    """
    return {
        "answer": answer,
        "evidence": snippet.excerpt,
        "source": {
            "file": source.file_name,
            "page": source.page_no,
            "section": source.section,
            "score": source.score
        },
        "disclaimer": "※ この回答は規程文書からの抜粋に基づいています。正式な確認は原本をご参照ください。"
    }


def generate_qa_style_response(query: str, hits: List[SearchHit]) -> str:
    """
    Q&A形式のレスポンスを生成
    
    Args:
        query: 質問
        hits: 検索結果
    
    Returns:
        Q&A形式の回答
    """
    if not hits:
        return "該当する情報が見つかりませんでした。別のキーワードでお試しください。"
    
    response = []
    response.append(f"**Q: {query}**\n")
    
    # メイン回答
    answer = generate_answer(query, hits, None)
    response.append(f"**A:** {answer}\n")
    
    # 関連情報
    if len(hits) > 1:
        response.append("\n**📚 関連する規程:**")
        for i, hit in enumerate(hits[:3], 1):
            if hit.section:
                response.append(f"{i}. {hit.section} ({hit.file_name} p.{hit.page_no})")
    
    return "\n".join(response)