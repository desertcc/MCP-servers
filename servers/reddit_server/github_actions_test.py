#!/usr/bin/env python3
"""
Test script specifically for GitHub Actions to diagnose Groq API issues
"""

import os
import sys
import json
import traceback
from dotenv import load_dotenv
import groq

# Load environment variables
load_dotenv()

def main():
    print("=== GitHub Actions Groq Test ===")
    print(f"Python version: {sys.version}")
    print(f"Groq version: {groq.__version__}")
    
    # Print all environment variables (excluding secrets)
    print("\nEnvironment variables:")
    for var in sorted(os.environ):
        if "key" not in var.lower() and "token" not in var.lower() and "secret" not in var.lower():
            print(f"{var}: {os.environ[var]}")
    
    # Check for proxy environment variables
    print("\nProxy environment variables:")
    proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy', 'NO_PROXY']
    found_proxy = False
    for var in proxy_vars:
        if var in os.environ:
            found_proxy = True
            print(f"{var}: {os.environ[var]}")
            # Unset the proxy variable
            print(f"Unsetting {var}")
            del os.environ[var]
    
    if not found_proxy:
        print("No proxy environment variables found")
    
    # Check if GROQ_API_KEY is set
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is not set")
        return 1
    
    # Try different initialization methods
    print("\nTesting Groq client initialization:")
    
    # Method 1: Standard initialization
    try:
        print("\nMethod 1: Standard initialization")
        client = groq.Groq(api_key=api_key)
        print("✓ Initialization successful")
        
        # Test a simple completion
        print("Testing completion...")
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"✓ Completion successful: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"✗ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
    
    # Method 2: Try with explicit empty parameters
    try:
        print("\nMethod 2: With empty parameters")
        client = groq.Groq(
            api_key=api_key,
            base_url=None,
            timeout=None,
        )
        print("✓ Initialization successful")
        
        # Test a simple completion
        print("Testing completion...")
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"✓ Completion successful: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"✗ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
    
    # Method 3: Try with a different model
    try:
        print("\nMethod 3: With a different model")
        client = groq.Groq(api_key=api_key)
        print("✓ Initialization successful")
        
        # Test a simple completion with a different model
        print("Testing completion with different model...")
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"✓ Completion successful: {completion.choices[0].message.content}")
    except Exception as e:
        print(f"✗ Error: {e}")
        print(f"Traceback: {traceback.format_exc()}")
    
    print("\nTest completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
