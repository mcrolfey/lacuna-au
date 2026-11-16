"""Thin client for LM Studio's OpenAI-compatible server."""
import json
import re

from openai import OpenAI


class LMStudio:
    def __init__(self, cfg: dict):
        c = cfg["lmstudio"]
        self.client = OpenAI(base_url=c["base_url"], api_key=c["api_key"])
        self.chat_model = c["chat_model"]
        self.verifier_model = c.get("verifier_model") or c["chat_model"]
        self.embed_model = c["embed_model"]
        self.temperature = c.get("temperature", 0.2)
        self.max_tokens = c.get("max_tokens", 2048)

    def chat(self, system: str, user: str, model: str | None = None) -> str:
        max_tokens = self.max_tokens
        for attempt in range(2):
            resp = self.client.chat.completions.create(
                model=model or self.chat_model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=self.temperature,
                max_tokens=max_tokens,
            )
            choice = resp.choices[0]
            text = choice.message.content or ""
            # Reasoning models can spend the whole budget thinking and never answer: retry once with more room.
            if text.strip() or choice.finish_reason != "length":
                break
            if attempt == 0:
                print(f"   (model ran out of tokens while thinking; retrying with max_tokens={max_tokens * 3})")
                max_tokens *= 3
        if not text.strip() and choice.finish_reason == "length":
            print("   warning: model gave no answer within max_tokens; raise lmstudio.max_tokens in config.yaml")
        # Reasoning models (e.g. Qwen3) may emit <think>...</think>; drop it.
        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

    def chat_json(self, system: str, user: str, model: str | None = None):
        """Ask for JSON and parse it leniently. Returns None if unparseable."""
        text = self.chat(system + "\n\nRespond with valid JSON only, no prose.", user, model)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        for candidate in (text, _first_json_block(text)):
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        return None

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.embed_model, input=texts)
        return [d.embedding for d in resp.data]

    def ping(self) -> list[str]:
        return [m.id for m in self.client.models.list().data]


def _first_json_block(text: str) -> str | None:
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    return m.group(1) if m else None
