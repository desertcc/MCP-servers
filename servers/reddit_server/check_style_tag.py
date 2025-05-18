#!/usr/bin/env python3
"""
Simple script to check if style_tag is properly loaded from Supabase
"""

import sys
import json
import logging
from supabase_loader import load_bot_config

# Configure logging to file instead of console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='style_tag_check.log',
    filemode='w'
)

def main():
    if len(sys.argv) != 2:
        print("Usage: python check_style_tag.py <bot_id>")
        return 1
    
    bot_id = sys.argv[1]
    print(f"\n===== CHECKING STYLE_TAG FOR BOT: {bot_id} =====")
    
    try:
        # Load the bot configuration from Supabase
        config = load_bot_config(bot_id)
        print(f"\n✓ Successfully loaded config from Supabase for bot: {bot_id}")
        
        # Extract and display key fields
        print("\nKEY FIELDS:")
        print("-" * 40)
        
        # Check if style_tag is present
        style_tag = config.get('style_tag')
        if style_tag:
            print(f"STYLE_TAG: '{style_tag}'")
        else:
            print("STYLE_TAG: Not found in configuration")
        
        # Check other relevant fields
        bot_type = config.get('bot_type', 'unknown')
        print(f"BOT_TYPE: {bot_type}")
        print(f"BOT_ID: {config.get('id')}")
        
        # Print safe fields in a formatted way
        print("\nALL SAFE FIELDS:")
        print("-" * 40)
        safe_keys = ['id', 'style_tag', 'bot_type', 'max_replies', 'max_upvotes', 'max_subs', 'active']
        for key in safe_keys:
            if key in config:
                print(f"{key}: {config[key]}")
        
        print("\n===== CHECK COMPLETE =====\n")
        return 0
    except Exception as e:
        print(f"\nERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
