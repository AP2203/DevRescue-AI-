import os
import re
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.nemotron_service import nemotron_service, _sanitize_error

class NebiusService:
    """
    Integration abstraction for NVIDIA Nemotron LLMs.
    Backed by NemotronService and settings.
    """
    @property
    def api_key(self) -> Optional[str]:
        return settings.NVIDIA_API_KEY

    @property
    def base_url(self) -> str:
        return settings.NVIDIA_BASE_URL

    @property
    def model_name(self) -> str:
        return settings.NEMOTRON_MODEL

    def is_configured(self) -> bool:
        return bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip())

    async def generate_code_repair(
        self,
        repo: str,
        issue_title: str,
        error_description: str,
        code_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes a minimal patch using NVIDIA Nemotron.
        Returns status 'unavailable' if credentials are not configured.
        """
        if not self.is_configured():
            return {
                "status": "unavailable",
                "message": "AI repair service unavailable - NVIDIA_API_KEY not configured",
                "patch": None,
                "model": self.model_name
            }

        try:
            client = nemotron_service.get_client()
            prompt = (
                f"Repository: {repo}\n"
                f"Issue Title: {issue_title}\n"
                f"Error Description: {error_description}\n"
                f"Code Context:\n{code_context or 'No additional context provided'}\n\n"
                f"Generate a minimal unified diff patch (starting with --- a/ and +++ b/) that resolves this bug."
            )
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are DevRescue AI code repair agent. "
                            "Output ONLY a minimal unified diff patch for the described issue. "
                            "Do not include conversational preamble or markdown code blocks unless it is diff formatted."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1024
            )
            if not response.choices or not response.choices[0].message.content:
                return {
                    "status": "error",
                    "message": "Nemotron returned an empty response",
                    "patch": None,
                    "model": self.model_name
                }

            patch_content = response.choices[0].message.content.strip()
            # Clean markdown code block fences if present
            if "```diff" in patch_content:
                m = re.search(r'```diff\s*(.*?)\s*```', patch_content, re.DOTALL)
                if m:
                    patch_content = m.group(1).strip()
            elif "```" in patch_content:
                m = re.search(r'```\s*(.*?)\s*```', patch_content, re.DOTALL)
                if m:
                    patch_content = m.group(1).strip()

            if "--- " not in patch_content or "+++ " not in patch_content:
                return {
                    "status": "error",
                    "message": "Model output did not contain valid unified diff headers (--- / +++)",
                    "patch": None,
                    "model": self.model_name
                }

            return {
                "status": "success",
                "patch": patch_content,
                "model": self.model_name
            }
        except Exception as e:
            return {
                "status": "error",
                "message": _sanitize_error(e),
                "patch": None,
                "model": self.model_name
            }

nebius_service = NebiusService()

