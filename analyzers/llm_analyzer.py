"""LLMによる企業課題分析"""

import json

import anthropic

from config.prompts import COMPANY_ANALYSIS_PROMPT
from config.settings import ANTHROPIC_API_KEY, CLAUDE_MAX_TOKENS, CLAUDE_MODEL
from sheets.models import Analysis


class LLMAnalyzer:
    """Claude APIを使用して企業の課題分析を行う"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def analyze(
        self,
        company_name: str,
        company_url: str,
        scraped_content: str,
        enriched_content: str = "",
    ) -> Analysis | None:
        """企業情報を分析してAnalysisモデルを返す"""
        prompt = COMPANY_ANALYSIS_PROMPT.format(
            company_name=company_name,
            company_url=company_url,
            scraped_content=scraped_content,
            enriched_content=enriched_content or "（外部ソースからの追加情報はありません）",
        )

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            print(f"Claude API呼び出しエラー: {e}")
            return None

        return self._parse_response(response.content[0].text)

    def _parse_response(self, response_text: str) -> Analysis | None:
        """LLMの応答をパースしてAnalysisモデルに変換"""
        try:
            # JSONブロックを抽出
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]

            data = json.loads(json_match.strip())
            # パースしたJSON全体を保持（連絡先情報等の取得用）
            self._last_parsed_data = data

            challenges = data.get("estimated_challenges", [])
            if isinstance(challenges, list):
                challenges = " / ".join(challenges)

            needs = data.get("estimated_needs", [])
            if isinstance(needs, list):
                needs = " / ".join(needs)

            efforts = data.get("health_management_efforts", "")
            if isinstance(efforts, list):
                efforts = " / ".join(efforts)

            return Analysis(
                company_id="",  # 呼び出し側で設定
                industry=data.get("industry", ""),
                employee_scale=data.get("employee_scale", ""),
                health_management_efforts=efforts,
                estimated_challenges=challenges,
                estimated_needs=needs,
                confidence_score=float(data.get("confidence_score", 0.0)),
                analysis_notes=data.get("analysis_notes", ""),
            )
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"LLM応答のパースに失敗: {e}")
            print(f"応答テキスト: {response_text[:500]}")
            return None

    def fill_missing_fields(self, company_name: str, company_url: str, current_data: dict) -> dict:
        """空のフィールドをLLMの知識で補完する2回目の呼び出し"""
        # 空のフィールドを特定
        all_fields = [
            "representative", "established", "capital", "revenue", "listed",
            "employee_scale", "phone", "address", "email", "fax",
            "contact_url", "contact_form_url", "industry",
        ]
        missing = [f for f in all_fields if not current_data.get(f)]

        if not missing:
            return current_data

        missing_desc = {
            "representative": "代表者名（例：代表取締役社長 山田太郎）",
            "established": "設立年（例：2005年3月）",
            "capital": "資本金（例：1,000万円、3億円）",
            "revenue": "売上高（例：約10億円）。不明なら事業規模から推定し「推定○○円」と記載",
            "listed": "上場区分（東証プライム/スタンダード/グロース/非上場）",
            "employee_scale": "従業員規模（例：約50名）。不明なら推定し「推定○○名」と記載",
            "phone": "代表電話番号（例：03-1234-5678）",
            "address": "本社所在地（例：東京都千代田区丸の内1-1-1）",
            "email": "メールアドレス（info@ドメイン等の推定も可）",
            "fax": "FAX番号",
            "contact_url": "問い合わせページURL（企業URL + /contact/ 等の推定も可）",
            "contact_form_url": "問い合わせフォームURL",
            "industry": "業種",
        }

        fields_text = "\n".join(f'    "{f}": "{missing_desc[f]}"' for f in missing)

        prompt = f"""あなたは企業情報の専門家です。以下の企業について、不足している情報を**あなたの学習済み知識を最大限活用して**回答してください。

企業名: {company_name}
企業URL: {company_url}

既に判明している情報:
{json.dumps({k: v for k, v in current_data.items() if v}, ensure_ascii=False, indent=2)}

以下の不足項目をJSON形式で回答してください。**推定でもいいので必ず値を入れてください。**
推定値には「推定」と明記してください。本当に推定すら不可能な場合のみ空文字にしてください。

```json
{{
{fields_text}
}}
```

重要:
- あなたが知っている情報は必ず記入すること
- 企業URLのドメインからメールアドレスを推定可能（例: info@example.co.jp）
- 企業URLに/contact/を付ければ問い合わせURLを推定可能
- 上場/非上場は必ず判定できるはず
- JSONのみ回答し、説明は不要です
"""

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            print(f"補完LLM呼び出しエラー: {e}")
            return current_data

        try:
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            fill_data = json.loads(text.strip())

            # 空のフィールドのみ補完
            for k, v in fill_data.items():
                if v and not current_data.get(k):
                    current_data[k] = v

        except (json.JSONDecodeError, IndexError) as e:
            print(f"補完LLMパースエラー: {e}")

        return current_data

    def get_contact_info(self) -> dict:
        """直前の分析結果から連絡先情報を取得（analyzeの後に呼ぶ）"""
        data = getattr(self, "_last_parsed_data", {})
        return {
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "fax": data.get("fax", ""),
            "address": data.get("address", ""),
            "contact_url": data.get("contact_url", ""),
            "contact_form_url": data.get("contact_form_url", ""),
        }
