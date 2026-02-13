from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Callable, Optional

import httpx

from bookworm.config import AppConfig, TranslationProviderConfig
from bookworm.library.database import Database

log = logging.getLogger(__name__)

BATCH_SEPARATOR = "\n---\n"
BATCH_MAX_PARAGRAPHS = 20


class TranslationEngine:
    def __init__(self, config: AppConfig, db: Database) -> None:
        self._config = config
        self._db = db
        self._client: Optional[httpx.AsyncClient] = None
        self._cancel = False

    @property
    def provider(self) -> Optional[TranslationProviderConfig]:
        return self._config.get_active_provider()

    @property
    def target_lang(self) -> str:
        return self._config.translate_target_lang

    @property
    def is_configured(self) -> bool:
        p = self.provider
        if not p:
            return False
        if p.name == "ollama":
            return bool(p.base_url)
        return bool(p.api_key and p.base_url)

    def cancel(self) -> None:
        self._cancel = True

    def reset_cancel(self) -> None:
        self._cancel = False

    def is_translated(self, text: str) -> bool:
        if not text.strip():
            return True
        text_hash = self._make_hash(text, self.target_lang)
        return self._db.get_cached_translation(text_hash) is not None

    def get_cached(self, text: str) -> Optional[str]:
        if not text.strip():
            return ""
        text_hash = self._make_hash(text, self.target_lang)
        return self._db.get_cached_translation(text_hash)

    def count_translated(self, paragraphs: list[str]) -> int:
        count = 0
        for p in paragraphs:
            if self.is_translated(p):
                count += 1
        return count

    async def translate_batch(self, paragraphs: list[str]) -> list[str]:
        """Translate paragraphs in a single API call. Uses cache, batches uncached."""
        results: list[Optional[str]] = [None] * len(paragraphs)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, para in enumerate(paragraphs):
            if not para.strip():
                results[i] = ""
                continue
            cached = self.get_cached(para)
            if cached is not None:
                results[i] = cached
            else:
                uncached_indices.append(i)
                uncached_texts.append(para)

        if uncached_texts:
            translated_parts = await self._call_api_batch(uncached_texts)
            provider_name = self.provider.name if self.provider else "unknown"
            for j, idx in enumerate(uncached_indices):
                trans = translated_parts[j] if j < len(translated_parts) else ""
                results[idx] = trans
                self._db.cache_translation(
                    text_hash=self._make_hash(paragraphs[idx], self.target_lang),
                    source_text=paragraphs[idx],
                    translated_text=trans,
                    target_lang=self.target_lang,
                    provider=provider_name,
                )

        return [r or "" for r in results]

    async def translate_all(
        self,
        paragraphs: list[str],
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> list[str]:
        """Translate all paragraphs in batches. Calls on_progress(done, total) periodically."""
        results: list[str] = [""] * len(paragraphs)
        total = len(paragraphs)
        done = 0

        for i, para in enumerate(paragraphs):
            cached = self.get_cached(para)
            if cached is not None:
                results[i] = cached
                done += 1

        if on_progress:
            on_progress(done, total)

        batch_indices: list[int] = []
        batch_texts: list[str] = []

        for i, para in enumerate(paragraphs):
            if self._cancel:
                break
            if results[i]:
                continue
            if not para.strip():
                results[i] = ""
                done += 1
                continue

            batch_indices.append(i)
            batch_texts.append(para)

            if len(batch_texts) >= BATCH_MAX_PARAGRAPHS:
                translated = await self._call_api_batch(batch_texts)
                provider_name = self.provider.name if self.provider else "unknown"
                for j, idx in enumerate(batch_indices):
                    trans = translated[j] if j < len(translated) else ""
                    results[idx] = trans
                    self._db.cache_translation(
                        text_hash=self._make_hash(paragraphs[idx], self.target_lang),
                        source_text=paragraphs[idx],
                        translated_text=trans,
                        target_lang=self.target_lang,
                        provider=provider_name,
                    )
                done += len(batch_indices)
                if on_progress:
                    on_progress(done, total)
                batch_indices = []
                batch_texts = []
                await asyncio.sleep(0)

        if batch_texts and not self._cancel:
            translated = await self._call_api_batch(batch_texts)
            provider_name = self.provider.name if self.provider else "unknown"
            for j, idx in enumerate(batch_indices):
                trans = translated[j] if j < len(translated) else ""
                results[idx] = trans
                self._db.cache_translation(
                    text_hash=self._make_hash(paragraphs[idx], self.target_lang),
                    source_text=paragraphs[idx],
                    translated_text=trans,
                    target_lang=self.target_lang,
                    provider=provider_name,
                )
            done += len(batch_indices)
            if on_progress:
                on_progress(done, total)

        return results

    async def _call_api_batch(self, texts: list[str]) -> list[str]:
        combined = BATCH_SEPARATOR.join(texts)
        prompt = (
            f"Translate each paragraph to {self.target_lang}. "
            f"Paragraphs are separated by '---'. "
            f"Output translations in the same order, separated by '---'. "
            f"Keep exactly {len(texts)} translated paragraphs. "
            f"Only output translations, no explanations."
        )
        result = await self._call_api(combined, system_prompt=prompt)
        parts = [p.strip() for p in result.split("---")]
        if len(parts) < len(texts):
            parts.extend([""] * (len(texts) - len(parts)))
        return parts[: len(texts)]

    async def _call_api(self, text: str, system_prompt: Optional[str] = None) -> str:
        p = self.provider
        if not p:
            raise RuntimeError("No translation provider configured")

        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if p.api_key:
            headers["Authorization"] = f"Bearer {p.api_key}"

        if system_prompt is None:
            system_prompt = (
                f"You are a professional translator. "
                f"Translate the following text to {self.target_lang}. "
                f"Preserve the original meaning, tone, and style. "
                f"Only output the translation, nothing else."
            )

        url = f"{p.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": p.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }

        try:
            resp = await self._client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            log.error(
                "Translation API error: %s %s",
                e.response.status_code,
                e.response.text[:200],
            )
            raise RuntimeError(
                f"Translation failed: HTTP {e.response.status_code}"
            ) from e
        except (KeyError, IndexError) as e:
            log.error("Unexpected API response format: %s", e)
            raise RuntimeError("Translation failed: unexpected response format") from e
        except httpx.RequestError as e:
            log.error(
                "Translation request error: %s %s -> %s",
                type(e).__name__,
                e.request.url,
                e,
            )
            raise RuntimeError(f"Translation failed: {type(e).__name__} ({url})") from e

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _make_hash(text: str, target_lang: str) -> str:
        raw = f"{text}:{target_lang}"
        return hashlib.sha256(raw.encode()).hexdigest()[:20]
