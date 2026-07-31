import os
import time
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("VARTA.LLMAdapter")


# ============================================================================
# Custom Exception Hierarchy for OpenAI Integration
# ============================================================================
class OpenAIAdapterError(Exception):
    """Base exception for OpenAI LLM Adapter errors."""
    pass


class OpenAIAuthError(OpenAIAdapterError):
    """Raised when API Key authentication fails (401 / Invalid Key)."""
    pass


class OpenAIRateLimitError(OpenAIAdapterError):
    """Raised when request rate limits are hit (429)."""
    pass


class OpenAIQuotaError(OpenAIAdapterError):
    """Raised when usage quota is exceeded (429 Quota Exceeded)."""
    pass


class OpenAIInvalidModelError(OpenAIAdapterError):
    """Raised when an invalid or inaccessible model name is provided (404/400)."""
    pass


class OpenAINetworkError(OpenAIAdapterError):
    """Raised when network connectivity or socket connection fails."""
    pass


# ============================================================================
# Abstract Base Class
# ============================================================================
class BaseLLMAdapter(ABC):
    """
    Model-Agnostic LLM Adapter Interface:
    Focuses SOLELY on model communication (Prompt Input -> Structured Text Response).
    Supports OpenAI, Gemini, Claude, Ollama, and Mock testing adapters.
    """

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generates response text from prompt input."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Returns active model identifier."""
        pass


# ============================================================================
# Mock LLM Adapter
# ============================================================================
class MockLLMAdapter(BaseLLMAdapter):
    """
    Lightweight Mock LLM Adapter for dry-run offline testing:
    Extracts citation tags [Doc N] and context snippets from the prompt string
    to generate grounded mock responses without API keys or network dependencies.
    """

    def __init__(self, model_name: str = "mock-rag-synthesizer-v1"):
        self.model_name = model_name

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        if "No relevant context blocks available" in prompt or "insufficient" in prompt.lower():
            text = "The provided context contains insufficient information to answer this query."
        else:
            cits = re.findall(r"\[Doc \d+\]", prompt)
            unique_cits = sorted(list(set(cits)))
            cit_str = " ".join(unique_cits) if unique_cits else "[Doc 1]"

            q_match = re.search(r"=== USER QUERY ===\n(.*?)\n\n", prompt, re.DOTALL)
            query_str = q_match.group(1).strip() if q_match else "query"

            text = f"प्राप्त जानकारी और दस्तावेजों के अनुसार, '{query_str}' के संबंध में विस्तृत रिपोर्ट एवं राहत कार्य उपलब्ध हैं {cit_str}।"

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(text) // 4)

        return {
            "text": text,
            "provider": "MockLLMAdapter",
            "model_name": self.model_name,
            "generation_time_ms": elapsed_ms,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_tokens_estimated": prompt_tokens
        }

    def get_model_name(self) -> str:
        return self.model_name


# ============================================================================
# OpenAI LLM Adapter (Official OpenAI SDK - Responses API)
# ============================================================================
class OpenAILLMAdapter(BaseLLMAdapter):
    """
    Official OpenAI API LLM Adapter implementation using the OpenAI SDK (Responses API).
    Reads OPENAI_API_KEY and OPENAI_MODEL dynamically from .env / environment.
    """

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("OPENAI_MODEL")

    def _extract_response_text(self, response: Any) -> str:
        """Extracts text content cleanly from OpenAI Responses API object."""
        if hasattr(response, "output_text") and response.output_text:
            return str(response.output_text).strip()
        
        if hasattr(response, "output") and response.output:
            text_parts = []
            for item in response.output:
                if getattr(item, "type", None) == "message" and hasattr(item, "content"):
                    for content_item in item.content:
                        if getattr(content_item, "type", None) == "text" and hasattr(content_item, "text"):
                            text_parts.append(content_item.text)
                elif hasattr(item, "text"):
                    text_parts.append(getattr(item, "text"))
            if text_parts:
                return "\n".join(text_parts).strip()

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                return str(choice.message.content or "").strip()

        return str(response)

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        
        # 1. API Key & Model Validation
        key = (self.api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        if not key:
            raise OpenAIAdapterError(
                "OPENAI_API_KEY is missing or empty. Please set OPENAI_API_KEY in environment or .env file."
            )

        model = (self.model_name or os.getenv("OPENAI_MODEL") or "").strip()
        if not model:
            raise OpenAIInvalidModelError(
                "OPENAI_MODEL is missing or empty. Please set OPENAI_MODEL in environment or .env file."
            )

        # 2. SDK Import Verification
        try:
            from openai import (
                OpenAI,
                AuthenticationError,
                RateLimitError,
                NotFoundError,
                BadRequestError,
                APIConnectionError,
                APIError
            )
        except ImportError:
            raise OpenAIAdapterError(
                "The 'openai' Python SDK is not installed. Please run: pip install openai>=1.50.0"
            )

        # 3. Model Communication via OpenAI Responses API
        try:
            client = OpenAI(api_key=key)

            # Use OpenAI Responses API (client.responses.create)
            if hasattr(client, "responses"):
                res = client.responses.create(
                    model=model,
                    input=prompt
                )
            else:
                # Fallback for older SDK versions
                res = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )

            text = self._extract_response_text(res)

            # Extract Token Usage Metrics
            usage = getattr(res, "usage", None)
            input_tokens = getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0)) if usage else 0
            output_tokens = getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0)) if usage else 0
            total_tokens = getattr(usage, "total_tokens", input_tokens + output_tokens) if usage else (input_tokens + output_tokens)

            if input_tokens == 0:
                input_tokens = max(1, len(prompt) // 4)
            if output_tokens == 0:
                output_tokens = max(1, len(text) // 4)
            if total_tokens == 0:
                total_tokens = input_tokens + output_tokens

            elapsed_ms = round((time.time() - start_time) * 1000, 2)

            # Log Provider, Model, Tokens, Latency
            logger.info(
                f"[OpenAILLMAdapter] Provider=openai | Model={model} | "
                f"Input Tokens={input_tokens} | Output Tokens={output_tokens} | "
                f"Total Tokens={total_tokens} | Latency={elapsed_ms}ms"
            )

            return {
                "text": text,
                "provider": "OpenAILLMAdapter",
                "model_name": model,
                "generation_time_ms": elapsed_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "prompt_tokens_estimated": input_tokens
            }

        except AuthenticationError as e:
            raise OpenAIAuthError(f"Authentication failed: Invalid OPENAI_API_KEY. Details: {e}") from e
        except RateLimitError as e:
            err_str = str(e).lower()
            if "quota" in err_str or "insufficient_quota" in err_str:
                raise OpenAIQuotaError(f"OpenAI quota exceeded. Check account billing. Details: {e}") from e
            raise OpenAIRateLimitError(f"OpenAI rate limit reached. Details: {e}") from e
        except (NotFoundError, BadRequestError) as e:
            raise OpenAIInvalidModelError(f"Invalid or inaccessible OpenAI model '{model}'. Details: {e}") from e
        except APIConnectionError as e:
            raise OpenAINetworkError(f"Network error connecting to OpenAI API endpoints. Details: {e}") from e
        except APIError as e:
            raise OpenAIAdapterError(f"OpenAI API Error: {e}") from e
        except Exception as e:
            if isinstance(e, OpenAIAdapterError):
                raise e
            raise OpenAIAdapterError(f"Unexpected OpenAI Adapter Error: {e}") from e

    def get_model_name(self) -> str:
        return self.model_name or os.getenv("OPENAI_MODEL", "")


# ============================================================================
# Gemini LLM Adapter (Google Gemini API Adapter - Preserved for Multi-Provider)
# ============================================================================
class GeminiLLMAdapter(BaseLLMAdapter):
    """Google Gemini API Adapter implementation using google-genai SDK."""

    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            from google import genai
            api_key = self.api_key or os.getenv("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key) if api_key else genai.Client()
            res = client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            text = res.text if hasattr(res, "text") and res.text else str(res)
        except Exception as e:
            text = f"[Gemini Error]: {e}. Unable to contact Gemini API."

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(text) // 4)

        return {
            "text": text,
            "provider": "GeminiLLMAdapter",
            "model_name": self.model_name,
            "generation_time_ms": elapsed_ms,
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "prompt_tokens_estimated": prompt_tokens
        }

    def get_model_name(self) -> str:
        return self.model_name or os.getenv("GEMINI_MODEL", "")


# ============================================================================
# Dynamic LLM Adapter Factory (.env as Single Source of Truth)
# ============================================================================
def get_llm_adapter(config: Optional[Dict[str, Any]] = None) -> BaseLLMAdapter:
    """
    Factory function to instantiate the configured LLM Adapter.
    Prioritizes .env as the single source of truth for LLM_PROVIDER and model settings.
    """
    cfg = config or {}
    llm_cfg = cfg.get("llm", {})

    provider = (os.getenv("LLM_PROVIDER") or llm_cfg.get("provider") or "openai").strip().lower()

    if provider == "openai":
        model_name = os.getenv("OPENAI_MODEL") or llm_cfg.get("model_name")
        api_key = os.getenv("OPENAI_API_KEY") or llm_cfg.get("api_key")
        return OpenAILLMAdapter(model_name=model_name, api_key=api_key)

    elif provider == "gemini":
        model_name = os.getenv("GEMINI_MODEL") or llm_cfg.get("model_name")
        api_key = os.getenv("GEMINI_API_KEY") or llm_cfg.get("api_key")
        return GeminiLLMAdapter(model_name=model_name, api_key=api_key)

    else:
        model_name = llm_cfg.get("model_name", "mock-rag-synthesizer-v1")
        return MockLLMAdapter(model_name=model_name)
