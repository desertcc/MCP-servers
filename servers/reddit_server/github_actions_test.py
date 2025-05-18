#!/usr/bin/env python3
"""
Test script specifically for GitHub Actions to diagnose Groq API issues and test bot functionality
"""

import os
import sys
import json
import traceback
from dotenv import load_dotenv
import groq
import re

# Import our custom modules for testing
from groq_wrapper import GroqWrapper
from supabase_loader import load_bot_config
from bot_runner import RedditBot

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
    
    # Test the style_tag functionality
    try:
        print("\nTesting style_tag functionality:")
        
        # Try to load a bot config from Supabase - try multiple known bot IDs
        bot_ids = [os.environ.get("TEST_BOT_ID", "logistics1"), "logistics2", "slime", "slime2"]
        bot_config = None
        
        for bot_id in bot_ids:
            try:
                print(f"Attempting to load bot config for {bot_id}...")
                bot_config = load_bot_config(bot_id)
                print(f"✓ Successfully loaded bot config for {bot_id}")
                print(f"Bot type: {bot_config.get('bot_type', 'unknown')}")
                print(f"Style tag: {bot_config.get('style_tag', 'none')}")
                
                # Create a RedditBot instance
                bot = RedditBot(dry_run=True, read_only=True, config=bot_config)
                assert hasattr(bot, 'style_tag'), "Bot instance missing style_tag attribute"
                print(f"✓ Bot instance has style_tag attribute: {bot.style_tag}")
                break  # Stop trying more IDs if one succeeds
                
            except Exception as e:
                print(f"✗ Could not load bot config for {bot_id}: {str(e)[:100]}...")
        
        # If no bot configs could be loaded, use a mock config
        if not bot_config:
            print("Using mock config for testing since no bot configs could be loaded...")
            # Create a mock config with style_tag
            bot_config = {
                'id': 'test_bot',
                'style_tag': 'grumpy-vet',
                'bot_type': 'logistics',
                'groq_prompt': 'You are a helpful Reddit commenter. Keep replies brief.'
            }
        
        # Test the GroqWrapper with style_tag and a realistic Reddit post
        wrapper = GroqWrapper()
        print("\nTesting GroqWrapper with style_tag and realistic Reddit post...")
        print(f"Using bot_id: {bot_config.get('id')}")
        print(f"Using style_tag: {bot_config.get('style_tag')}")
        
        # Print the custom prompt if available
        custom_prompt = bot_config.get('groq_prompt')
        if custom_prompt:
            print(f"Using custom prompt from Supabase: {custom_prompt[:100]}...")
        
        # Create a realistic Reddit post example
        test_post_title = "Just got my first truck! Any maintenance tips?"
        test_post_content = """I just bought my first semi truck, a 2018 Freightliner Cascadia. 
        I'm new to owning my own rig and would appreciate any maintenance tips from experienced drivers. 
        What should I be checking regularly? Any common issues with this model I should watch out for?"""
        
        # Format the prompt like the bot_runner.py does
        test_prompt = f"""Post Title: {test_post_title}\n\nPost Content: {test_post_content}"""
        
        # Test with the custom prompt from Supabase if available
        if custom_prompt:
            messages = [
                {"role": "system", "content": custom_prompt},
                {"role": "user", "content": test_prompt}
            ]
            response = wrapper.generate_completion(messages, style_tag=bot_config.get('style_tag'))
        else:
            # Fall back to default prompt
            response = wrapper.generate_completion(test_prompt, style_tag=bot_config.get('style_tag'))
        
        # Check that response is not too long (≤ 15 words)
        word_count = len(response.split())
        print(f"\nResponse to truck maintenance post (using '{bot_config.get('style_tag')}' style):")
        print(f"\"{response}\"")
        print(f"Word count: {word_count}")
        assert word_count <= 15, f"Response too long: {word_count} words (max 15)"
        print(f"✓ Response length check passed: {word_count} words (max 15)")
        
        # Test with another realistic post for a different topic
        test_post_title2 = "Made slime with my kids today!"
        test_post_content2 = """We had so much fun making slime today! Used glue, borax, and food coloring. 
        The kids loved mixing in glitter and beads. It was messy but totally worth it for the smiles on their faces."""
        
        test_prompt2 = f"""Post Title: {test_post_title2}\n\nPost Content: {test_post_content2}"""
        
        # For the slime post, we should use a slime-appropriate style tag like 'proud-parent'
        # Try to load a slime bot config if we're not already using one
        slime_style_tag = None
        if 'slime' not in bot_config.get('id', '').lower():
            try:
                print("\nLoading a slime bot config for the slime post...")
                slime_bot_config = load_bot_config('slime')
                slime_style_tag = slime_bot_config.get('style_tag')
                slime_prompt = slime_bot_config.get('groq_prompt')
                print(f"Using slime bot style_tag: {slime_style_tag}")
                
                # Test with the slime bot's custom prompt
                messages2 = [
                    {"role": "system", "content": slime_prompt},
                    {"role": "user", "content": test_prompt2}
                ]
                response2 = wrapper.generate_completion(messages2, style_tag=slime_style_tag)
            except Exception as e:
                print(f"Could not load slime bot config: {str(e)[:100]}...")
                # Fall back to a hardcoded slime-appropriate style tag
                slime_style_tag = "proud-parent"
                print(f"Using hardcoded slime style_tag: {slime_style_tag}")
                response2 = wrapper.generate_completion(test_prompt2, style_tag=slime_style_tag)
        else:
            # We're already using a slime bot, so use its style tag
            print("\nAlready using a slime bot config for the slime post")
            response2 = wrapper.generate_completion(test_prompt2, style_tag=bot_config.get('style_tag'))
        
        word_count2 = len(response2.split())
        style_tag_used = slime_style_tag if slime_style_tag else bot_config.get('style_tag')
        print(f"\nResponse to slime post (using '{style_tag_used}' style):")
        print(f"\"{response2}\"")
        print(f"Word count: {word_count2}")
        assert word_count2 <= 15, f"Response too long: {word_count2} words (max 15)"
        print(f"✓ Second response length check passed: {word_count2} words (max 15)")
        
        print("✓ style_tag functionality tests passed")
    except Exception as e:
        print(f"✗ Error testing style_tag functionality: {e}")
        print(traceback.format_exc())
    
    print("\nAll tests completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
