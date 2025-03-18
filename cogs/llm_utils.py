# cogs/llm_utils.py
import aiohttp
import json

async def call_local_llm(
    messages,
    default_model="qwen2.5-14b-instruct",
    url="http://localhost:1234/v1/chat/completions",
    model_override=None
):
    """
    Example LLM call to a local endpoint.
    If model_override is given, we use that model instead of default_model.
    """
    headers = {"Content-Type": "application/json"}
    chosen_model = model_override or default_model

    payload = {
        "model": chosen_model,
        "messages": messages,
        "temperature": 0.8,
        "top_k": 40,
        "top_p": 0.95
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=payload, timeout=120) as response:
                if response.status != 200:
                    return {
                        "message": f"[ERROR] HTTP {response.status} from LLM server.",
                        "tool_calls": []
                    }
                data = await response.json()
                raw_content = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw_content)
                return parsed
        except aiohttp.ClientError as e:
            return {"message": f"[ERROR] ClientError: {str(e)}", "tool_calls": []}
        except (KeyError, json.JSONDecodeError) as e:
            return {"message": f"[ERROR] Parsing LLM response: {str(e)}", "tool_calls": []}

async def setup(bot):
    pass
