#!/usr/bin/env python3
"""
VARTA - OpenAI API Connectivity Test Script (OpenAI SDK - Responses API).

Validates end-to-end connectivity to the OpenAI API using:
- API key configured in .env file (OPENAI_API_KEY)
- Model configured in .env file (OPENAI_MODEL) or CLI argument (--model)
- Official OpenAI SDK Responses API (client.responses.create)

Verifies:
1. API Key Loading & Environment Configuration
2. Model Accessibility
3. Successful API Response
4. Token Usage Reporting (Input, Output, Total Tokens)
5. Latency Measurement (ms)
6. Error Handling & Diagnosis
"""

import os
import sys
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.llm_adapter import (
    OpenAILLMAdapter,
    OpenAIAdapterError,
    OpenAIAuthError,
    OpenAIRateLimitError,
    OpenAIQuotaError,
    OpenAIInvalidModelError,
    OpenAINetworkError
)


def mask_key(key: str) -> str:
    """Masks API key for display security."""
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Test OpenAI API Connection using OpenAI SDK Responses API")
    parser.add_argument("--model", type=str, default=None, help="OpenAI model name to test (defaults to OPENAI_MODEL from .env)")
    parser.add_argument("--test-error-simulation", action="store_true", help="Simulate invalid API key error handling path")
    args = parser.parse_args()

    print("=" * 65)
    print(" VARTA - OPENAI API CONNECTION TEST (Responses API)")
    print("=" * 65)

    # 1. Load API key & model from .env file
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("OPENAI_API_KEY")
    env_model = os.getenv("OPENAI_MODEL")
    model_name = args.model or env_model

    # Check if API key is present
    if not api_key or not api_key.strip():
        print("\n[1/5 KEY STATUS] API Key Loaded: NO [FAIL]")
        print("[ERROR] OPENAI_API_KEY is missing or empty in environment / .env file.")
        print("-> Please ensure '.env' file exists in project root with:")
        print("   OPENAI_API_KEY=<your_openai_api_key>")
        print("   OPENAI_MODEL=<your_model_name>")
        print("   LLM_PROVIDER=openai")
        print("\n[RESULT] [FAIL] TEST FAILED: Missing API Key.")
        sys.exit(1)

    # Check if Model name is specified
    if not model_name or not model_name.strip():
        print("\n[2/5 MODEL STATUS] Model Specified: NO [FAIL]")
        print("[ERROR] OPENAI_MODEL is missing or empty in environment / .env file.")
        print("-> Please specify OPENAI_MODEL in .env or pass --model <model_name> CLI argument.")
        print("\n[RESULT] [FAIL] TEST FAILED: Missing Model Name.")
        sys.exit(1)

    clean_key = api_key.strip()
    clean_model = model_name.strip()
    print(f"\n[1/5 KEY STATUS] API Key Loaded: YES [OK] ({mask_key(clean_key)})")
    print(f"[2/5 MODEL NAME] Active Model: {clean_model}")

    # 2. Check for OpenAI SDK package
    try:
        import openai
        print(f"[SDK STATUS] OpenAI Python SDK Loaded: YES [OK] (v{openai.__version__})")
    except ImportError:
        print("\n[ERROR] 'openai' package is not installed.")
        print("-> Run: pip install openai python-dotenv")
        print("\n[RESULT] [FAIL] TEST FAILED: Missing Dependency.")
        sys.exit(1)

    # 3. Handle optional Error Handling Simulation Test
    if args.test_error_simulation:
        print("\n[3/5 ERROR HANDLER TEST] Simulating Invalid Key Verification...")
        invalid_adapter = OpenAILLMAdapter(model_name=clean_model, api_key="sk-invalid-test-key-12345")
        try:
            invalid_adapter.generate("Test prompt")
            print("  [WARN] Expected error did not raise for invalid key.")
        except OpenAIAuthError as e:
            print(f"  [OK] Successfully caught OpenAIAuthError: {e}")
        except Exception as e:
            print(f"  [OK] Caught exception: {type(e).__name__} -> {e}")

    # 4. Execute Connectivity & Generation Test
    prompt = "Reply with exactly: OPENAI CONNECTION SUCCESS"
    print(f"\n[4/5 PROMPT SENT]: \"{prompt}\"")

    try:
        adapter = OpenAILLMAdapter(model_name=clean_model, api_key=clean_key)
        start_t = time.time()
        res = adapter.generate(prompt)
        total_time_ms = round((time.time() - start_t) * 1000, 2)

        # 5. Extract and verify Token Usage & Latency
        response_text = res.get("text", "")
        input_tokens = res.get("input_tokens", 0)
        output_tokens = res.get("output_tokens", 0)
        total_tokens = res.get("total_tokens", 0)
        gen_time_ms = res.get("generation_time_ms", total_time_ms)

        print("\n" + "=" * 65)
        print(" [5/5 RESPONSE & LOGGING METRICS]")
        print("=" * 65)
        print(f"  Provider       : {res.get('provider')}")
        print(f"  Model          : {res.get('model_name')}")
        print(f"  Response Text  : {response_text}")
        print(f"  Input Tokens   : {input_tokens}")
        print(f"  Output Tokens  : {output_tokens}")
        print(f"  Total Tokens   : {total_tokens}")
        print(f"  Latency        : {gen_time_ms} ms")
        print("=" * 65)
        print("\n [RESULT] [SUCCESS] OPENAI CONNECTION SUCCESSFUL!")
        print("=" * 65)
        sys.exit(0)

    except OpenAIAuthError as e:
        print(f"\n[ERROR ENCOUNTERED]: (OpenAIAuthError) {e}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(" [FAIL] Invalid API Key (HTTP 401 / Authentication Error).")
        print(" -> Please check your OPENAI_API_KEY in the .env file.")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Authentication Error.")
        sys.exit(1)

    except OpenAIQuotaError as e:
        print(f"\n[ERROR ENCOUNTERED]: (OpenAIQuotaError) {e}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(" [FAIL] Account Quota Exceeded (HTTP 429 Insufficient Quota).")
        print(" -> Check your OpenAI account billing details and usage limits.")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Quota Exceeded.")
        sys.exit(1)

    except OpenAIRateLimitError as e:
        print(f"\n[ERROR ENCOUNTERED]: (OpenAIRateLimitError) {e}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(" [FAIL] Rate Limit Reached (HTTP 429 Rate Limit).")
        print(" -> Request frequency is too high. Wait a moment and retry.")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Rate Limited.")
        sys.exit(1)

    except OpenAIInvalidModelError as e:
        print(f"\n[ERROR ENCOUNTERED]: (OpenAIInvalidModelError) {e}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(" [FAIL] Invalid or Inaccessible Model (HTTP 404 / 400).")
        print(f" -> Model '{clean_model}' is not recognized or not enabled for this API key.")
        print(" -> Check OPENAI_MODEL in .env or try a model accessible by your key.")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Invalid Model.")
        sys.exit(1)

    except OpenAINetworkError as e:
        print(f"\n[ERROR ENCOUNTERED]: (OpenAINetworkError) {e}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(" [FAIL] Network Error / Connectivity Failed.")
        print(" -> Check network connection, DNS, proxy, or firewall configuration.")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Network Error.")
        sys.exit(1)

    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)
        print(f"\n[ERROR ENCOUNTERED]: ({err_type}) {err_msg}")
        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        print(f" [FAIL] Unhandled API Call Error: {err_type}")
        print("-" * 60)
        print("\n[RESULT] [FAIL] TEST FAILED: Connection or API Error.")
        sys.exit(1)


if __name__ == "__main__":
    main()
