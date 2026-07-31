#!/usr/bin/env python3
"""
VARTA - Gemini API Connectivity Test Script (google-genai SDK).

Validates end-to-end connectivity to the Google Gemini API using
the API key configured in the project .env file and the official google-genai SDK.
Supports AQ. format keys issued by Google AI Studio.
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is in python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Test Google Gemini API Connection using google-genai SDK")
    parser.add_argument("--model", type=str, default="gemini-2.0-flash", help="Gemini model name to test")
    args = parser.parse_args()

    print("=" * 60)
    print(" VARTA - GEMINI API CONNECTION TEST (google-genai SDK)")
    print("=" * 60)

    # 1. Load API key from .env file
    env_path = project_root / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")

    # Check if API key is present
    if not api_key or not api_key.strip():
        print("\n[KEY STATUS] API Key Loaded: NO [FAIL]")
        print("[ERROR] GEMINI_API_KEY is missing or empty in environment / .env file.")
        print("-> Please ensure '.env' file exists in project root with GEMINI_API_KEY=<your_key>.")
        print("\n[RESULT] [FAIL] TEST FAILED: Missing API Key.")
        sys.exit(1)

    clean_key = api_key.strip()
    is_aq_key = clean_key.startswith("AQ.")
    key_type_str = "Google AI Studio AQ. key" if is_aq_key else "Standard Gemini key"

    print(f"\n[KEY STATUS] API Key Loaded: YES [OK] ({key_type_str}, masked for security)")
    model_name = args.model
    print(f"[MODEL NAME] Active Model: {model_name}")

    # 2. Check for google-genai package
    try:
        from google import genai
    except ImportError:
        print("\n[ERROR] 'google-genai' package is not installed.")
        print("-> Run: pip install google-genai python-dotenv")
        print("\n[RESULT] [FAIL] TEST FAILED: Missing Dependency.")
        sys.exit(1)

    # 3. Send prompt and handle response/errors
    prompt = "Reply with exactly: GEMINI CONNECTION SUCCESS"
    print(f"[PROMPT SENT]: \"{prompt}\"")

    try:
        client = genai.Client(api_key=clean_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )

        # Extract text response
        if hasattr(response, "text") and response.text:
            response_text = response.text.strip()
        else:
            response_text = str(response)

        print(f"[MODEL RESPONSE]: {response_text}")
        print("\n" + "=" * 60)
        print(" [RESULT] [SUCCESS] GEMINI CONNECTION SUCCESSFUL!")
        print("=" * 60)
        sys.exit(0)

    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)
        print(f"\n[ERROR ENCOUNTERED]: ({err_type}) {err_msg}")

        print("-" * 60)
        print(" DIAGNOSIS & REMEDIATION:")
        if "401" in err_msg or "API_KEY_INVALID" in err_msg or "Unauthenticated" in err_type or "invalid" in err_msg.lower():
            print(" [FAIL] Invalid API Key (HTTP 401 / Unauthenticated).")
            print(" -> Please check your GEMINI_API_KEY in the .env file.")
        elif "403" in err_msg or "PermissionDenied" in err_type or "Forbidden" in err_msg:
            print(" [FAIL] Permission Denied (HTTP 403 / Forbidden).")
            print(" -> Ensure the API key has permission to access the specified model.")
        elif "429" in err_msg or "ResourceExhausted" in err_type or "quota" in err_msg.lower():
            print(" [FAIL] Quota Exceeded / Rate Limited (HTTP 429).")
            print(" -> Usage quota exceeded or request rate limit reached. Retry later.")
        elif any(k in err_msg.lower() for k in ["connection", "network", "timeout", "socket", "getaddrinfo", "unreachable"]):
            print(" [FAIL] Network Error / Connectivity Failed.")
            print(" -> Check network connection, firewall, or proxy configuration.")
        else:
            print(f" [FAIL] Unhandled API Call Error: {err_type}")
        print("-" * 60)

        print("\n[RESULT] [FAIL] TEST FAILED: Connection or API Error.")
        sys.exit(1)


if __name__ == "__main__":
    main()
