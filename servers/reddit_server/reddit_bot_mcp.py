#!/usr/bin/env python3
"""
Reddit Bot MCP Integration Module

This module integrates the Reddit Automation Bot with the MCP server architecture.
It adds new tools to the MCP server for discovering subreddits, replying to posts,
and running automated engagement sessions.
"""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from mcp.types import TextContent
from bot_runner import RedditBot

# Set up logging
logger = logging.getLogger("reddit_bot_mcp")

# Initialize the bot (without running it yet)
bot = None

async def initialize_bot(dry_run: bool = False) -> RedditBot:
    """Initialize the Reddit bot if not already initialized."""
    global bot
    if bot is None:
        bot = RedditBot(dry_run=dry_run)
    return bot

async def discover_subreddits_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """MCP tool to discover relevant subreddits."""
    try:
        dry_run = arguments.get("dry_run", False)
        bot = await initialize_bot(dry_run)
        
        subreddits = bot.discover_subreddits()
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "subreddits": subreddits,
                "count": len(subreddits)
            }, indent=2)
        )]
    except Exception as e:
        logger.exception(f"Error in discover_subreddits_tool: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)
        )]

async def reply_to_subreddit_posts_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """MCP tool to reply to posts in a specific subreddit."""
    try:
        subreddit = arguments.get("subreddit")
        if not subreddit:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "status": "error",
                    "message": "Subreddit name is required"
                }, indent=2)
            )]
        
        dry_run = arguments.get("dry_run", False)
        bot = await initialize_bot(dry_run)
        
        # This will be executed synchronously since PRAW is not async
        bot.reply_to_posts(subreddit)
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "message": f"Processed posts in r/{subreddit}",
                "dry_run": dry_run
            }, indent=2)
        )]
    except Exception as e:
        logger.exception(f"Error in reply_to_subreddit_posts_tool: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)
        )]

async def run_reddit_bot(subreddit: str = None, limit: int = 5, dry_run: bool = False, read_only: bool = False, max_subreddits: int = 3, max_replies: int = 10, max_upvotes: int = 20) -> Dict[str, Any]:
    """Run the Reddit MCP Automation Bot.
    
    Args:
        subreddit: Optional specific subreddit to target
        limit: Maximum number of posts to process per subreddit
        dry_run: Run in dry-run mode (no actual posts or upvotes)
        read_only: Run in read-only mode (no authentication required)
        max_subreddits: Maximum number of subreddits to process in a single run
        max_replies: Maximum number of replies to post in a single run
        max_upvotes: Maximum number of upvotes to perform in a single run
        
    Returns:
        Dict with status and summary information
    """
    try:
        # Initialize the bot
        from bot_runner import RedditBot, MAX_POSTS_PER_SUBREDDIT
        
        # Override the global limit if specified
        if limit != 5:
            global MAX_POSTS_PER_SUBREDDIT
            MAX_POSTS_PER_SUBREDDIT = limit
        
        # Initialize the bot with activity limits
        bot = RedditBot(
            dry_run=dry_run, 
            read_only=read_only,
            max_subreddits=max_subreddits,
            max_replies=max_replies,
            max_upvotes=max_upvotes
        )
        
        # If a specific subreddit was provided, only process that one
        if subreddit:
            bot.reply_to_posts(subreddit)
        else:
            # Run the full bot workflow
            bot.run()
        
        # Get the interaction log for the summary
        interaction_log = get_interaction_log(10)  # Get the last 10 interactions
        
        return {
            "status": "success",
            "mode": "dry_run" if dry_run else "read_only" if read_only else "full",
            "target": f"r/{subreddit}" if subreddit else "multiple subreddits",
            "limit_per_subreddit": limit,
            "max_subreddits": max_subreddits,
            "max_replies": max_replies,
            "max_upvotes": max_upvotes,
            "recent_interactions": interaction_log
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def run_bot_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """MCP tool to run the complete bot workflow."""
    try:
        dry_run = arguments.get("dry_run", False)
        bot = await initialize_bot(dry_run)
        
        # Run the bot (this will discover subreddits and reply to posts)
        bot.run()
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "message": "Bot run completed successfully",
                "dry_run": dry_run,
                "timestamp": datetime.now().isoformat()
            }, indent=2)
        )]
    except Exception as e:
        logger.exception(f"Error in run_bot_tool: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)
        )]

async def get_interaction_log_tool(arguments: Dict[str, Any]) -> List[TextContent]:
    """MCP tool to retrieve the bot's interaction log."""
    try:
        limit = int(arguments.get("limit", 10))
        bot = await initialize_bot()
        
        # Get the most recent interactions up to the limit
        recent_interactions = bot.interaction_log[-limit:] if bot.interaction_log else []
        
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "success",
                "interactions": recent_interactions,
                "count": len(recent_interactions),
                "total_interactions": len(bot.interaction_log)
            }, indent=2)
        )]
    except Exception as e:
        logger.exception(f"Error in get_interaction_log_tool: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)
        )]

# List of new tools to be registered with the MCP server
BOT_TOOLS = [
    {
        "name": "discover_subreddits",
        "description": "Discover relevant subreddits based on keywords like slime, crafts, kids, parenting, home, and toys.",
        "parameters": {
            "dry_run": {
                "type": "boolean",
                "description": "If true, only simulate the discovery without making actual API calls.",
                "default": False
            }
        },
        "function": discover_subreddits_tool
    },
    {
        "name": "reply_to_subreddit_posts",
        "description": "Reply to posts in a specific subreddit with friendly, helpful comments.",
        "parameters": {
            "subreddit": {
                "type": "string",
                "description": "Name of the subreddit to process (without the 'r/' prefix)."
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, only simulate replies without posting actual comments.",
                "default": False
            }
        },
        "function": reply_to_subreddit_posts_tool
    },
    {
        "name": "run_reddit_bot",
        "description": "Run the Reddit MCP Automation Bot to discover subreddits, reply to posts, and upvote content",
        "parameters": {
            "type": "object",
            "properties": {
                "subreddit": {
                    "type": "string",
                    "description": "Optional specific subreddit to target (e.g., 'slime' or 'parenting')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of posts to process per subreddit (default: 5)"
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Run in dry-run mode with no actual posts or upvotes (default: false)"
                },
                "read_only": {
                    "type": "boolean",
                    "description": "Run in read-only mode with no authentication required (default: false)"
                },
                "max_subreddits": {
                    "type": "integer",
                    "description": "Maximum number of subreddits to process in a single run (default: 3)"
                },
                "max_replies": {
                    "type": "integer",
                    "description": "Maximum number of replies to post in a single run (default: 10)"
                },
                "max_upvotes": {
                    "type": "integer",
                    "description": "Maximum number of upvotes to perform in a single run (default: 20)"
                }
            },
            "required": []
        },
        "function": run_reddit_bot
    },
    {
        "name": "get_interaction_log",
        "description": "Retrieve the bot's interaction log.",
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent interactions to retrieve.",
                "default": 10
            }
        },
        "function": get_interaction_log_tool
    }
]

# Function to register the bot tools with the MCP server
def register_bot_tools(app):
    """Register the bot tools with the MCP server."""
    for tool in BOT_TOOLS:
        app.register_tool(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            function=tool["function"]
        )
    
    logger.info(f"Registered {len(BOT_TOOLS)} Reddit bot tools with MCP server")
