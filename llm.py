import json
import urllib.request
from constants import OLLAMA_URL, OLLAMA_MODEL


def parse_prompt_with_llm(user_text: str) -> dict:
    system_prompt = f"""### Role
You are a Market Research Analyst specialized in Product Extraction. Your goal is to extract specific commercial data points from entrepreneur queries.

### Extraction Logic
1. **product**: Identify the specific item being manufactured or sold.
2. **location**: The target city or region for sales.
3. **price_range**: This MUST be the **targeted selling price** of the product to the consumer.
   - Ignore marketing budgets, investment amounts, or company revenue.
   - If the user says "around 50k", provide a ±10% range: [45000, 55000].
   - If a specific range is mentioned (e.g., "50k to 60k"), return [50000, 60000].
   - If no price is mentioned, return null.
   - Convert "Lakh" to 100000 and "k" to 1000.

### Output Format
Return ONLY a valid JSON object. Do not include any conversational text, explanations, or markdown code blocks.

### Strict Constraint
The 'price_range' field must only contain the unit price of the item described. If the user mentions a marketing budget or an investment figure, do NOT extract it into this field.

### Examples
User: "I want to sell my brand of headphones in Delhi for around 2000. I have 1 Lakh to spend on ads."
Output: {{"product": "headphones", "location": "Delhi", "price_range": [1800, 2200]}}

User: "I have a laptop company DCS and I want to sell in Ahmedabad in the 50000 to 60000 range."
Output: {{"product": "laptop", "location": "Ahmedabad", "price_range": [50000, 60000]}}

### Current Task
User: "{user_text}"
Output:"""

    try:
        req_body = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": system_prompt,
        }).encode("utf-8")

        req = urllib.request.Request(
            OLLAMA_URL,
            data=req_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        full_text = ""
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                if not raw_line:
                    continue
                data = json.loads(raw_line.decode("utf-8"))
                if "response" in data:
                    full_text += data["response"]
                if data.get("done", False):
                    break

    except Exception as e:
        raise RuntimeError(f"Ollama connection error: {e}\n\nMake sure Ollama is running:  ollama serve")

    clean = full_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()

    try:
        result = json.loads(clean)
    except json.JSONDecodeError:
        raise RuntimeError(f"LLM returned invalid JSON:\n{full_text}")

    return result
