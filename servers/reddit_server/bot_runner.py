#!/usr/bin/env python3
"""
Reddit MCP Automation Bot

A bot that discovers and interacts with subreddits based on configured keywords.
Uses Groq API to generate friendly, helpful replies and upvotes positive content.
Supports multiple Reddit accounts via Supabase configuration.
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple

import praw
# Import our custom GroqWrapper instead of direct Groq import
from groq_wrapper import GroqWrapper
from dotenv import load_dotenv
# Import Supabase loader for multi-account support
from supabase_loader import load_bot_config, setup_environment_from_config, get_recent_subreddits, update_subreddit_history, get_excluded_subreddits
# Import TextBlob for sentiment analysis
from textblob import TextBlob

# Set up logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f"reddit_bot_{datetime.now().strftime('%Y%m%d')}.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("reddit_bot")

# Load environment variables
load_dotenv()

# Unset proxy environment variables that might interfere with Groq
proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'no_proxy', 'NO_PROXY']
for var in proxy_vars:
    if var in os.environ:
        logger.info(f"Unsetting proxy environment variable: {var}")
        del os.environ[var]

# Constants
DEFAULT_KEYWORDS = ["slime", "crafts", "kids", "parenting", "home", "toys"]
MAX_POSTS_PER_SUBREDDIT = 5
MAX_COMMENTS_TO_UPVOTE = 3
SLEEP_BETWEEN_ACTIONS = 5  # seconds - increased to avoid rate limiting
SLEEP_BETWEEN_POSTS = 10  # seconds - longer delay between posting to avoid rate limiting

# Default activity limits (can be overridden by Supabase config)
DEFAULT_MAX_SUBREDDITS_PER_RUN = 3  # Maximum number of subreddits to process in a single run
DEFAULT_MAX_TOTAL_REPLIES_PER_RUN = 10  # Maximum number of replies to post in a single run
DEFAULT_MAX_TOTAL_UPVOTES_PER_RUN = 20  # Maximum number of upvotes to perform in a single run

def discover_subreddits_by_keywords(keywords: List[str], max_subreddits: int) -> List[str]:
    """
    Discover subreddits based on keywords using Reddit's search functionality.
    
    Args:
        keywords: List of keywords to search for
        max_subreddits: Maximum number of subreddits to return
        
    Returns:
        List of subreddit names
    """
    try:
        # Create a read-only Reddit instance for discovery
        reddit = praw.Reddit(
            client_id=os.environ.get("REDDIT_CLIENT_ID"),
            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
            user_agent=os.environ.get("REDDIT_USER_AGENT"),
            check_for_updates=False,
            read_only=True
        )
        
        # Shuffle keywords to get different results each time
        shuffled_keywords = list(keywords)
        random.shuffle(shuffled_keywords)
        
        # Limit to first 3 keywords to avoid too many API calls
        search_keywords = shuffled_keywords[:min(3, len(shuffled_keywords))]
        
        # Discover subreddits for each keyword
        discovered_subreddits = set()
        for keyword in search_keywords:
            logger.info(f"Discovering subreddits for keyword: {keyword}")
            try:
                # Search for subreddits related to the keyword
                subreddits = reddit.subreddits.search(keyword, limit=10)
                
                # Add discovered subreddits to the set
                for subreddit in subreddits:
                    discovered_subreddits.add(subreddit.display_name)
                    
                    # Break if we have enough subreddits
                    if len(discovered_subreddits) >= max_subreddits:
                        break
                        
                # Sleep to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error discovering subreddits for keyword {keyword}: {e}")
        
        # Convert set to list and limit to max_subreddits
        result = list(discovered_subreddits)[:max_subreddits]
        logger.info(f"Discovered {len(result)} subreddits: {', '.join(result)}")
        return result
        
    except Exception as e:
        logger.error(f"Error in discover_subreddits_by_keywords: {e}")
        return []


def select_subreddits(bot_config: Dict[str, Any], max_subreddits: int, bot_id: Optional[str] = None) -> List[str]:
    """Select subreddits to process based on bot configuration.
    
    Args:
        bot_config: Bot configuration from Supabase
        max_subreddits: Maximum number of subreddits to process
        bot_id: Bot ID for tracking subreddit history
        
    Returns:
        List of subreddit names to process
    """
    # Initialize empty list of subreddits
    all_subreddits = []
    
    # If fixed_subs is provided, use those
    if "fixed_subs" in bot_config and bot_config["fixed_subs"]:
        logger.info("Using fixed subreddit list from configuration")
        all_subreddits.extend(bot_config["fixed_subs"])
    
    # If keywords are provided and we don't have enough subreddits, discover more
    if ("keywords" in bot_config and bot_config["keywords"] and 
            (not all_subreddits or len(all_subreddits) < max_subreddits * 2)):
        logger.info("Discovering subreddits based on keywords")
        # Use keywords to discover subreddits
        discovered = discover_subreddits_by_keywords(bot_config["keywords"], max_subreddits * 2)
        # Add discovered subreddits to the list
        all_subreddits.extend(discovered)
    
    # Remove duplicates
    all_subreddits = list(set(all_subreddits))
    
    # Get globally excluded subreddits from Supabase
    excluded_subs = get_excluded_subreddits()
    logger.info(f"Globally excluded subreddits: {', '.join(excluded_subs) if excluded_subs else 'None'}"
              f" (Total: {len(excluded_subs)})")
    
    # Get recently used subreddits if bot_id is provided
    recent_subs = []
    if bot_id:
        recent_subs = get_recent_subreddits(bot_id, days=3)
        logger.info(f"Recently used subreddits (last 3 days): {', '.join(recent_subs) if recent_subs else 'None'}"
                  f" (Total: {len(recent_subs)})")
    
    # Filter out excluded and recently used subreddits
    filtered_subs = [sub for sub in all_subreddits 
                    if sub.lower() not in [s.lower() for s in excluded_subs] 
                    and sub.lower() not in [s.lower() for s in recent_subs]]
    
    logger.info(f"After filtering excluded and recent subreddits: {len(filtered_subs)} subreddits remain")
    
    # Shuffle the list to randomize selection
    random.shuffle(filtered_subs)
    logger.info(f"Shuffled subreddits for randomization")
    
    # Select a random sample of subreddits up to max_subreddits
    selected_subs = filtered_subs[:max_subreddits]
    logger.info(f"Selected {len(selected_subs)} subreddits from filtered list: {', '.join(selected_subs) if selected_subs else 'None'}")
    
    # If we don't have enough subreddits after filtering, include some recent ones
    # but prioritize ones that haven't been used recently
    if len(selected_subs) < max_subreddits and recent_subs:
        remaining_slots = max_subreddits - len(selected_subs)
        available_recent = [sub for sub in recent_subs 
                           if sub.lower() not in [s.lower() for s in excluded_subs]]
        
        # Add some recent subreddits if needed, but shuffle them first
        random.shuffle(available_recent)
        selected_subs.extend(available_recent[:remaining_slots])
    
    logger.info(f"Selected {len(selected_subs)} subreddits: {', '.join(selected_subs)}")
    return selected_subs

class RedditBot:
    """Reddit Automation Bot for positive engagement in family-friendly subreddits."""
    
    def __init__(self, dry_run: bool = False, read_only: bool = False, 
                 max_subreddits: int = DEFAULT_MAX_SUBREDDITS_PER_RUN, 
                 max_replies: int = DEFAULT_MAX_TOTAL_REPLIES_PER_RUN, 
                 max_upvotes: int = DEFAULT_MAX_TOTAL_UPVOTES_PER_RUN,
                 config: Dict[str, Any] = None):
        """Initialize the Reddit bot with API credentials.
        
        Args:
            dry_run: If True, don't make actual posts or upvotes
            read_only: If True, use Reddit's read-only mode (no authentication required)
        """
        self.dry_run = dry_run
        self.read_only = read_only or dry_run  # Always use read_only for dry_run
        self.config = config or {}
        
        # Set limits from config if available, otherwise use defaults
        self.max_subreddits = self.config.get('max_subs', max_subreddits)
        self.max_replies = self.config.get('max_replies', max_replies)
        self.max_upvotes = self.config.get('max_upvotes', max_upvotes)
        
        # Get keywords and fixed subreddits from config
        self.keywords = self.config.get('keywords', DEFAULT_KEYWORDS)
        self.fixed_subs = self.config.get('fixed_subs', [])
        
        # Get custom system prompt from config if available
        self.custom_prompt = self.config.get('groq_prompt')
        if self.custom_prompt:
            logger.info(f"Using custom system prompt from config (length: {len(self.custom_prompt)})")
        
        # Activity counters
        self.replies_made = 0
        self.upvotes_made = 0
        
        # Bot ID for logging
        self.bot_id = self.config.get('id', 'default')
        
        logger.info(f"Initializing Reddit Bot ID: {self.bot_id} (Dry Run: {dry_run}, Read Only: {self.read_only})")
        logger.info(f"Activity limits: {self.max_subreddits} subreddits, {self.max_replies} replies, {self.max_upvotes} upvotes")
        logger.info(f"Using {len(self.keywords)} keywords and {len(self.fixed_subs)} fixed subreddits")
        
        # Initialize Reddit API client
        try:
            # Use Reddit's read-only mode which doesn't require authentication
            if self.read_only:
                logger.info("Using Reddit's read-only mode")
                self.reddit = praw.Reddit(
                    client_id=os.environ.get("REDDIT_CLIENT_ID"),
                    client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                    refresh_token=os.environ.get("REDDIT_REFRESH_TOKEN"),
                    user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)"),
                    redirect_uri=os.environ.get("REDDIT_REDIRECT_URI", "http://localhost:8000/reddit/callback"),
                    check_for_updates=False,
                    read_only=True  # This is key - it allows read-only access without authentication
                )
                logger.info("Successfully initialized Reddit client in read-only mode")
            else:
                # For actual posting, we need full authentication
                # Use custom user agent from config if available
                user_agent = os.environ.get("REDDIT_USER_AGENT", f"windows:bot:{self.bot_id}:1.0")
                try:
                    # First try using refresh token (OAuth) authentication
                    refresh_token = os.environ.get("REDDIT_REFRESH_TOKEN")
                    if refresh_token:
                        logger.info("Attempting to authenticate using refresh token")
                        self.reddit = praw.Reddit(
                            client_id=os.environ.get("REDDIT_CLIENT_ID"),
                            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                            refresh_token=refresh_token,
                            user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)")
                        )
                    else:
                        # Fall back to username/password if no refresh token
                        logger.info("No refresh token found, using username/password authentication")
                        self.reddit = praw.Reddit(
                            client_id=os.environ.get("REDDIT_CLIENT_ID"),
                            client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                            username=os.environ.get("REDDIT_USERNAME"),
                            password=os.environ.get("REDDIT_PASSWORD"),
                            user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)")
                        )
                
                    # Verify authentication
                    username = self.reddit.user.me().name
                    logger.info(f"Authenticated as: {username}")
                except Exception as auth_error:
                    logger.warning(f"Authentication failed: {auth_error}. Falling back to read-only mode.")
                    # Fall back to read-only mode
                    self.read_only = True
                    self.reddit = praw.Reddit(
                        client_id=os.environ.get("REDDIT_CLIENT_ID"),
                        client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                        user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)"),
                        check_for_updates=False,
                        read_only=True
                    )
                    logger.info("Fallback to read-only mode successful")
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            sys.exit(1)
        
        # Initialize Groq client using our custom wrapper
        logger.info("Initializing Groq client using GroqWrapper...")
        self.groq_wrapper = GroqWrapper()
        
        # Initialize Groq wrapper for AI-generated replies
        self.groq_wrapper = GroqWrapper()
        
        # Test the custom prompt if available
        if self.custom_prompt and self.groq_wrapper.client:
            logger.info("Testing custom prompt with Groq API...")
            test_messages = [
                {
                    "role": "system",
                    "content": self.custom_prompt + " IMPORTANT: NEVER use quotation marks in your responses."
                },
                {
                    "role": "user",
                    "content": "Test prompt"
                }
            ]
            try:
                test_response = self.groq_wrapper.generate_completion(test_messages)
                logger.info(f"Test response from Groq: {test_response}")
            except Exception as e:
                logger.error(f"Error testing custom prompt: {e}")
                logger.warning("Will fall back to default prompt if needed")
            # Test the Groq wrapper
            test_response = self.groq_wrapper.generate_completion("Say hello!")
            logger.info(f"Test response from Groq: {test_response}")
        else:
            logger.warning("Groq wrapper could not initialize a client, will use fallback responses")
        
        # Initialize log storage
        self.interaction_log = []
        self.replied_posts = set()
        
        # Load previously replied posts if log exists
        self.log_file = os.path.join(log_dir, "interaction_log.json")
        self._load_interaction_log()
    
    def _load_interaction_log(self):
        """Load the interaction log from file if it exists."""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    log_data = json.load(f)
                    self.interaction_log = log_data.get("interactions", [])
                    
                    # Extract post IDs that have already been replied to
                    for interaction in self.interaction_log:
                        if interaction.get("action") == "reply":
                            self.replied_posts.add(interaction.get("post_id"))
                    
                    logger.info(f"Loaded {len(self.interaction_log)} previous interactions")
                    logger.info(f"Found {len(self.replied_posts)} previously replied posts")
        except Exception as e:
            logger.error(f"Error loading interaction log: {e}")
    
    def _save_interaction_log(self):
        """Save the interaction log to a JSON file."""
        try:
            with open(self.log_file, 'w') as f:
                json.dump({"interactions": self.interaction_log}, f, indent=2)
            logger.info(f"Saved {len(self.interaction_log)} interactions to log")
        except Exception as e:
            logger.error(f"Error saving interaction log: {e}")
    
    def _log_interaction(self, action: str, subreddit: str, post_id: str = None, 
                        comment_id: str = None, content: str = None):
        """Log an interaction with Reddit."""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "subreddit": subreddit
        }
        
        if post_id:
            interaction["post_id"] = post_id
        
        if comment_id:
            interaction["comment_id"] = comment_id
            
        if content:
            interaction["content"] = content
            
        self.interaction_log.append(interaction)
        self._save_interaction_log()
    
    def discover_subreddits(self):
        """Discover active subreddits related to our keywords or use fixed subreddits."""
        discovered_subreddits = []
        
        # If we have fixed subreddits in config, use those instead of discovering
        if self.fixed_subs and len(self.fixed_subs) > 0:
            logger.info(f"Using {len(self.fixed_subs)} fixed subreddits from config")
            # Make a copy to avoid modifying the original list
            fixed_subs_copy = self.fixed_subs.copy()
            # Randomize order
            random.shuffle(fixed_subs_copy)
            # Limit to max_subreddits
            discovered_subreddits = fixed_subs_copy[:self.max_subreddits]
            logger.info(f"Selected {len(discovered_subreddits)} fixed subreddits: {', '.join(discovered_subreddits)}")
            return discovered_subreddits
        
        try:
            # Search for subreddits related to our keywords
            for keyword in self.keywords:
                logger.info(f"Searching for subreddits related to '{keyword}'")
                
                # Use Reddit's search to find related subreddits
                search_results = list(self.reddit.subreddits.search(keyword, limit=5))
                
                for subreddit in search_results:
                    # Skip NSFW subreddits
                    if subreddit.over18:
                        logger.info(f"Skipping NSFW subreddit: r/{subreddit.display_name}")
                        continue
                        
                    # Skip subreddits with very low subscriber counts
                    if subreddit.subscribers < 1000:
                        logger.info(f"Skipping small subreddit: r/{subreddit.display_name} ({subreddit.subscribers} subscribers)")
                        continue
                    
                    # Add to our list of discovered subreddits
                    discovered_subreddits.append(subreddit.display_name)
                    logger.info(f"Discovered subreddit: r/{subreddit.display_name} ({subreddit.subscribers} subscribers)")
            
            # Remove duplicates and randomize order
            discovered_subreddits = list(set(discovered_subreddits))
            random.shuffle(discovered_subreddits)
            
            # Limit to max_subreddits
            discovered_subreddits = discovered_subreddits[:self.max_subreddits]
            
            logger.info(f"Discovered {len(discovered_subreddits)} subreddits: {', '.join(discovered_subreddits)}")
            return discovered_subreddits
            
        except Exception as e:
            logger.error(f"Error discovering subreddits: {e}")
            return []
    
    def check_reply_sentiment(self, reply: str) -> bool:
        """Check if a reply is appropriate using sentiment score + keyword filter.
        
        Returns:
            bool: True if the reply is positive and appropriate, False otherwise
        """
        reply_lower = reply.lower()

        # 1. TextBlob sentiment analysis
        blob = TextBlob(reply)
        polarity = blob.sentiment.polarity  # -1 (very negative) to +1 (very positive)
        subjectivity = blob.sentiment.subjectivity

        logger.info(f"Reply sentiment — Polarity: {polarity:.2f}, Subjectivity: {subjectivity:.2f}")

        if polarity < 0.1:
            logger.warning(f"Rejected reply due to low sentiment score ({polarity:.2f}): {reply}")
            return False

        # 2. Keyword-based rejection for obviously toxic or dismissive replies
        negative_patterns = [
            "no idea", "don't know", "not sure", "can't help", "sorry", 
            "don't understand", "what are you talking about", "confused",
            "negative", "bad", "terrible", "awful", "hate", "dislike",
            "stupid", "dumb", "idiot", "fool", "wrong", "incorrect",
            "waste", "boring", "lame", "weird", "strange", "odd",
            "not good", "not great", "not worth", "wouldn't", "shouldn't",
            "can't stand", "annoying", "irritating", "frustrating",
            "wtf", "what the", "huh?", "eh?", "um", "uh"
        ]

        for pattern in negative_patterns:
            if pattern in reply_lower:
                logger.warning(f"Rejected reply due to pattern '{pattern}': {reply}")
                return False

        # 3. Minimum word count (prevents "meh" or one-word replies)
        if len(reply.split()) < 3:
            logger.warning(f"Rejected reply due to short length: {reply}")
            return False

        # 4. Reject questions unless clearly positive
        if reply.count('?') > 0 and not any(word in reply_lower for word in ["cool", "awesome", "nice", "love", "great"]):
            logger.warning(f"Rejected question-style reply: {reply}")
            return False

        return True
    
    def generate_reply(self, post_title: str, post_content: str):
        """Generate a friendly reply using our GroqWrapper."""
        try:
            # Create a prompt for the Groq API
            prompt = f"""Post Title: {post_title}

Post Content: {post_content}

Please write a brief, friendly, and supportive reply to this Reddit post. Keep it under 25 words. DO NOT use quotation marks in your response."""
            
            # Generate a reply using our Groq wrapper
            if self.custom_prompt and self.groq_wrapper.client:
                # If we have a custom system prompt in the config, use it
                messages = [
                    {
                        "role": "system",
                        "content": self.custom_prompt + " IMPORTANT: NEVER use quotation marks in your responses."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
                reply = self.groq_wrapper.generate_completion(messages)
            else:
                # Otherwise use the default prompt in the groq_wrapper
                reply = self.groq_wrapper.generate_completion(prompt)
            
            # Strip any quotation marks from the reply
            reply = reply.strip()
            reply = reply.strip('"')
            reply = reply.strip("'")
            
            # Also remove any internal quotation marks
            reply = reply.replace('"', '')
            reply = reply.replace("'", '')
            
            # Check if the reply is appropriate
            if not self.check_reply_sentiment(reply):
                logger.warning(f"Generated reply failed sentiment check: {reply}")
                return None
                
            return reply
            
        except Exception as e:
            logger.error(f"Error generating reply: {e}")
            return None
        
        logger.warning("Using fallback response after multiple failed attempts")
        return random.choice(fallback_responses)
    
    def reply_to_posts(self, subreddit_name: str):
        """Get recent posts from a subreddit and reply to them."""
        try:
            logger.info(f"Processing subreddit: r/{subreddit_name}")

            # Limit the number of posts based on mode
            max_posts = 2 if self.dry_run else MAX_POSTS_PER_SUBREDDIT
            logger.info(f"Will process up to {max_posts} posts from this subreddit")

            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Update subreddit history in Supabase if we're not in dry run mode
            if not self.dry_run and self.bot_id:
                update_subreddit_history(self.bot_id, subreddit_name)
            
            # Get rising or new posts
            try:
                posts = list(subreddit.rising(limit=max_posts))
                if not posts:
                    posts = list(subreddit.new(limit=max_posts))
                
                logger.info(f"Found {len(posts)} posts in r/{subreddit_name}")
            except Exception as e:
                logger.error(f"Error retrieving posts from r/{subreddit_name}: {e}")
                # In dry run mode, generate some mock posts for testing
                if self.dry_run:
                    logger.info(f"Using mock posts for r/{subreddit_name} in dry run mode")
                    # Create a simple class to mimic Reddit post objects
                    class MockPost:
                        def __init__(self, post_id, title, selftext):
                            self.id = post_id
                            self.title = title
                            self.selftext = selftext
                            self.comments = []
                    
                    # Create mock posts based on the subreddit
                    mock_posts = []
                    if "slime" in subreddit_name.lower():
                        mock_posts.append(MockPost("mock1", "My first slime creation!", "I just made my first slime and it turned out great! Used glue, borax, and food coloring."))
                        mock_posts.append(MockPost("mock2", "Help with slime recipe", "My slime keeps turning out too sticky. What am I doing wrong?"))
                    elif "craft" in subreddit_name.lower():
                        mock_posts.append(MockPost("mock3", "Paper craft ideas for kids", "Looking for simple paper craft ideas for a 5-year-old. Any suggestions?"))
                        mock_posts.append(MockPost("mock4", "My latest knitting project", "Just finished this sweater for my daughter. What do you think?"))
                    elif "parent" in subreddit_name.lower():
                        mock_posts.append(MockPost("mock5", "Activities for rainy days", "What do you do with your kids when you're stuck inside on rainy days?"))
                        mock_posts.append(MockPost("mock6", "Bedtime routine help", "My 3-year-old refuses to go to bed. Any tips for establishing a good bedtime routine?"))
                    else:
                        mock_posts.append(MockPost("mock7", "Organization tips", "How do you keep your kids' toys organized?"))
                        mock_posts.append(MockPost("mock8", "DIY toy repair", "My kid's favorite toy broke. Any ideas for fixing it?"))
                    
                    posts = mock_posts
                    logger.info(f"Created {len(posts)} mock posts for testing")
                else:
                    # If not in dry run mode, we can't proceed without actual posts
                    logger.error(f"Cannot process r/{subreddit_name} without proper authentication")
                    return
            
            for post in posts:
                # Skip posts we've already replied to
                if post.id in self.replied_posts:
                    logger.info(f"Skipping already replied post: {post.id}")
                    continue
                
                # Skip posts with no text content
                if not post.selftext and not post.title:
                    logger.info(f"Skipping post with no content: {post.id}")
                    continue
                
                # Skip posts related to images or photos
                image_keywords = ["image", "photo", "picture", "pic", "look at", "see this", "check out this image", 
                                 "look at this photo", "look at this pic", "what do you see", "what do you think of this image",
                                 "what do you think of this photo", "what do you think of this picture", "what do you think of this pic",
                                 "what's in this image", "what's in this photo", "what's in this picture", "what's in this pic"]
                
                post_text = (post.title + " " + post.selftext).lower()
                if any(keyword.lower() in post_text for keyword in image_keywords):
                    logger.info(f"Skipping image-related post: {post.id}")
                    self._log_interaction("skip", subreddit_name, post_id=post.id, content="Skipped image-related post")
                    continue
                
                # Check if we've hit our reply limit
                if self.replies_made >= self.max_replies:
                    logger.info(f"Reached maximum replies limit ({self.max_replies}). Skipping remaining posts.")
                    break
                
                # Generate and post reply
                reply_text = self.generate_reply(post.title, post.selftext)
                
                if not self.dry_run and not self.read_only:
                    try:
                        post.reply(reply_text)
                        logger.info(f"Posted reply to: {post.id}")
                        self.replied_posts.add(post.id)
                        self.replies_made += 1
                        
                        # Natural delay after commenting (1-3 minutes)
                        comment_delay = random.randint(60, 180)
                        logger.info(f"Adding natural delay of {comment_delay} seconds after commenting...")
                        time.sleep(comment_delay)
                    except Exception as e:
                        if "RATELIMIT" in str(e):
                            logger.warning(f"Rate limited by Reddit: {e}")
                            # If rate limited, sleep for a longer time before continuing
                            sleep_time = 60  # 1 minute
                            logger.info(f"Sleeping for {sleep_time} seconds due to rate limiting")
                            time.sleep(sleep_time)
                        else:
                            logger.error(f"Error posting reply to {post.id}: {e}")
                else:
                    mode = "[DRY RUN]" if self.dry_run else "[READ ONLY]"
                    logger.info(f"{mode} Would reply to post {post.id} with: {reply_text}")
                    # Count simulated replies too
                    self.replies_made += 1
                    
                    # Simulate natural delay in dry run mode
                    comment_delay = random.randint(60, 180)
                    logger.info(f"{mode} Would add natural delay of {comment_delay} seconds after commenting")
                
                # Log the interaction
                self._log_interaction("reply", subreddit_name, post_id=post.id, content=reply_text)
                
                # Check if we've hit our upvote limit
                if self.upvotes_made >= self.max_upvotes:
                    logger.info(f"Reached maximum upvotes limit ({self.max_upvotes}). Skipping upvotes.")
                else:
                    # In dry run or read-only mode, we skip the actual upvoting but still log it
                    mode = "[DRY RUN]" if self.dry_run else "[READ ONLY]"
                    logger.info(f"{mode} Would upvote post: {post.id}")
                    self._log_interaction("upvote", subreddit_name, post_id=post.id)
                    self.upvotes_made += 1
                
                # For mock posts in dry run mode, we don't have real comments to upvote
                if hasattr(post, 'comments') and not isinstance(post.comments, list):
                    # Only try to get comments if it's a real Reddit post object
                    try:
                        post.comments.replace_more(limit=0)  # Flatten comment tree
                        top_comments = list(post.comments)[:MAX_COMMENTS_TO_UPVOTE]
                        
                        for comment in top_comments:
                            if not self.dry_run:
                                try:
                                    comment.upvote()
                                    logger.info(f"Upvoted comment: {comment.id}")
                                except Exception as e:
                                    logger.error(f"Error upvoting comment {comment.id}: {e}")
                            else:
                                mode = "[DRY RUN]" if self.dry_run else "[READ ONLY]"
                                # Check if we've hit our upvote limit
                                if self.upvotes_made >= self.max_upvotes:
                                    logger.info(f"Reached maximum upvotes limit ({self.max_upvotes}). Skipping remaining upvotes.")
                                    break
                                    
                                logger.info(f"{mode} Would upvote comment: {comment.id}")
                                self._log_interaction("upvote", subreddit_name, comment_id=comment.id)
                                self.upvotes_made += 1
                    except Exception as e:
                        logger.error(f"Error processing comments for post {post.id}: {e}")
                else:
                    # For mock posts, log that we would upvote some comments
                    for i in range(MAX_COMMENTS_TO_UPVOTE):
                        mock_comment_id = f"mockcomment{post.id}_{i}"
                        mode = "[DRY RUN]" if self.dry_run else "[READ ONLY]"
                        # Check if we've hit our upvote limit
                        if self.upvotes_made >= self.max_upvotes:
                            logger.info(f"Reached maximum upvotes limit ({self.max_upvotes}). Skipping remaining upvotes.")
                            break
                            
                        logger.info(f"{mode} Would upvote comment: {mock_comment_id}")
                        self._log_interaction("upvote", subreddit_name, comment_id=mock_comment_id)
                        self.upvotes_made += 1
                
                # Only add a small delay between post processing if we didn't just comment
                # (If we commented, we already added a longer natural delay)
                if not reply_text:  # No comment was made, just add a small delay
                    time.sleep(SLEEP_BETWEEN_ACTIONS)
                
        except Exception as e:
            logger.error(f"Error processing subreddit r/{subreddit_name}: {e}")
    
    def run(self):
        """Run the bot to discover subreddits and reply to posts."""
        try:
            # Discover relevant subreddits
            subreddits = self.discover_subreddits()
            logger.info(f"Discovered {len(subreddits)} relevant subreddits")
            
            # Limit the number of subreddits to process
            if len(subreddits) > self.max_subreddits:
                logger.info(f"Limiting to {self.max_subreddits} subreddits (out of {len(subreddits)} discovered)")
                
                # Select a diverse set of subreddits
                selected_subreddits = []
                categories = ['slime', 'craft', 'parent', 'toy', 'home']
                
                # Try to get one subreddit from each category
                for category in categories:
                    if len(selected_subreddits) >= self.max_subreddits:
                        break
                        
                    for subreddit in subreddits:
                        if category in subreddit.lower() and subreddit not in selected_subreddits:
                            selected_subreddits.append(subreddit)
                            break
                
                # If we couldn't find enough category-specific subreddits, add more until we reach the limit
                remaining_slots = self.max_subreddits - len(selected_subreddits)
                if remaining_slots > 0:
                    for subreddit in subreddits:
                        if subreddit not in selected_subreddits:
                            selected_subreddits.append(subreddit)
                            remaining_slots -= 1
                            if remaining_slots == 0:
                                break
                
                subreddits = selected_subreddits
                logger.info(f"Selected subreddits: {subreddits}")
            
            # Process each subreddit until we hit our reply/upvote limits
            subreddits_processed = 0
            for subreddit in subreddits:
                # Check if we've hit our limits
                if self.replies_made >= self.max_replies:
                    logger.info(f"Reached maximum replies limit ({self.max_replies}). Stopping.")
                    break
                    
                if self.upvotes_made >= self.max_upvotes:
                    logger.info(f"Reached maximum upvotes limit ({self.max_upvotes}). Stopping.")
                    break
                
                self.reply_to_posts(subreddit)
                subreddits_processed += 1
                
                # Add a longer pause between subreddits to respect rate limits
                time.sleep(SLEEP_BETWEEN_ACTIONS * 2)
            
            logger.info(f"Bot run completed successfully. Processed {subreddits_processed} subreddits.")
            logger.info(f"Made {self.replies_made} replies and {self.upvotes_made} upvotes.")
            
        except Exception as e:
            logger.error(f"Error during bot run: {e}")


def main():
    """Main entry point for the Reddit bot."""
    parser = argparse.ArgumentParser(description="Run the Reddit bot.")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no actual posts)")
    parser.add_argument("--read-only", action="store_true", help="Run in read-only mode (no posts or upvotes)")
    parser.add_argument("--subreddit", type=str, help="Process a specific subreddit only")
    parser.add_argument("--limit", type=int, default=MAX_POSTS_PER_SUBREDDIT, 
                        help=f"Maximum number of posts to process per subreddit (default: {MAX_POSTS_PER_SUBREDDIT})")
    parser.add_argument("--max-subreddits", type=int, default=DEFAULT_MAX_SUBREDDITS_PER_RUN, 
                        help=f"Maximum number of subreddits to process (default: {DEFAULT_MAX_SUBREDDITS_PER_RUN})")
    parser.add_argument("--max-replies", type=int, default=DEFAULT_MAX_TOTAL_REPLIES_PER_RUN,
                        help=f"Maximum number of replies to make (default: {DEFAULT_MAX_TOTAL_REPLIES_PER_RUN})")
    parser.add_argument("--max-upvotes", type=int, default=DEFAULT_MAX_TOTAL_UPVOTES_PER_RUN,
                        help=f"Maximum number of upvotes to make (default: {DEFAULT_MAX_TOTAL_UPVOTES_PER_RUN})")
    parser.add_argument("--bot-id", type=str, default=os.environ.get("BOT_ID", ""),
                        help="Bot ID to load configuration from Supabase")
    parser.add_argument("--no-delay", action="store_true", help="Disable natural delays between actions")
    args = parser.parse_args()
    
    # Load configuration from Supabase if bot_id is provided
    bot_config = None
    if args.bot_id:
        logger.info(f"Loading configuration for bot: {args.bot_id}")
        bot_config = load_bot_config(args.bot_id)
        if not bot_config:
            logger.error(f"Failed to load configuration for bot: {args.bot_id}")
            sys.exit(1)
        
        # Set environment variables from bot configuration
        setup_environment_from_config(bot_config)
    
    # Create and run the bot
    bot = RedditBot(
        dry_run=args.dry_run,
        read_only=args.read_only,
        max_subreddits=args.max_subreddits,
        max_replies=args.max_replies if not bot_config else bot_config.get("max_replies", args.max_replies),
        max_upvotes=args.max_upvotes if not bot_config else bot_config.get("max_upvotes", args.max_upvotes),
        config=bot_config
    )
    
    # If a specific subreddit was provided, only process that one
    if args.subreddit:
        logger.info(f"Processing only subreddit: r/{args.subreddit}")
        # Set the limit for posts per subreddit
        # Note: We're modifying a module-level variable, but avoiding global statement
        # since it's already defined at the module level
        bot.reply_to_posts(args.subreddit)
    else:
        # Run the full bot workflow
        bot.run()
    
    logger.info("Bot execution completed")


if __name__ == "__main__":
    main()
