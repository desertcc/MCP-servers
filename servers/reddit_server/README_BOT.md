# Reddit MCP Automation Bot

A Reddit bot that automatically discovers and interacts with subreddits about slime, crafts, kids, parenting, home, and toys. The bot uses Groq's LLM API to generate friendly, helpful replies to posts and upvotes positive content.

## Features

- **Dynamic Subreddit Discovery**: Automatically finds relevant subreddits based on keywords
- **Intelligent Engagement**: Uses Groq LLM to generate contextually appropriate, positive replies
- **Content Curation**: Upvotes helpful comments and posts
- **Rate Limit Compliance**: Respects Reddit's API rate limits with built-in delays
- **Comprehensive Logging**: Tracks all interactions for review and analysis
- **Dry Run Mode**: Test functionality without posting actual comments

## Requirements

- Python 3.8+
- Reddit API credentials
- Groq API key

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/desertcc/MCP-servers.git
   cd MCP-servers/servers/reddit_server
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the `reddit_server` directory
   - Add the following variables:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USERNAME=your_username
   REDDIT_PASSWORD=your_password
   REDDIT_USER_AGENT=slime_bot/1.0
   GROQ_API_KEY=your_groq_api_key
   ```

## Usage

### Running the Bot Directly

To run the bot as a standalone application:

```
python bot_runner.py
```

For a dry run (no actual posting):

```
python bot_runner.py --dry-run
```

### Using the MCP Server

The bot is integrated with the MCP server architecture. To use it through the MCP server:

1. Start the MCP server:
   ```
   python reddit_mcp.py
   ```

2. Use the following MCP tools:
   - `discover_subreddits`: Find relevant subreddits
   - `reply_to_subreddit_posts`: Reply to posts in a specific subreddit
   - `run_bot`: Run the complete bot workflow
   - `get_interaction_log`: View the bot's interaction history

## Bot Workflow

1. **Discover Subreddits**: The bot searches for active subreddits related to keywords like "slime", "crafts", "kids", etc.
2. **Process Posts**: For each subreddit, the bot retrieves recent posts from the "rising" or "new" sections.
3. **Generate Replies**: The bot uses Groq's LLM to create friendly, helpful replies to relevant posts.
4. **Post Engagement**: The bot posts replies and upvotes the original post.
5. **Comment Engagement**: The bot upvotes 2-3 top comments on each post.
6. **Logging**: All interactions are logged with timestamps and details.

## Customization

You can customize the bot's behavior by modifying the following constants in `bot_runner.py`:

- `KEYWORDS`: List of keywords for subreddit discovery
- `MAX_POSTS_PER_SUBREDDIT`: Number of posts to process per subreddit
- `MAX_COMMENTS_TO_UPVOTE`: Number of comments to upvote per post
- `SLEEP_BETWEEN_ACTIONS`: Delay between actions to respect rate limits

## Logs

Logs are stored in the `logs` directory:
- Daily runtime logs: `reddit_bot_YYYYMMDD.log`
- Interaction history: `interaction_log.json`

## Safety and Compliance

This bot is designed to be a positive contributor to Reddit communities. It:
- Focuses on family-friendly content
- Maintains a positive, helpful tone
- Avoids controversial topics
- Respects Reddit's rate limits and API terms of service
- Does not engage in spammy behavior

## License

This project is licensed under the MIT License.
