
import json
import os

from groq import Groq

from schemas import TestPlan


class GroqPlanner:
    def __init__(self, model=None):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is missing. Add it to your .env file."
            )

        self.client = Groq(api_key=api_key)
        self.model = model or os.getenv(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile",
        )

    def generate_plan(self, user_test, page_snapshot, page_url):
        system_prompt = """
You are an expert browser QA automation planner.

Convert the user's natural-language test into a valid JSON TestPlan.

Allowed actions:
CLICK, TYPE, SELECT, ASSERT_TEXT, ASSERT_URL, WAIT, PRESS_ENTER

Schema:
{
  "test_name": "string",
  "description": "string",
  "steps": [
    {
      "action": "CLICK | TYPE | SELECT | ASSERT_TEXT | ASSERT_URL | WAIT | PRESS_ENTER",
      "element_description": "string or null",
      "value": "string or null",
      "expected_text": "string or null",
      "expected_url": "string or null",
      "timeout_seconds": 10,
      "description": "string"
    }
  ]
}

Rules:
- Return ONLY JSON. No markdown fences.
- Never invent page elements.
- Use semantic element descriptions, not XPath or CSS.
- Use ASSERT_TEXT for verifying visible text.
- Use ASSERT_URL for URL checks.
- For page title, use element_description: "page title".
- For body content, use element_description: "main body".
- TYPE must include element_description and value.
- SELECT must include element_description and value.
- CLICK must include element_description.
- PRESS_ENTER must include element_description.
- WAIT can use value as seconds.
- Prefer short, deterministic test plans.
- Include verification steps after meaningful interactions.
"""

        user_prompt = f"""
User test:
{user_test}

Page URL:
{page_url}

Current page snapshot:
{page_snapshot[:12000]}

Generate the TestPlan JSON.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        if not content:
            raise RuntimeError("Groq returned an empty response.")

        data = json.loads(content)
        return TestPlan.model_validate(data)
