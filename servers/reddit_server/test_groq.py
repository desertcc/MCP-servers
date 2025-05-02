#!/usr/bin/env python3
"""
Test script for Groq API to diagnose initialization issues
"""

import os
import sys
from dotenv import load_dotenv
import groq

# Load environment variables
load_dotenv()

# Print environment variables related to proxies
print("Environment variables related to proxies:")
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        print(f"{var}: {os.environ[var]}")

# Print Groq version
print(f"Groq version: {groq.__version__}")

# Unset proxy environment variables that might interfere with Groq
for var in proxy_vars:
    if var in os.environ:
        print(f"Unsetting proxy variable: {var}")
        del os.environ[var]

# Try to initialize Groq client with just the API key
try:
    client = groq.Groq(
        api_key=os.environ.get("GROQ_API_KEY")
    )
    print("Successfully initialized Groq client with just the API key")
    
    # Try to make a simple completion
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10  # Correct parameter name for installed version
    )
    print(f"Response: {completion.choices[0].message.content}")
    print("Test completed")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
