# Reddit Bot Multi-Account System

This document explains how the refactored Reddit bot system supports multiple Reddit accounts from a central Supabase configuration.

## Overview

The Reddit Bot Multi-Account System allows running multiple Reddit bots from a single codebase, with each bot having its own:

- Reddit credentials (client_id, secret, refresh_token)
- Post discovery keywords and fixed subreddit list
- Custom Groq prompt and tone parameters
- Per-run activity limits (max replies, upvotes, subreddits)

## Architecture

1. **Supabase Database**: Central storage for all bot configurations
2. **Bot Runner**: CLI tool that loads configuration from Supabase based on bot_id
3. **GitHub Actions**: Matrix workflow that runs each bot in parallel

## Setup Instructions

### 1. Supabase Setup

1. Create a free Supabase account at [supabase.com](https://supabase.com)
2. Create a new project
3. Run the SQL script in `supabase_setup.sql` in the SQL Editor
4. Replace the example credentials with real Reddit API credentials
5. Get your Supabase URL and service role key from the API settings

### 2. GitHub Secrets

Add the following secrets to your GitHub repository:

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_KEY`: Your Supabase service role key (for read access)
- `GROQ_API_KEY`: Your Groq API key for AI responses

### 3. Local Development

Create a `.env` file with the following:

```
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
GROQ_API_KEY=your_groq_api_key
```

To run a specific bot locally:

```bash
# Using environment variable
BOT_ID=slime python bot_runner.py --dry-run

# Or using command line argument
python bot_runner.py --dry-run --bot-id truck1
```

## Bot Configuration Fields

| Field | Description | Default |
|-------|-------------|---------|
| `id` | Unique identifier for the bot | Required |
| `reddit_client_id` | Reddit API client ID | Required |
| `reddit_secret` | Reddit API client secret | Required |
| `reddit_refresh` | Reddit OAuth refresh token | Required |
| `user_agent` | User agent string for Reddit API | 'bot/1.0' |
| `keywords` | Array of keywords for subreddit discovery | [] |
| `fixed_subs` | Array of specific subreddits to use | [] |
| `groq_prompt` | Custom system prompt for Groq | Default in code |
| `max_replies` | Maximum replies per run | 3 |
| `max_upvotes` | Maximum upvotes per run | 6 |
| `max_subs` | Maximum subreddits per run | 3 |
| `active` | Whether the bot is active | true |

## How It Works

1. The GitHub Action runs a matrix job for each bot_id
2. Each job calls `bot_runner.py` with the appropriate `--bot-id`
3. The bot runner loads the configuration from Supabase
4. Environment variables are set from the configuration
5. The RedditBot class uses these variables for authentication
6. The bot discovers subreddits based on keywords or fixed_subs
7. The bot generates replies using the custom Groq prompt

## Subreddit Selection Logic

- If `fixed_subs` is provided, the bot will randomly select up to `max_subs` subreddits from this list
- Otherwise, it will discover subreddits based on the `keywords` list

## Adding a New Bot

1. Add a new row to the `reddit_bots` table in Supabase
2. Update the GitHub Actions workflow matrix to include the new bot_id
3. No code changes required!

## Troubleshooting

- If a bot fails to run, check the logs for error messages
- Ensure the bot is marked as `active = true` in Supabase
- Verify that the Reddit credentials are valid
- Check that the Supabase service key has the correct permissions
