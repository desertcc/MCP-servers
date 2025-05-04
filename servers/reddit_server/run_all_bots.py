#!/usr/bin/env python3
"""
Run all active Reddit bots in sequence.
This script fetches all active bots from Supabase and runs them one by one.
"""

import os
import sys
import logging
import argparse
import subprocess
from typing import List, Dict, Any
from dotenv import load_dotenv

# Import Supabase loader
from supabase_loader import load_bot_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_all_active_bots() -> List[str]:
    """
    Get a list of all active bot IDs from Supabase.
    
    Returns:
        List of bot IDs
    """
    try:
        # Import supabase-py
        import supabase
        from supabase import create_client
        
        # Get Supabase credentials from environment
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
            )
        
        # Initialize Supabase client
        logger.info("Connecting to Supabase to fetch all active bots")
        client = create_client(supabase_url, supabase_key)
        
        # Query the reddit_bots table for all active bots
        response = client.table("reddit_bots").select("id").eq("active", True).execute()
        
        # Check if we got a valid response with data
        if not response.data:
            logger.warning("No active bots found in Supabase")
            return []
        
        # Extract bot IDs
        bot_ids = [bot["id"] for bot in response.data]
        logger.info(f"Found {len(bot_ids)} active bots: {', '.join(bot_ids)}")
        
        return bot_ids
        
    except ImportError:
        logger.error("supabase-py package not installed. Install with: pip install supabase")
        raise RuntimeError("Missing required dependency: supabase-py")
    except Exception as e:
        logger.error(f"Error fetching active bots from Supabase: {e}")
        raise

def run_bot(bot_id: str, dry_run: bool = False, max_subreddits: int = None, 
            max_replies: int = None, max_upvotes: int = None) -> int:
    """
    Run a single bot with the given ID.
    
    Args:
        bot_id: The ID of the bot to run
        dry_run: Whether to run in dry-run mode
        max_subreddits: Maximum number of subreddits to process
        max_replies: Maximum number of replies to post
        max_upvotes: Maximum number of upvotes to perform
        
    Returns:
        Exit code from the bot process
    """
    logger.info(f"Running bot: {bot_id}")
    
    # Build command
    cmd = ["python", "servers/reddit_server/bot_runner.py", "--bot-id", bot_id]
    
    if dry_run:
        cmd.append("--dry-run")
    
    if max_subreddits is not None:
        cmd.extend(["--max-subreddits", str(max_subreddits)])
    
    if max_replies is not None:
        cmd.extend(["--max-replies", str(max_replies)])
    
    if max_upvotes is not None:
        cmd.extend(["--max-upvotes", str(max_upvotes)])
    
    # Run the bot
    logger.info(f"Executing command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    logger.info(f"Bot {bot_id} completed with exit code: {result.returncode}")
    return result.returncode

def main():
    """Main entry point for running all bots."""
    parser = argparse.ArgumentParser(description="Run all active Reddit bots")
    parser.add_argument("--dry-run", action="store_true", help="Run all bots in dry-run mode")
    parser.add_argument("--max-subreddits", type=int, help="Override maximum subreddits for all bots")
    parser.add_argument("--max-replies", type=int, help="Override maximum replies for all bots")
    parser.add_argument("--max-upvotes", type=int, help="Override maximum upvotes for all bots")
    args = parser.parse_args()
    
    try:
        # Get all active bots
        bot_ids = get_all_active_bots()
        
        if not bot_ids:
            logger.error("No active bots found. Exiting.")
            return 1
        
        # Run each bot
        success_count = 0
        failure_count = 0
        
        for bot_id in bot_ids:
            try:
                exit_code = run_bot(
                    bot_id=bot_id,
                    dry_run=args.dry_run,
                    max_subreddits=args.max_subreddits,
                    max_replies=args.max_replies,
                    max_upvotes=args.max_upvotes
                )
                
                if exit_code == 0:
                    success_count += 1
                else:
                    failure_count += 1
                    
            except Exception as e:
                logger.error(f"Error running bot {bot_id}: {e}")
                failure_count += 1
        
        logger.info(f"All bots completed. Success: {success_count}, Failures: {failure_count}")
        
        # Return non-zero exit code if any bot failed
        return 1 if failure_count > 0 else 0
        
    except Exception as e:
        logger.error(f"Error running bots: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
