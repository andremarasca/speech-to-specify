"""Simple OpenAI connection test - run directly to verify API key."""

import os
import sys

import pytest


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping real API test",
)
def test_openai_api_connection():
    """Test direct connection to OpenAI API.
    
    This test is skipped by default unless OPENAI_API_KEY is set.
    Run with: pytest tests/test_openai_connection.py -v
    """
    import httpx
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    assert api_key, "OPENAI_API_KEY must be set"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say 'Hello' and nothing else."}],
        "max_tokens": 10,
    }

    url = "https://api.openai.com/v1/chat/completions"

    with httpx.Client(timeout=30) as client:
        response = client.post(url, headers=headers, json=payload)

    assert response.status_code == 200, f"API returned {response.status_code}: {response.text}"
    
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "message" in data["choices"][0]
    
    content = data["choices"][0]["message"]["content"]
    assert content, "Response content should not be empty"
    print(f"✅ OpenAI API connection successful! Response: {content}")


def _manual_connection_test():
    """Manual test function for direct connection to OpenAI API (not a pytest test)."""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return False

    print(f"🔑 API Key found: {api_key[:8]}...{api_key[-4:]}")
    print(f"   Key length: {len(api_key)} chars")

    # Test with a minimal request
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",  # Cheaper model for testing
        "messages": [{"role": "user", "content": "Say 'Hello' and nothing else."}],
        "max_tokens": 10,
    }

    url = "https://api.openai.com/v1/chat/completions"

    print(f"\n📡 Testing connection to: {url}")
    print(f"   Model: {payload['model']}")

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(url, headers=headers, json=payload)

            print(f"\n📥 Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                print(f"✅ SUCCESS! Response: {content}")
                return True
            else:
                print(f"❌ FAILED!")
                print(f"   Response: {response.text}")

                # Parse error details
                try:
                    error_data = response.json()
                    error = error_data.get("error", {})
                    print(f"   Error type: {error.get('type')}")
                    print(f"   Error message: {error.get('message')}")
                    print(f"   Error code: {error.get('code')}")
                except Exception:
                    pass

                return False

    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        return False


def _check_env_loading():
    """Check if .env file is being loaded correctly (not a pytest test)."""
    from pathlib import Path

    env_file = Path(__file__).parent.parent / ".env"
    print(f"\n📁 Checking .env file: {env_file}")
    print(f"   Exists: {env_file.exists()}")

    if env_file.exists():
        content = env_file.read_text()
        lines = [l for l in content.splitlines() if l.strip() and not l.startswith("#")]
        print(f"   Non-empty lines: {len(lines)}")

        for line in lines:
            if "=" in line:
                key = line.split("=")[0].strip()
                value = line.split("=", 1)[1].strip()
                # Mask the value
                if len(value) > 8:
                    masked = f"{value[:4]}...{value[-4:]}"
                else:
                    masked = "***"
                print(f"   {key}={masked}")


if __name__ == "__main__":
    print("=" * 60)
    print("OpenAI Connection Test")
    print("=" * 60)

    # First check raw environment
    print("\n🔍 Checking environment variables...")
    _check_env_loading()

    # Try loading dotenv
    try:
        from dotenv import load_dotenv

        load_dotenv()
        print("\n✅ dotenv loaded")
    except ImportError:
        print("\n⚠️  python-dotenv not installed, using raw env vars")

    # Now test the connection
    success = _manual_connection_test()

    print("\n" + "=" * 60)
    sys.exit(0 if success else 1)
