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
