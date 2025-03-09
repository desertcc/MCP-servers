import asyncio
import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import base64
import urllib.parse
import uuid

import aiohttp
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
import platform

if platform.system() == "Darwin":  # macOS
    log_dir = os.path.expanduser("~/Library/Logs/Claude")
elif platform.system() == "Windows":
    log_dir = os.path.join(os.getenv("APPDATA"), "Claude", "logs")
else:  # Linux or other
    log_dir = os.path.expanduser("~/.claude/logs")
log_file = os.path.join(log_dir, "mcp_reddit.log")
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("reddit_mcp")

# Constants for Reddit API
REDDIT_API_BASE = "https://www.reddit.com"
REDDIT_OAUTH_API_BASE = "https://oauth.reddit.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# These should be set as environment variables or as a config
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET",)
REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", "")

# Global auth token storage
auth_token = {
    "access_token": "",
    "token_type": "bearer",
    "expires_at": datetime.now()
}

# Request tracking for rate limiting and debugging
request_history = []
request_cache = {}  # Simple cache to avoid duplicate requests

# Initialize MCP server
app = Server("reddit-browser")

# Helper function to get or refresh auth token
async def get_auth_token() -> str:
    """Get a valid OAuth token, refreshing if necessary."""
    global auth_token
    
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"AUTH-{request_id}: Checking if token refresh is needed")
    
    # Check if token is still valid with 5 min buffer
    if auth_token["access_token"] and auth_token["expires_at"] > datetime.now() + timedelta(minutes=5):
        logger.info(f"AUTH-{request_id}: Using existing token valid until {auth_token['expires_at']}")
        return auth_token["access_token"]
    
    # Need to get a new token
    logger.info(f"AUTH-{request_id}: Token expired or not present, requesting new token")
    
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET or not REDDIT_USERNAME or not REDDIT_PASSWORD:
        logger.error(f"AUTH-{request_id}: Missing Reddit API credentials")
        raise ValueError("Reddit API credentials not configured. Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME and REDDIT_PASSWORD environment variables.")
    
    auth_string = base64.b64encode(f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}".encode()).decode()
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Basic {auth_string}"
        }
        data = {
            "grant_type": "password",
            "username": REDDIT_USERNAME,
            "password": "********"  # Log masked password
        }
        
        logger.info(f"AUTH-{request_id}: Sending POST request to /api/v1/access_token")
        start_time = time.time()
        
        try:
            async with session.post(
                "https://www.reddit.com/api/v1/access_token",
                headers=headers,
                data={
                    "grant_type": "password",
                    "username": REDDIT_USERNAME,
                    "password": REDDIT_PASSWORD  # Use actual password in request
                }
            ) as response:
                elapsed_time = time.time() - start_time
                status_code = response.status
                
                if not response.ok:
                    text = await response.text()
                    logger.error(f"AUTH-{request_id}: Failed to get auth token: {status_code} ({elapsed_time:.2f}s) - {text}")
                    raise ValueError(f"Failed to get auth token: {status_code} - {text}")
                
                token_data = await response.json()
                logger.info(f"AUTH-{request_id}: Successfully obtained token: {status_code} ({elapsed_time:.2f}s)")
                
                # Update token storage
                auth_token = {
                    "access_token": token_data["access_token"],
                    "token_type": token_data["token_type"],
                    "expires_at": datetime.now() + timedelta(seconds=token_data["expires_in"])
                }
                
                logger.info(f"AUTH-{request_id}: Token expires at {auth_token['expires_at']}")
                return auth_token["access_token"]
        except Exception as e:
            logger.exception(f"AUTH-{request_id}: Error getting auth token: {str(e)}")
            raise

# Helper function to make Reddit API requests (authenticated or not)
async def fetch_reddit_data(endpoint: str, params: Dict[str, str] = None, authenticated: bool = False, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Fetch data from Reddit API with proper error handling."""
    if params is None:
        params = {}
    
    # Generate a unique ID for this request for logging
    request_id = str(uuid.uuid4())[:8]
    
    # Check cache for GET requests
    cache_key = None
    if method == "GET":
        cache_key = f"{endpoint}:{json.dumps(params)}:{authenticated}"
        if cache_key in request_cache:
            cache_entry = request_cache[cache_key]
            # Check if cache entry is still fresh (less than 30 seconds old)
            if time.time() - cache_entry["timestamp"] < 30:
                logger.info(f"API-{request_id}: Cache hit for {endpoint}")
                return cache_entry["data"]
    
    if authenticated:
        # Use OAuth API endpoint with authentication
        base_url = REDDIT_OAUTH_API_BASE
        token = await get_auth_token()
        headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded" if method == "POST" else "application/json"
        }
        logger.info(f"API-{request_id}: Authenticated request to {endpoint}")
    else:
        # Use public API endpoint
        base_url = REDDIT_API_BASE
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
        logger.info(f"API-{request_id}: Public request to {endpoint}")
    
    # Add .json to the endpoint if it's a GET request to public API
    url = f"{base_url}{endpoint}"
    if not authenticated and method == "GET":
        url += ".json"
    
    # Log request details
    log_params = params.copy() if params else {}
    log_data = None
    if data:
        # Create a copy of data for logging, masking sensitive fields
        log_data = data.copy()
        if "password" in log_data:
            log_data["password"] = "********"
    
    logger.info(f"API-{request_id}: {method} {url} params={log_params} data={log_data}")
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as response:
                    status_code = response.status
                    elapsed_time = time.time() - start_time
                    
                    # Add to request history
                    request_history.append({
                        "id": request_id,
                        "timestamp": datetime.now().isoformat(),
                        "method": method,
                        "url": url,
                        "status": status_code,
                        "elapsed_time": elapsed_time
                    })
                    
                    if len(request_history) > 100:
                        request_history.pop(0)  # Keep history manageable
                    
                    logger.info(f"API-{request_id}: Response status {status_code} ({elapsed_time:.2f}s)")
                    
                    if not response.ok:
                        response_text = await response.text()
                        logger.error(f"API-{request_id}: HTTP error! status: {status_code}, response: {response_text}")
                        raise ValueError(f"HTTP error! status: {status_code}, response: {response_text}")
                    
                    response_data = await response.json()
                    
                    # Cache successful GET responses
                    if cache_key:
                        request_cache[cache_key] = {
                            "timestamp": time.time(),
                            "data": response_data
                        }
                        # Trim cache if it gets too large
                        if len(request_cache) > 50:
                            oldest_key = min(request_cache.keys(), key=lambda k: request_cache[k]["timestamp"])
                            del request_cache[oldest_key]
                    
                    # Log response summary
                    if isinstance(response_data, dict) and "data" in response_data:
                        if "children" in response_data["data"]:
                            children_count = len(response_data["data"]["children"])
                            logger.info(f"API-{request_id}: Got {children_count} items")
                        elif "name" in response_data["data"]:
                            logger.info(f"API-{request_id}: Got data for {response_data['data'].get('name', 'unknown')}")
                    elif isinstance(response_data, list):
                        logger.info(f"API-{request_id}: Got list with {len(response_data)} items")
                    
                    return response_data
            elif method == "POST":
                async with session.post(url, headers=headers, data=data) as response:
                    status_code = response.status
                    elapsed_time = time.time() - start_time
                    
                    # Add to request history
                    request_history.append({
                        "id": request_id,
                        "timestamp": datetime.now().isoformat(),
                        "method": method,
                        "url": url,
                        "status": status_code,
                        "elapsed_time": elapsed_time
                    })
                    
                    if len(request_history) > 100:
                        request_history.pop(0)
                    
                    logger.info(f"API-{request_id}: Response status {status_code} ({elapsed_time:.2f}s)")
                    
                    if not response.ok:
                        response_text = await response.text()
                        logger.error(f"API-{request_id}: HTTP error! status: {status_code}, response: {response_text}")
                        raise ValueError(f"HTTP error! status: {status_code}, response: {response_text}")
                    
                    try:
                        response_data = await response.json()
                        
                        # Log response summary for POST requests
                        if isinstance(response_data, dict):
                            if "json" in response_data and "data" in response_data["json"]:
                                logger.info(f"API-{request_id}: POST successful with data returned")
                            elif "status" in response_data:
                                logger.info(f"API-{request_id}: POST status: {response_data['status']}")
                        
                        return response_data
                    except:
                        logger.info(f"API-{request_id}: POST successful but no JSON response")
                        return {"status": "success", "status_code": status_code}
            elif method == "PUT":
                async with session.put(url, headers=headers, data=data) as response:
                    status_code = response.status
                    elapsed_time = time.time() - start_time
                    
                    # Add to request history
                    request_history.append({
                        "id": request_id,
                        "timestamp": datetime.now().isoformat(),
                        "method": method,
                        "url": url,
                        "status": status_code,
                        "elapsed_time": elapsed_time
                    })
                    
                    if len(request_history) > 100:
                        request_history.pop(0)
                    
                    logger.info(f"API-{request_id}: Response status {status_code} ({elapsed_time:.2f}s)")
                    
                    if not response.ok:
                        response_text = await response.text()
                        logger.error(f"API-{request_id}: HTTP error! status: {status_code}, response: {response_text}")
                        raise ValueError(f"HTTP error! status: {status_code}, response: {response_text}")
                    
                    try:
                        response_data = await response.json()
                        return response_data
                    except:
                        logger.info(f"API-{request_id}: PUT successful but no JSON response")
                        return {"status": "success", "status_code": status_code}
            elif method == "DELETE":
                async with session.delete(url, headers=headers) as response:
                    status_code = response.status
                    elapsed_time = time.time() - start_time
                    
                    # Add to request history
                    request_history.append({
                        "id": request_id,
                        "timestamp": datetime.now().isoformat(),
                        "method": method,
                        "url": url,
                        "status": status_code,
                        "elapsed_time": elapsed_time
                    })
                    
                    if len(request_history) > 100:
                        request_history.pop(0)
                    
                    logger.info(f"API-{request_id}: Response status {status_code} ({elapsed_time:.2f}s)")
                    
                    if not response.ok:
                        response_text = await response.text()
                        logger.error(f"API-{request_id}: HTTP error! status: {status_code}, response: {response_text}")
                        raise ValueError(f"HTTP error! status: {status_code}, response: {response_text}")
                    
                    try:
                        response_data = await response.json()
                        return response_data
                    except:
                        logger.info(f"API-{request_id}: DELETE successful but no JSON response")
                        return {"status": "success", "status_code": status_code}
    except Exception as e:
        logger.exception(f"API-{request_id}: Error fetching data from Reddit: {str(e)}")
        raise

# Format post data for output
def format_post(post: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Reddit post for consistent output."""
    data = post.get("data", {})
    formatted = {
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "subreddit": data.get("subreddit_name_prefixed", ""),
        "upvotes": data.get("ups", 0),
        "url": f"https://www.reddit.com{data.get('permalink', '')}",
        "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
        "selftext": data.get("selftext", "[No text content]"),
        "is_video": data.get("is_video", False),
        "is_image": data.get("post_hint", "") == "image",
        "num_comments": data.get("num_comments", 0),
        "id": data.get("id", ""),
        "fullname": data.get("name", ""),
        "saved": data.get("saved", False),
        "stickied": data.get("stickied", False),
        "locked": data.get("locked", False),
        "over_18": data.get("over_18", False),
    }
    logger.debug(f"Formatted post: {formatted['title']}")
    return formatted

# Format comment data for output
def format_comment(comment: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Reddit comment for consistent output."""
    if comment.get("kind") == "more" or not comment.get("data"):
        logger.debug("Formatted 'more comments' object")
        return {"more_comments": True}
    
    data = comment.get("data", {})
    formatted = {
        "id": data.get("id", ""),
        "fullname": data.get("name", ""),
        "author": data.get("author", ""),
        "body": data.get("body", ""),
        "body_html": data.get("body_html", ""),
        "upvotes": data.get("ups", 0),
        "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
        "edited": bool(data.get("edited", False)),
        "permalink": f"https://www.reddit.com{data.get('permalink', '')}" if data.get("permalink") else None,
        "saved": data.get("saved", False),
        "stickied": data.get("stickied", False),
    }
    
    # Format any replies
    if data.get("replies") and isinstance(data["replies"], dict) and data["replies"].get("data") and data["replies"]["data"].get("children"):
        formatted["replies"] = [format_comment(reply) for reply in data["replies"]["data"]["children"]]
    else:
        formatted["replies"] = []
    
    logger.debug(f"Formatted comment from: {formatted['author']}")
    return formatted

# Format subreddit data for output
def format_subreddit(subreddit: Dict[str, Any]) -> Dict[str, Any]:
    """Format a subreddit for consistent output."""
    data = subreddit.get("data", {})
    formatted = {
        "display_name": data.get("display_name", ""),
        "title": data.get("title", ""),
        "public_description": data.get("public_description", ""),
        "subscribers": data.get("subscribers", 0),
        "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
        "url": data.get("url", ""),
        "over18": data.get("over18", False),
        "description": data.get("description", ""),
        "is_default": data.get("is_default", False),
        "user_is_subscriber": data.get("user_is_subscriber", False),
        "user_is_banned": data.get("user_is_banned", False),
        "user_is_moderator": data.get("user_is_moderator", False),
    }
    logger.debug(f"Formatted subreddit: {formatted['display_name']}")
    return formatted

# Format message data for output
def format_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Reddit message for consistent output."""
    data = message.get("data", {})
    formatted = {
        "id": data.get("id", ""),
        "fullname": data.get("name", ""),
        "author": data.get("author", ""),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
        "was_comment": data.get("was_comment", False),
        "dest": data.get("dest", ""),
        "new": data.get("new", False),
    }
    logger.debug(f"Formatted message: {formatted['subject']}")
    return formatted

# Format notification data for output
def format_notification(notification: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Reddit notification for consistent output."""
    data = notification.get("data", {})
    formatted = {
        "id": data.get("id", ""),
        "fullname": data.get("name", ""),
        "type": data.get("type", ""),
        "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
        "context": data.get("context", ""),
        "subject": data.get("subject", ""),
        "body": data.get("body", ""),
        "link_title": data.get("link_title", ""),
        "subreddit": data.get("subreddit", ""),
        "was_comment": data.get("was_comment", False),
    }
    logger.debug(f"Formatted notification with ID: {formatted['id']}")
    return formatted

# Register tools
@app.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available tools for the Reddit MCP server."""
    logger.info("MCP: list_tools called")
    tool_list = [
        types.Tool(
            name="browse_subreddit",
            description="Browse posts from a specific subreddit",
            inputSchema={
                "type": "object",
                "properties": {
                    "subreddit": {
                        "type": "string",
                        "description": "Name of the subreddit (without r/)"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["hot", "new", "rising", "top", "controversial"],
                        "description": "Sort method for posts"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of posts to return (max 25)"
                    },
                    "time": {
                        "type": "string",
                        "enum": ["hour", "day", "week", "month", "year", "all"],
                        "description": "Time period for 'top' or 'controversial' sorting"
                    }
                },
                "required": ["subreddit"]
            }
        ),
        types.Tool(
            name="get_post",
            description="Get a specific Reddit post and its comments",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Reddit post ID (usually a 6-character alphanumeric string)"
                    },
                    "subreddit": {
                        "type": "string",
                        "description": "Subreddit containing the post (without r/)"
                    },
                    "comment_sort": {
                        "type": "string",
                        "enum": ["confidence", "top", "new", "controversial", "old", "qa"],
                        "description": "Sort method for comments"
                    },
                    "comment_limit": {
                        "type": "number",
                        "description": "Number of comments to return (max 25)"
                    }
                },
                "required": ["post_id", "subreddit"]
            }
        ),
        types.Tool(
            name="search_reddit",
            description="Search Reddit for posts matching a query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "subreddit": {
                        "type": "string",
                        "description": "Limit search to a specific subreddit (optional, without r/)"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["relevance", "hot", "top", "new", "comments"],
                        "description": "Sort method for search results"
                    },
                    "time": {
                        "type": "string",
                        "enum": ["hour", "day", "week", "month", "year", "all"],
                        "description": "Time period for results"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of results to return (max 25)"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_user_profile",
            description="Get information about a Reddit user and their recent posts/comments",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Reddit username (without u/)"
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["new", "hot", "top", "controversial"],
                        "description": "Sort method for user's posts/comments"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of posts/comments to return (max 25)"
                    }
                },
                "required": ["username"]
            }
        ),
        types.Tool(
            name="submit_post",
            description="Submit a new post to a subreddit",
            inputSchema={
                "type": "object",
                "properties": {
                    "subreddit": {
                        "type": "string",
                        "description": "Name of the subreddit to post to (without r/)"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the post"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content for text posts"
                    },
                    "url": {
                        "type": "string",
                        "description": "URL for link posts"
                    },
                    "flair_id": {
                        "type": "string",
                        "description": "Flair ID for the post (optional)"
                    },
                    "flair_text": {
                        "type": "string",
                        "description": "Flair text for the post (optional)"
                    }
                },
                "required": ["subreddit", "title"]
            }
        ),
        types.Tool(
            name="submit_comment",
            description="Submit a comment on a post or another comment",
            inputSchema={
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "Full ID of post or comment to reply to (e.g., t3_abcdef for posts, t1_abcdef for comments)"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content of the comment"
                    }
                },
                "required": ["thing_id", "text"]
            }
        ),
        types.Tool(
            name="vote",
            description="Cast a vote on a post or comment",
            inputSchema={
                "type": "object",
                "properties": {
                    "thing_id": {
                        "type": "string",
                        "description": "Full ID of post or comment to vote on (e.g., t3_abcdef for posts, t1_abcdef for comments)"
                    },
                    "direction": {
                        "type": "number",
                        "enum": [1, 0, -1],
                        "description": "Vote direction: 1 for upvote, -1 for downvote, 0 to remove vote"
                    }
                },
                "required": ["thing_id", "direction"]
            }
        ),
        types.Tool(
            name="get_subreddit_rules",
            description="Get the rules for a subreddit",
            inputSchema={
                "type": "object",
                "properties": {
                    "subreddit": {
                        "type": "string",
                        "description": "Name of the subreddit (without r/)"
                    }
                },
                "required": ["subreddit"]
            }
        ),
        # New diagnostic tool to see recent API calls
        types.Tool(
            name="get_request_stats",
            description="Get statistics about recent API requests",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Number of recent requests to show (default: 10)"
                    }
                }
            }
        )
    ]
    logger.info(f"MCP: Returning {len(tool_list)} available tools")
    return tool_list

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls for the Reddit MCP server."""
    tool_id = str(uuid.uuid4())[:8]
    logger.info(f"TOOL-{tool_id}: Call to '{name}' with arguments: {arguments}")
    
    try:
        # Browse subreddit
        if name == "browse_subreddit":
            subreddit = arguments.get("subreddit")
            sort = arguments.get("sort", "hot")
            limit = min(int(arguments.get("limit", 10)), 25)
            time = arguments.get("time", "day")
            
            logger.info(f"TOOL-{tool_id}: Browsing r/{subreddit} sorted by {sort}")
            
            params = {"limit": str(limit)}
            
            # Add time parameter if sort is top or controversial
            if (sort in ["top", "controversial"]) and time:
                params["t"] = time
            
            data = await fetch_reddit_data(f"/r/{subreddit}/{sort}", params)
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No posts found for r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find subreddit r/{subreddit} or it has no posts."
                )]
            
            posts = [format_post(post) for post in data["data"]["children"]]
            
            result = {
                "subreddit": f"r/{subreddit}",
                "sort": sort,
                "posts": posts
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(posts)} posts from r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Get post and comments
        elif name == "get_post":
            post_id = arguments.get("post_id")
            subreddit = arguments.get("subreddit")
            comment_sort = arguments.get("comment_sort", "confidence")
            comment_limit = min(int(arguments.get("comment_limit", 10)), 25)
            
            logger.info(f"TOOL-{tool_id}: Getting post {post_id} from r/{subreddit}")
            
            params = {
                "sort": comment_sort,
                "limit": str(comment_limit)
            }
            
            data = await fetch_reddit_data(f"/r/{subreddit}/comments/{post_id}", params)
            
            if not data or not data[0].get("data") or not data[0]["data"].get("children") or len(data[0]["data"]["children"]) == 0:
                logger.warning(f"TOOL-{tool_id}: Post {post_id} not found in r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find post with ID {post_id} in r/{subreddit}."
                )]
            
            post = format_post(data[0]["data"]["children"][0])
            
            comments = []
            if len(data) > 1 and data[1].get("data") and data[1]["data"].get("children"):
                comments = [format_comment(comment) for comment in data[1]["data"]["children"]]
            
            result = {
                "post": post,
                "comments": comments
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved post {post_id} with {len(comments)} comments")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Search Reddit
        elif name == "search_reddit":
            query = arguments.get("query")
            subreddit = arguments.get("subreddit")
            sort = arguments.get("sort", "relevance")
            time = arguments.get("time", "all")
            limit = min(int(arguments.get("limit", 10)), 25)
            
            search_scope = f"r/{subreddit}" if subreddit else "all of Reddit"
            logger.info(f"TOOL-{tool_id}: Searching {search_scope} for '{query}'")
            
            params = {
                "q": query,
                "sort": sort,
                "t": time,
                "limit": str(limit)
            }
            
            endpoint = f"/r/{subreddit}/search" if subreddit else "/search"
            data = await fetch_reddit_data(endpoint, params)
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No results found for search query '{query}'")
                return [types.TextContent(
                    type="text",
                    text="Error: Search failed or returned no results."
                )]
            
            results = [format_post(post) for post in data["data"]["children"]]
            
            result = {
                "query": query,
                "subreddit": f"r/{subreddit}" if subreddit else "all of Reddit",
                "sort": sort,
                "time": time,
                "results": results
            }
            
            logger.info(f"TOOL-{tool_id}: Search returned {len(results)} results")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Get user profile
        elif name == "get_user_profile":
            username = arguments.get("username")
            sort = arguments.get("sort", "new")
            limit = min(int(arguments.get("limit", 10)), 25)
            
            logger.info(f"TOOL-{tool_id}: Getting profile for u/{username}")
            
            # Fetch user's profile data
            user_data = await fetch_reddit_data(f"/user/{username}/about")
            
            if not user_data.get("data"):
                logger.warning(f"TOOL-{tool_id}: User not found: u/{username}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find user u/{username}."
                )]
            
            # Fetch user's posts and comments
            user_content = await fetch_reddit_data(f"/user/{username}/{sort}", {
                "limit": str(limit)
            })
            
            content = []
            if user_content.get("data") and user_content["data"].get("children"):
                for item in user_content["data"]["children"]:
                    data = item.get("data", {})
                    # Determine if it's a post or comment
                    if data.get("title"):
                        # It's a post
                        content.append({
                            "type": "post",
                            "subreddit": data.get("subreddit_name_prefixed", ""),
                            "title": data.get("title", ""),
                            "url": f"https://www.reddit.com{data.get('permalink', '')}",
                            "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
                            "upvotes": data.get("ups", 0),
                        })
                    else:
                        # It's a comment
                        content.append({
                            "type": "comment",
                            "subreddit": data.get("subreddit_name_prefixed", ""),
                            "body": data.get("body", ""),
                            "url": f"https://www.reddit.com{data.get('permalink', '')}",
                            "created": datetime.fromtimestamp(data.get("created_utc", 0)).isoformat(),
                            "upvotes": data.get("ups", 0),
                        })
            
            profile = {
                "username": user_data["data"].get("name", ""),
                "karma": {
                    "post": user_data["data"].get("link_karma", 0),
                    "comment": user_data["data"].get("comment_karma", 0),
                    "total": user_data["data"].get("total_karma", 0),
                },
                "created": datetime.fromtimestamp(user_data["data"].get("created_utc", 0)).isoformat(),
                "is_mod": user_data["data"].get("is_mod", False),
                "has_verified_email": user_data["data"].get("has_verified_email", False),
                "content": content,
            }
            
            logger.info(f"TOOL-{tool_id}: Retrieved profile for u/{username} with {len(content)} content items")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(profile, indent=2)
            )]

        # Submit a new post
        elif name == "submit_post":
            # Requires authentication
            subreddit = arguments.get("subreddit")
            title = arguments.get("title")
            text = arguments.get("text", "")
            url = arguments.get("url", "")
            flair_id = arguments.get("flair_id", "")
            flair_text = arguments.get("flair_text", "")
            
            if not title:
                logger.warning(f"TOOL-{tool_id}: Post submission failed - missing title")
                return [types.TextContent(
                    type="text",
                    text="Error: Title is required for posting."
                )]
            
            # Determine submission kind
            kind = "self" if text and not url else "link"
            
            logger.info(f"TOOL-{tool_id}: Submitting {kind} post to r/{subreddit}: '{title}'")
            
            data = {
                "sr": subreddit,
                "title": title,
                "kind": kind,
            }
            
            if kind == "self":
                data["text"] = text
            elif kind == "link":
                data["url"] = url
            
            if flair_id:
                data["flair_id"] = flair_id
            if flair_text:
                data["flair_text"] = flair_text
            
            # Convert data to form format
            form_data = data
            
            response = await fetch_reddit_data(
                "/api/submit",
                authenticated=True,
                method="POST",
                data=form_data
            )
            
            if response.get("json") and response["json"].get("errors") and len(response["json"]["errors"]) > 0:
                error_msgs = response["json"]["errors"]
                logger.error(f"TOOL-{tool_id}: Post submission error: {error_msgs}")
                return [types.TextContent(
                    type="text",
                    text=f"Error posting: {error_msgs}"
                )]
            
            # Successful post should have URL in the response
            if response.get("json") and response["json"].get("data") and response["json"]["data"].get("url"):
                post_url = response["json"]["data"]["url"]
                post_id = response["json"]["data"].get("id", "unknown")
                logger.info(f"TOOL-{tool_id}: Successfully posted to r/{subreddit}, post ID: {post_id}")
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "post_url": post_url,
                        "id": post_id,
                        "name": response["json"]["data"].get("name", "unknown")
                    }, indent=2)
                )]
            
            logger.info(f"TOOL-{tool_id}: Post likely submitted, but no confirmation URL returned")
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": "Post appears to have been submitted, but no confirmation URL was returned."
                }, indent=2)
            )]

        # Submit a comment
        elif name == "submit_comment":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            text = arguments.get("text")
            
            if not thing_id or not text:
                logger.warning(f"TOOL-{tool_id}: Comment submission failed - missing thing_id or text")
                return [types.TextContent(
                    type="text",
                    text="Error: Both thing_id and text are required for commenting."
                )]
            
            logger.info(f"TOOL-{tool_id}: Submitting comment on {thing_id}")
            
            data = {
                "thing_id": thing_id,
                "text": text
            }
            
            response = await fetch_reddit_data(
                "/api/comment",
                authenticated=True,
                method="POST",
                data=data
            )
            
            if response.get("json") and response["json"].get("errors") and len(response["json"]["errors"]) > 0:
                error_msgs = response["json"]["errors"]
                logger.error(f"TOOL-{tool_id}: Comment submission error: {error_msgs}")
                return [types.TextContent(
                    type="text",
                    text=f"Error commenting: {error_msgs}"
                )]
            
            # Try to extract comment ID and permalink
            comment_data = None
            if response.get("json") and response["json"].get("data") and response["json"]["data"].get("things") and len(response["json"]["data"]["things"]) > 0:
                comment_data = response["json"]["data"]["things"][0].get("data", {})
            
            if comment_data and comment_data.get("id"):
                comment_id = comment_data.get("id")
                logger.info(f"TOOL-{tool_id}: Successfully posted comment ID: {comment_id}")
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "success",
                        "comment_id": comment_id,
                        "permalink": f"https://www.reddit.com{comment_data.get('permalink', '')}" if comment_data.get("permalink") else None
                    }, indent=2)
                )]
            
            logger.info(f"TOOL-{tool_id}: Comment likely submitted, but no confirmation data returned")
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": "Comment appears to have been submitted."
                }, indent=2)
            )]

        # Vote on a post or comment
        elif name == "vote":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            direction = arguments.get("direction")
            
            if not thing_id or direction not in [1, 0, -1]:
                logger.warning(f"TOOL-{tool_id}: Vote failed - invalid thing_id or direction")
                return [types.TextContent(
                    type="text",
                    text="Error: Both thing_id and a valid direction (1, 0, or -1) are required for voting."
                )]
            
            vote_type = "up" if direction == 1 else "down" if direction == -1 else "removed"
            logger.info(f"TOOL-{tool_id}: Casting {vote_type} vote on {thing_id}")
            
            data = {
                "id": thing_id,
                "dir": str(direction)
            }
            
            response = await fetch_reddit_data(
                "/api/vote",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Vote {vote_type} successfully cast on {thing_id}")
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Vote {vote_type} on {thing_id}"
                }, indent=2)
            )]

        # Get subreddit rules
        elif name == "get_subreddit_rules":
            subreddit = arguments.get("subreddit")
            
            if not subreddit:
                logger.warning(f"TOOL-{tool_id}: Get rules failed - missing subreddit name")
                return [types.TextContent(
                    type="text",
                    text="Error: Subreddit name is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Getting rules for r/{subreddit}")
            
            data = await fetch_reddit_data(f"/r/{subreddit}/about/rules")
            
            if not data.get("rules"):
                logger.warning(f"TOOL-{tool_id}: No rules found for r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't fetch rules for r/{subreddit} or subreddit does not exist."
                )]
            
            rules = []
            for rule in data.get("rules", []):
                rules.append({
                    "priority": rule.get("priority"),
                    "short_name": rule.get("short_name"),
                    "description": rule.get("description"),
                    "violation_reason": rule.get("violation_reason")
                })
            
            result = {
                "subreddit": f"r/{subreddit}",
                "rules": rules,
            }
            
            if data.get("site_rules"):
                result["site_rules"] = data["site_rules"]
            
            logger.info(f"TOOL-{tool_id}: Retrieved {len(rules)} rules for r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Get request statistics
        elif name == "get_request_stats":
            limit = min(int(arguments.get("limit", 10)), 100)
            
            logger.info(f"TOOL-{tool_id}: Getting recent request statistics, limit: {limit}")
            
            # Get most recent requests
            recent_requests = request_history[-limit:] if request_history else []
            
            # Calculate some statistics
            total_requests = len(request_history)
            avg_time = 0
            status_counts = {}
            method_counts = {}
            
            if recent_requests:
                # Calculate average response time
                avg_time = sum(r.get("elapsed_time", 0) for r in recent_requests) / len(recent_requests)
                
                # Count status codes
                for r in recent_requests:
                    status = r.get("status", 0)
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    method = r.get("method", "")
                    method_counts[method] = method_counts.get(method, 0) + 1
            
            stats = {
                "total_requests": total_requests,
                "average_response_time": f"{avg_time:.2f}s",
                "status_codes": status_counts,
                "methods": method_counts,
                "recent_requests": recent_requests
            }
            
            logger.info(f"TOOL-{tool_id}: Returning stats for {len(recent_requests)} recent requests")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(stats, indent=2)
            )]
            
        # ================== NEW TOOLS ==================
        # Subreddit Info tools
        elif name == "get_subreddit_info":
            subreddit = arguments.get("subreddit")
            
            if not subreddit:
                logger.warning(f"TOOL-{tool_id}: Get subreddit info failed - missing subreddit name")
                return [types.TextContent(
                    type="text",
                    text="Error: Subreddit name is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Getting info for r/{subreddit}")
            
            data = await fetch_reddit_data(f"/r/{subreddit}/about")
            
            if not data.get("data"):
                logger.warning(f"TOOL-{tool_id}: Subreddit not found: r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find subreddit r/{subreddit}."
                )]
            
            subreddit_info = format_subreddit(data)
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved info for r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(subreddit_info, indent=2)
            )]
        
        elif name == "get_trending_subreddits":
            logger.info(f"TOOL-{tool_id}: Getting trending subreddits")
            
            data = await fetch_reddit_data("/trending_subreddits")
            
            if not data.get("subreddit_names"):
                logger.warning(f"TOOL-{tool_id}: No trending subreddits found")
                return [types.TextContent(
                    type="text",
                    text="Error: Couldn't retrieve trending subreddits."
                )]
            
            trending = {
                "trending_subreddits": data.get("subreddit_names", []),
                "trending_timestamp": data.get("comment", "")
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(trending['trending_subreddits'])} trending subreddits")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(trending, indent=2)
            )]
        
        elif name == "get_subreddit_moderators":
            subreddit = arguments.get("subreddit")
            
            if not subreddit:
                logger.warning(f"TOOL-{tool_id}: Get moderators failed - missing subreddit name")
                return [types.TextContent(
                    type="text",
                    text="Error: Subreddit name is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Getting moderators for r/{subreddit}")
            
            data = await fetch_reddit_data(f"/r/{subreddit}/about/moderators")
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No moderators found for r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't retrieve moderators for r/{subreddit}."
                )]
            
            moderators = []
            for mod in data["data"]["children"]:
                moderators.append({
                    "name": mod.get("name", ""),
                    "author_flair_text": mod.get("author_flair_text", ""),
                    "mod_permissions": mod.get("mod_permissions", []),
                    "date": datetime.fromtimestamp(mod.get("date", 0)).isoformat() if mod.get("date") else None
                })
            
            result = {
                "subreddit": f"r/{subreddit}",
                "moderators": moderators
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(moderators)} moderators for r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Content Management tools
        elif name == "save_content":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            
            if not thing_id:
                logger.warning(f"TOOL-{tool_id}: Save content failed - missing thing_id")
                return [types.TextContent(
                    type="text",
                    text="Error: thing_id is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Saving content with ID {thing_id}")
            
            data = {
                "id": thing_id
            }
            
            response = await fetch_reddit_data(
                "/api/save",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully saved content with ID {thing_id}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Content with ID {thing_id} has been saved."
                }, indent=2)
            )]
        
        elif name == "unsave_content":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            
            if not thing_id:
                logger.warning(f"TOOL-{tool_id}: Unsave content failed - missing thing_id")
                return [types.TextContent(
                    type="text",
                    text="Error: thing_id is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Unsaving content with ID {thing_id}")
            
            data = {
                "id": thing_id
            }
            
            response = await fetch_reddit_data(
                "/api/unsave",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully unsaved content with ID {thing_id}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Content with ID {thing_id} has been unsaved."
                }, indent=2)
            )]
        
        elif name == "get_saved_content":
            # Requires authentication
            limit = min(int(arguments.get("limit", 25)), 100)
            
            logger.info(f"TOOL-{tool_id}: Getting saved content, limit: {limit}")
            
            data = await fetch_reddit_data(
                f"/user/{REDDIT_USERNAME}/saved",
                params={"limit": str(limit)},
                authenticated=True
            )
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No saved content found")
                return [types.TextContent(
                    type="text",
                    text="No saved content found."
                )]
            
            saved_items = []
            for item in data["data"]["children"]:
                kind = item.get("kind", "")
                if kind == "t3":  # Post
                    saved_items.append(format_post(item))
                elif kind == "t1":  # Comment
                    saved_items.append(format_comment(item))
            
            result = {
                "count": len(saved_items),
                "items": saved_items
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(saved_items)} saved items")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "edit_content":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            text = arguments.get("text")
            
            if not thing_id or not text:
                logger.warning(f"TOOL-{tool_id}: Edit content failed - missing thing_id or text")
                return [types.TextContent(
                    type="text",
                    text="Error: Both thing_id and text are required for editing."
                )]
            
            logger.info(f"TOOL-{tool_id}: Editing content with ID {thing_id}")
            
            data = {
                "thing_id": thing_id,
                "text": text
            }
            
            response = await fetch_reddit_data(
                "/api/editusertext",
                authenticated=True,
                method="POST",
                data=data
            )
            
            if response.get("json") and response["json"].get("errors") and len(response["json"]["errors"]) > 0:
                error_msgs = response["json"]["errors"]
                logger.error(f"TOOL-{tool_id}: Content editing error: {error_msgs}")
                return [types.TextContent(
                    type="text",
                    text=f"Error editing content: {error_msgs}"
                )]
            
            logger.info(f"TOOL-{tool_id}: Successfully edited content with ID {thing_id}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Content with ID {thing_id} has been edited."
                }, indent=2)
            )]
        
        elif name == "delete_content":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            
            if not thing_id:
                logger.warning(f"TOOL-{tool_id}: Delete content failed - missing thing_id")
                return [types.TextContent(
                    type="text",
                    text="Error: thing_id is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Deleting content with ID {thing_id}")
            
            data = {
                "id": thing_id
            }
            
            response = await fetch_reddit_data(
                "/api/del",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully deleted content with ID {thing_id}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Content with ID {thing_id} has been deleted."
                }, indent=2)
            )]
        
        # Subreddit subscription management
        elif name == "subscribe_to_subreddit":
            # Requires authentication
            subreddit = arguments.get("subreddit")
            
            if not subreddit:
                logger.warning(f"TOOL-{tool_id}: Subscribe failed - missing subreddit")
                return [types.TextContent(
                    type="text",
                    text="Error: Subreddit name is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Subscribing to r/{subreddit}")
            
            # First, get the subreddit ID
            subreddit_data = await fetch_reddit_data(f"/r/{subreddit}/about")
            
            if not subreddit_data.get("data") or not subreddit_data["data"].get("name"):
                logger.warning(f"TOOL-{tool_id}: Subreddit not found: r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find subreddit r/{subreddit}."
                )]
            
            subreddit_fullname = subreddit_data["data"]["name"]
            
            # Now subscribe
            data = {
                "action": "sub",
                "sr": subreddit_fullname
            }
            
            response = await fetch_reddit_data(
                "/api/subscribe",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully subscribed to r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Successfully subscribed to r/{subreddit}"
                }, indent=2)
            )]
        
        elif name == "unsubscribe_from_subreddit":
            # Requires authentication
            subreddit = arguments.get("subreddit")
            
            if not subreddit:
                logger.warning(f"TOOL-{tool_id}: Unsubscribe failed - missing subreddit")
                return [types.TextContent(
                    type="text",
                    text="Error: Subreddit name is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Unsubscribing from r/{subreddit}")
            
            # First, get the subreddit ID
            subreddit_data = await fetch_reddit_data(f"/r/{subreddit}/about")
            
            if not subreddit_data.get("data") or not subreddit_data["data"].get("name"):
                logger.warning(f"TOOL-{tool_id}: Subreddit not found: r/{subreddit}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: Couldn't find subreddit r/{subreddit}."
                )]
            
            subreddit_fullname = subreddit_data["data"]["name"]
            
            # Now unsubscribe
            data = {
                "action": "unsub",
                "sr": subreddit_fullname
            }
            
            response = await fetch_reddit_data(
                "/api/subscribe",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully unsubscribed from r/{subreddit}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Successfully unsubscribed from r/{subreddit}"
                }, indent=2)
            )]
        
        elif name == "get_subscribed_subreddits":
            # Requires authentication
            limit = min(int(arguments.get("limit", 100)), 100)
            
            logger.info(f"TOOL-{tool_id}: Getting subscribed subreddits, limit: {limit}")
            
            data = await fetch_reddit_data(
                "/subreddits/mine/subscriber",
                params={"limit": str(limit)},
                authenticated=True
            )
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No subscribed subreddits found")
                return [types.TextContent(
                    type="text",
                    text="No subscribed subreddits found."
                )]
            
            subreddits = [format_subreddit(subreddit) for subreddit in data["data"]["children"]]
            
            result = {
                "count": len(subreddits),
                "subreddits": subreddits
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(subreddits)} subscribed subreddits")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # User profile management
        elif name == "get_user_trophies":
            username = arguments.get("username")
            
            if not username:
                logger.warning(f"TOOL-{tool_id}: Get trophies failed - missing username")
                return [types.TextContent(
                    type="text",
                    text="Error: Username is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Getting trophies for u/{username}")
            
            data = await fetch_reddit_data(f"/user/{username}/trophies")
            
            if not data.get("data") or not data["data"].get("trophies"):
                logger.warning(f"TOOL-{tool_id}: No trophies found for u/{username}")
                return [types.TextContent(
                    type="text",
                    text=f"No trophies found for u/{username}."
                )]
            
            trophies = []
            for trophy in data["data"]["trophies"]:
                if trophy.get("data"):
                    trophy_data = trophy["data"]
                    trophies.append({
                        "name": trophy_data.get("name", ""),
                        "description": trophy_data.get("description", ""),
                        "award_id": trophy_data.get("award_id", ""),
                        "granted_at": datetime.fromtimestamp(trophy_data.get("granted_at", 0)).isoformat() if trophy_data.get("granted_at") else None
                    })
            
            result = {
                "username": username,
                "trophy_count": len(trophies),
                "trophies": trophies
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(trophies)} trophies for u/{username}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "edit_user_profile":
            # Requires authentication
            about = arguments.get("about", "")
            display_name = arguments.get("display_name", "")
            
            if not about and not display_name:
                logger.warning(f"TOOL-{tool_id}: Edit profile failed - no data provided")
                return [types.TextContent(
                    type="text",
                    text="Error: At least one field (about or display_name) is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Editing user profile")
            
            data = {}
            if about:
                data["about"] = about
            if display_name:
                data["display_name"] = display_name
            
            response = await fetch_reddit_data(
                "/api/v1/me/prefs",
                authenticated=True,
                method="PATCH",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully edited user profile")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": "User profile has been updated."
                }, indent=2)
            )]
        
        # Messages and notifications
        elif name == "get_notifications":
            # Requires authentication
            filter_type = arguments.get("filter", "all")
            limit = min(int(arguments.get("limit", 25)), 100)
            
            endpoint = "/message/inbox"
            if filter_type == "unread":
                endpoint = "/message/unread"
            elif filter_type == "messages":
                endpoint = "/message/messages"
            elif filter_type == "comments":
                endpoint = "/message/comments"
            elif filter_type == "posts":
                endpoint = "/message/selfreply"
            elif filter_type == "mentions":
                endpoint = "/message/mentions"
            
            logger.info(f"TOOL-{tool_id}: Getting notifications with filter '{filter_type}', limit: {limit}")
            
            data = await fetch_reddit_data(
                endpoint,
                params={"limit": str(limit)},
                authenticated=True
            )
            
            if not data.get("data") or not data["data"].get("children"):
                logger.warning(f"TOOL-{tool_id}: No notifications found with filter '{filter_type}'")
                return [types.TextContent(
                    type="text",
                    text=f"No notifications found with filter '{filter_type}'."
                )]
            
            notifications = []
            for notification in data["data"]["children"]:
                if notification.get("data"):
                    notifications.append(format_notification(notification))
            
            result = {
                "filter": filter_type,
                "count": len(notifications),
                "notifications": notifications
            }
            
            logger.info(f"TOOL-{tool_id}: Successfully retrieved {len(notifications)} notifications")
            
            return [types.TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        elif name == "mark_notifications_read":
            # Requires authentication
            thing_ids = arguments.get("thing_ids", [])
            
            if not thing_ids or not isinstance(thing_ids, list) or len(thing_ids) == 0:
                logger.warning(f"TOOL-{tool_id}: Mark read failed - no thing_ids provided")
                return [types.TextContent(
                    type="text",
                    text="Error: At least one thing_id is required."
                )]
            
            logger.info(f"TOOL-{tool_id}: Marking {len(thing_ids)} notifications as read")
            
            data = {
                "id": ",".join(thing_ids)
            }
            
            response = await fetch_reddit_data(
                "/api/read_message",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully marked {len(thing_ids)} notifications as read")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Marked {len(thing_ids)} notifications as read."
                }, indent=2)
            )]
        
        elif name == "send_private_message":
            # Requires authentication
            to = arguments.get("to")
            subject = arguments.get("subject")
            text = arguments.get("text")
            
            if not to or not subject or not text:
                logger.warning(f"TOOL-{tool_id}: Send message failed - missing required fields")
                return [types.TextContent(
                    type="text",
                    text="Error: 'to', 'subject', and 'text' are all required fields."
                )]
            
            logger.info(f"TOOL-{tool_id}: Sending message to u/{to}")
            
            data = {
                "to": to,
                "subject": subject,
                "text": text
            }
            
            response = await fetch_reddit_data(
                "/api/compose",
                authenticated=True,
                method="POST",
                data=data
            )
            
            if response.get("json") and response["json"].get("errors") and len(response["json"]["errors"]) > 0:
                error_msgs = response["json"]["errors"]
                logger.error(f"TOOL-{tool_id}: Message sending error: {error_msgs}")
                return [types.TextContent(
                    type="text",
                    text=f"Error sending message: {error_msgs}"
                )]
            
            logger.info(f"TOOL-{tool_id}: Successfully sent message to u/{to}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Message sent to u/{to}"
                }, indent=2)
            )]
        
        # Moderation and reporting
        elif name == "report_content":
            # Requires authentication
            thing_id = arguments.get("thing_id")
            reason = arguments.get("reason")
            
            if not thing_id or not reason:
                logger.warning(f"TOOL-{tool_id}: Report content failed - missing thing_id or reason")
                return [types.TextContent(
                    type="text",
                    text="Error: Both thing_id and reason are required for reporting."
                )]
            
            logger.info(f"TOOL-{tool_id}: Reporting content with ID {thing_id}")
            
            data = {
                "thing_id": thing_id,
                "reason": reason
            }
            
            response = await fetch_reddit_data(
                "/api/report",
                authenticated=True,
                method="POST",
                data=data
            )
            
            logger.info(f"TOOL-{tool_id}: Successfully reported content with ID {thing_id}")
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": f"Content with ID {thing_id} has been reported."
                }, indent=2)
            )]
        
        # If we reach here, the tool wasn't recognized
        logger.error(f"TOOL-{tool_id}: Unknown tool '{name}'")
        return [types.TextContent(
            type="text",
            text=f"Error: Unknown tool '{name}'."
        )]
        
    except Exception as e:
        logger.exception(f"TOOL-{tool_id}: Error executing tool '{name}': {str(e)}")
        return [types.TextContent(
            type="text",
            text=f"Error executing tool '{name}': {str(e)}"
        )]

async def main():
    """Run the MCP server."""
    logger.info("Starting Enhanced Reddit MCP Server")
    
    # Log environment setup
    env_vars = {
        "REDDIT_CLIENT_ID": REDDIT_CLIENT_ID,
        "REDDIT_USERNAME": REDDIT_USERNAME,
        "REDDIT_CLIENT_SECRET": "***" if REDDIT_CLIENT_SECRET else None,
        "REDDIT_PASSWORD": "***" if REDDIT_PASSWORD else None
    }
    logger.info(f"Environment configuration: {env_vars}")
    
    # Using stdio for transport
    try:
        async with stdio_server() as streams:
            stdin, stdout = streams
            logger.info("MCP server initialized, waiting for requests")
            await app.run(
                stdin,
                stdout,
                app.create_initialization_options()
            )
    except Exception as e:
        logger.exception(f"Error in MCP server: {str(e)}")
    finally:
        logger.info("MCP server shutting down")

if __name__ == "__main__":
    asyncio.run(main())