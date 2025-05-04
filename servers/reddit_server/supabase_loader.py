#!/usr/bin/env python3
"""
Supabase loader for Reddit bot configurations.

Loads bot configurations from Supabase for the multi-account Reddit bot system.
"""

import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def load_bot_config(bot_id: str) -> Dict[str, Any]:
    """
    Load bot configuration from Supabase based on bot_id.
    
    Args:
        bot_id: The ID of the bot to load configuration for
        
    Returns:
        Dictionary containing bot configuration
        
    Raises:
        ValueError: If bot_id is not found or inactive
        RuntimeError: If Supabase connection fails
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
        logger.info(f"Connecting to Supabase to fetch config for bot_id: {bot_id}")
        client = create_client(supabase_url, supabase_key)
        
        # Query the reddit_bots table for the specified bot_id
        response = client.table("reddit_bots").select("*").eq("id", bot_id).eq("active", True).execute()
        
        # Check if we got a valid response with data
        if not response.data:
            # Check if the bot exists but is inactive
            inactive_check = client.table("reddit_bots").select("id").eq("id", bot_id).execute()
            if inactive_check.data:
                raise ValueError(f"Bot with ID '{bot_id}' exists but is inactive (active=false)")
            else:
                raise ValueError(f"Bot with ID '{bot_id}' not found in Supabase")
        
        # Get the first (and should be only) result
        bot_config = response.data[0]
        logger.info(f"Successfully loaded configuration for bot: {bot_id}")
        
        # Convert PostgreSQL arrays to Python lists if they're strings
        for array_field in ['keywords', 'fixed_subs']:
            if array_field in bot_config and isinstance(bot_config[array_field], str):
                # Handle the case where the array might be represented as a string
                if bot_config[array_field].startswith('{') and bot_config[array_field].endswith('}'):
                    # PostgreSQL array format: {item1,item2,item3}
                    items = bot_config[array_field][1:-1].split(',')
                    bot_config[array_field] = [item.strip() for item in items]
        
        return bot_config
        
    except ImportError:
        logger.error("supabase-py package not installed. Install with: pip install supabase")
        raise RuntimeError("Missing required dependency: supabase-py")
    except Exception as e:
        logger.error(f"Error loading bot configuration from Supabase: {e}")
        raise

def setup_environment_from_config(config: Dict[str, Any]) -> None:
    """
    Set environment variables from bot configuration.
    
    Args:
        config: Bot configuration dictionary from Supabase
    """
    # Map Supabase fields to environment variable names
    env_mapping = {
        "reddit_client_id": "REDDIT_CLIENT_ID",
        "reddit_secret": "REDDIT_CLIENT_SECRET",
        "reddit_refresh": "REDDIT_REFRESH_TOKEN",
        "user_agent": "REDDIT_USER_AGENT"
    }
    
    # Set environment variables
    for config_key, env_var in env_mapping.items():
        if config_key in config and config[config_key]:
            os.environ[env_var] = config[config_key]
            logger.info(f"Set environment variable: {env_var}")

# Test the loader if run directly
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python supabase_loader.py <bot_id>")
        sys.exit(1)
    
    try:
        bot_id = sys.argv[1]
        config = load_bot_config(bot_id)
        print(f"Successfully loaded config for bot: {bot_id}")
        print(f"Bot has {len(config.get('keywords', []))} keywords and {len(config.get('fixed_subs', []))} fixed subreddits")
        
        # Don't print sensitive information
        safe_keys = ['id', 'keywords', 'fixed_subs', 'max_replies', 'max_upvotes', 'max_subs', 'active']
        safe_config = {k: config[k] for k in safe_keys if k in config}
        print(f"Config (safe fields only): {safe_config}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
