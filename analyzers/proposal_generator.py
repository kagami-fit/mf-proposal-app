"""提案文生成"""

import json

import anthropic

from config.prompts import PROPOSAL_GENERATION_PROMPT
from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    SERVICE_DESCRIPTION_FILE,
)
from sheets.models import Proposal


class ProposalGenerator:
    """Claude APIを使用して提案文を生成する"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._service_description = None

    @property
    def service_description(self) -> str:
        if self._service_description is None:
            if SERVICE_DESCRIPTION_FILE.exists():
                self._service_description = SERVICE_DESCRIPTION_FILE.read_text(
                    encoding="utf-8"
                )
            else:
                self._service_description = "（自社サービス情報が未設定です。knowledge/service_description.mdを作成してください。）"
        return self._service_description

    def generate(
        self,
        company_name: str,
        industry: str,
        employee_scale: str,
        health_management_efforts: str,
        estimated_challenges: str,
        estimated_needs: str,
        *,
        revision_instruction: str = "",
        previous_draft: str = "",
        tone: str = "丁寧",
        length_hint: str = "400〜600文字",
        reference_proposals: list[dict] | None = None,
    ) -> Proposal | None:
        """分析結果を基に提案文を生成

        Args:
            revision_instruction: やり直し時のユーザー指示（例: 「もっと簡潔に」「ROIに言及して」）
            previous_draft: やり直し時の前回生成文
            tone: 文体トーン（丁寧 / カジュアル / 簡潔）
            length_hint: 希望文字数（例: "400〜600文字"）
            reference_proposals: 参考にする過去の確定済み提案 [{"company_name": ..., "body": ...}, ...]
        """
        prompt = PROPOSAL_GENERATION_PROMPT.format(
            company_name=company_name,
            industry=industry,
            employee_scale=employee_scale,
            health_management_efforts=health_management_efforts,
            estimated_challenges=estimated_challenges,
            estimated_needs=estimated_needs,
            service_description=self.service_description,
        )

        # トーン・文字数のカスタマイズ
        if tone != "丁寧" or length_hint != "400〜600文字":
            prompt += f"\n\n## 追加の文体指定\n- トーン: {tone}\n- 本文の目安文字数: {length_hint}\n"

        # 過去の確定済み提案を参考情報として追加
        if reference_proposals:
            prompt += "\n\n## 参考: 過去に確定された提案文（トーンや構成を参考にしてください）\n"
            for ref in reference_proposals[:3]:
                prompt += f"\n### {ref['company_name']}宛\n{ref['body'][:500]}\n"

        messages = [{"role": "user", "content": prompt}]

        # やり直し: 前回の生成結果 + 修正指示を会話として渡す
        if previous_draft and revision_instruction:
            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": previous_draft},
                {"role": "user", "content": (
                    f"上記の提案文を以下の指示に従って修正してください。"
                    f"同じJSON形式で出力してください。\n\n"
                    f"## 修正指示\n{revision_instruction}"
                )},
            ]

        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=messages,
            )
        except anthropic.APIError as e:
            print(f"Claude API呼び出しエラー: {e}")
            return None

        return self._parse_response(response.content[0].text, company_name)

    def _parse_response(self, response_text: str, company_name: str) -> Proposal | None:
        """LLMの応答をパースしてProposalモデルに変換"""
        try:
            json_match = response_text
            if "```json" in response_text:
                json_match = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_match = response_text.split("```")[1].split("```")[0]

            data = json.loads(json_match.strip())

            key_points = data.get("key_points", [])
            if isinstance(key_points, list):
                key_points = " / ".join(key_points)

            return Proposal(
                company_id="",  # 呼び出し側で設定
                company_name=company_name,
                subject=data.get("subject", ""),
                body=data.get("body", ""),
                key_points=key_points,
                approval_status="未確認",
            )
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"提案文のパースに失敗: {e}")
            return None
