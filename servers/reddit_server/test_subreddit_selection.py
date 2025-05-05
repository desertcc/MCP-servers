#!/usr/bin/env python3
"""
Test script for subreddit selection logic.

This script tests the subreddit selection and rotation logic without running the full bot.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_script")

# Load environment variables
load_dotenv()

# Import our functions
from supabase_loader import load_bot_config, get_excluded_subreddits, get_recent_subreddits
from bot_runner import select_subreddits

def main():
    """Test the subreddit selection logic."""
    # Check command line arguments
    if len(sys.argv) < 2:
        logger.error("Usage: python test_subreddit_selection.py <bot_id>")
        sys.exit(1)
    
    bot_id = sys.argv[1]
    max_subreddits = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    logger.info(f"Testing subreddit selection for bot_id: {bot_id} with max_subreddits: {max_subreddits}")
    
    # Load bot configuration
    logger.info(f"Loading configuration for bot: {bot_id}")
    bot_config = load_bot_config(bot_id)
    if not bot_config:
        logger.error(f"Failed to load configuration for bot: {bot_id}")
        sys.exit(1)
    
    # Print bot configuration
    logger.info(f"Bot configuration:")
    logger.info(f"  Fixed subreddits: {', '.join(bot_config.get('fixed_subs', [])) if bot_config.get('fixed_subs') else 'None'}")
    logger.info(f"  Keywords: {', '.join(bot_config.get('keywords', [])) if bot_config.get('keywords') else 'None'}")
    
    # Get excluded subreddits
    logger.info("Getting globally excluded subreddits...")
    excluded_subs = get_excluded_subreddits()
    logger.info(f"Globally excluded subreddits: {', '.join(excluded_subs) if excluded_subs else 'None'} (Total: {len(excluded_subs)})")
    
    # Get recently used subreddits
    logger.info("Getting recently used subreddits...")
    recent_subs = get_recent_subreddits(bot_id, days=3)
    logger.info(f"Recently used subreddits (last 3 days): {', '.join(recent_subs) if recent_subs else 'None'} (Total: {len(recent_subs)})")
    
    # Select subreddits
    logger.info("Selecting subreddits...")
    selected_subs = select_subreddits(bot_config, max_subreddits, bot_id)
    logger.info(f"Final selected subreddits: {', '.join(selected_subs) if selected_subs else 'None'} (Total: {len(selected_subs)})")
    
    logger.info("Test completed successfully")

if __name__ == "__main__":
    main()
