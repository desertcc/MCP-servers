#!/usr/bin/env python3
"""
Reddit MCP Automation Bot

A bot that discovers and interacts with subreddits related to slime, crafts, kids, parenting, home, and toys.
Uses Groq API to generate friendly, helpful replies and upvotes positive content.
"""

import os
import sys
import json
import time
import random
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Set, Optional

import praw
# Import our custom GroqWrapper instead of direct Groq import
from groq_wrapper import GroqWrapper
from dotenv import load_dotenv

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
KEYWORDS = ["slime", "crafts", "kids", "parenting", "home", "toys"]
MAX_POSTS_PER_SUBREDDIT = 5
MAX_COMMENTS_TO_UPVOTE = 3
SLEEP_BETWEEN_ACTIONS = 5  # seconds - increased to avoid rate limiting
SLEEP_BETWEEN_POSTS = 10  # seconds - longer delay between posting to avoid rate limiting

# Activity limits
MAX_SUBREDDITS_PER_RUN = 3  # Maximum number of subreddits to process in a single run
MAX_TOTAL_REPLIES_PER_RUN = 10  # Maximum number of replies to post in a single run
MAX_TOTAL_UPVOTES_PER_RUN = 20  # Maximum number of upvotes to perform in a single run

class RedditBot:
    """Reddit Automation Bot for positive engagement in family-friendly subreddits."""
    
    def __init__(self, dry_run: bool = False, read_only: bool = False, max_subreddits: int = MAX_SUBREDDITS_PER_RUN, max_replies: int = MAX_TOTAL_REPLIES_PER_RUN, max_upvotes: int = MAX_TOTAL_UPVOTES_PER_RUN):
        """Initialize the Reddit bot with API credentials.
        
        Args:
            dry_run: If True, don't make actual posts or upvotes
            read_only: If True, use Reddit's read-only mode (no authentication required)
        """
        self.dry_run = dry_run
        self.read_only = read_only or dry_run  # Always use read_only for dry_run
        self.max_subreddits = max_subreddits
        self.max_replies = max_replies
        self.max_upvotes = max_upvotes
        
        # Activity counters
        self.replies_made = 0
        self.upvotes_made = 0
        
        logger.info(f"Initializing Reddit Bot (Dry Run: {dry_run}, Read Only: {self.read_only})")
        logger.info(f"Activity limits: {max_subreddits} subreddits, {max_replies} replies, {max_upvotes} upvotes")
        
        # Initialize Reddit API client
        try:
            # Use Reddit's read-only mode which doesn't require authentication
            if self.read_only:
                logger.info("Using Reddit's read-only mode")
                self.reddit = praw.Reddit(
                    client_id=os.environ.get("REDDIT_CLIENT_ID"),
                    client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
                    user_agent=os.environ.get("REDDIT_USER_AGENT", "windows:slime_bot:1.0 (by u/Slime_newbie)"),
                    redirect_uri=os.environ.get("REDDIT_REDIRECT_URI", "http://localhost:8000/reddit/callback"),
                    check_for_updates=False,
                    read_only=True  # This is key - it allows read-only access without authentication
                )
                logger.info("Successfully initialized Reddit client in read-only mode")
            else:
                # For actual posting, we need full authentication
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
        
        # Test if the wrapper was initialized successfully
        if self.groq_wrapper.client:
            logger.info("Groq wrapper initialized successfully")
            test_response = self.groq_wrapper.generate_completion("Hello")
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
    
    def discover_subreddits(self) -> List[str]:
        """Discover active subreddits related to our keywords."""
        discovered_subreddits = set()
        
        logger.info(f"Discovering subreddits using keywords: {KEYWORDS}")
        
        # In dry run mode with authentication issues, use a predefined list of relevant subreddits
        if self.dry_run:
            # These are popular subreddits related to our keywords
            predefined_subreddits = [
                "slime", "crafts", "DIY", "parenting", "Parenting", "crafting", 
                "slimerancher", "SlimeRancher", "kidscrafts", "toys", "toyexchange", 
                "homemaking", "homeimprovement", "organization"
            ]
            
            logger.info(f"Using predefined list of {len(predefined_subreddits)} subreddits for dry run")
            for subreddit_name in predefined_subreddits:
                discovered_subreddits.add(subreddit_name)
                logger.info(f"Added predefined subreddit: r/{subreddit_name}")
            
            return list(discovered_subreddits)
        
        # If not in dry run mode or if we have proper authentication, discover subreddits dynamically
        for keyword in KEYWORDS:
            try:
                logger.info(f"Searching for subreddits with keyword: {keyword}")
                search_results = self.reddit.subreddits.search(keyword, limit=5)
                
                for subreddit in search_results:
                    # Only include active subreddits with at least 1000 subscribers
                    # Handle case where subscribers might be None
                    if subreddit.subscribers is not None and subreddit.subscribers > 1000:
                        discovered_subreddits.add(subreddit.display_name)
                        logger.info(f"Found subreddit: r/{subreddit.display_name} with {subreddit.subscribers} subscribers")
                
                # Respect rate limits
                time.sleep(SLEEP_BETWEEN_ACTIONS)
                
            except Exception as e:
                logger.error(f"Error discovering subreddits for keyword '{keyword}': {e}")
        
        return list(discovered_subreddits)
    
    def check_reply_sentiment(self, reply: str) -> bool:
        """Check if a reply has appropriate sentiment and content.
        
        Returns:
            bool: True if the reply is positive and appropriate, False otherwise
        """
        # List of negative phrases or patterns that indicate an inappropriate response
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
        
        # Check for negative patterns
        reply_lower = reply.lower()
        for pattern in negative_patterns:
            if pattern in reply_lower:
                logger.warning(f"Rejected reply due to negative pattern '{pattern}': {reply}")
                return False
        
        # Check for minimum length (too short might be dismissive)
        if len(reply.split()) < 3:
            logger.warning(f"Rejected reply due to being too short: {reply}")
            return False
        
        # Check for question marks (we want statements, not questions)
        if reply.count('?') > 0 and not any(positive in reply_lower for positive in ["cool", "awesome", "nice", "love", "great"]):
            logger.warning(f"Rejected reply because it's a question without positive sentiment: {reply}")
            return False
            
        return True
    
    def generate_reply(self, post_title: str, post_content: str) -> str:
        """Generate a friendly reply using our GroqWrapper."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a POSITIVE and SUPPORTIVE Reddit commenter responding to posts about slime, crafts, parenting, and toys. "
                    "Your replies MUST be warm, encouraging, and helpful - never confused, dismissive, or negative. "
                    "Limit replies to 1-2 concise, supportive sentences. Maximum 25 words total. "
                    "Sound casual and warm like a fellow parent or crafter - not overly formal. "
                    "Use a conversational tone. No quotes, no greetings, no summarizing. "
                    "If you're unsure what the post is about, respond with something generally positive about creativity or sharing."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Write a super brief, casual, POSITIVE Reddit reply. Be supportive and encouraging.\n\n"
                    f"Title: {post_title}\nContent: {post_content}\n\nReply:"
                )
            }
        ]
        
        # Try up to 3 times to get a good reply
        for attempt in range(3):
            reply = self.groq_wrapper.generate_completion(messages)
            
            if self.check_reply_sentiment(reply):
                return reply
            
            logger.info(f"Attempt {attempt+1} produced inappropriate reply, trying again...")
        
        # If all attempts failed, use a safe fallback response
        fallback_responses = [
            "Love this idea! Thanks for sharing your creativity.",
            "This is so cool! Really appreciate you sharing.",
            "Awesome work! This community always has the best ideas.",
            "So creative! Can't wait to see what you make next.",
            "This is fantastic! Thanks for the inspiration."
        ]
        
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
                        # Use longer sleep after posting to avoid rate limiting
                        time.sleep(SLEEP_BETWEEN_POSTS)
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
                
                # Respect rate limits
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
    parser = argparse.ArgumentParser(description="Reddit MCP Automation Bot")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no actual posts or upvotes)")
    parser.add_argument("--read-only", action="store_true", help="Run in read-only mode (no authentication required)")
    parser.add_argument("--subreddit", type=str, help="Process a specific subreddit only")
    parser.add_argument("--limit", type=int, default=2, help="Maximum number of posts to process per subreddit")
    parser.add_argument("--force-auth", action="store_true", help="Force authentication attempt even if it failed previously")
    parser.add_argument("--max-subreddits", type=int, default=MAX_SUBREDDITS_PER_RUN, 
                      help=f"Maximum number of subreddits to process (default: {MAX_SUBREDDITS_PER_RUN})")
    parser.add_argument("--max-replies", type=int, default=MAX_TOTAL_REPLIES_PER_RUN, 
                      help=f"Maximum number of replies to post (default: {MAX_TOTAL_REPLIES_PER_RUN})")
    parser.add_argument("--max-upvotes", type=int, default=MAX_TOTAL_UPVOTES_PER_RUN, 
                      help=f"Maximum number of upvotes to perform (default: {MAX_TOTAL_UPVOTES_PER_RUN})")
    args = parser.parse_args()
    
    logger.info(f"Starting Reddit MCP Automation Bot (Dry Run: {args.dry_run}, Read Only: {args.read_only})")
    
    # If force-auth is specified, temporarily set read_only to False to force an authentication attempt
    read_only = args.read_only
    if args.force_auth:
        logger.info("Force authentication mode enabled - will attempt to authenticate even if read-only is specified")
        read_only = False
    
    # Initialize the bot with activity limits
    bot = RedditBot(
        dry_run=args.dry_run, 
        read_only=read_only,
        max_subreddits=args.max_subreddits,
        max_replies=args.max_replies,
        max_upvotes=args.max_upvotes
    )
    
    # If a specific subreddit was provided, only process that one
    if args.subreddit:
        logger.info(f"Processing only subreddit: r/{args.subreddit}")
        global MAX_POSTS_PER_SUBREDDIT
        MAX_POSTS_PER_SUBREDDIT = args.limit
        bot.reply_to_posts(args.subreddit)
    else:
        # Run the full bot workflow
        bot.run()
    
    logger.info("Bot execution completed")


if __name__ == "__main__":
    main()
