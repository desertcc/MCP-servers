# Subreddit Rotation Feature

This document explains the new subreddit rotation feature added to the Reddit Automation Bot.

## Overview

The subreddit rotation feature ensures that:

1. Bots select random subreddits for each run
2. Bots avoid repeatedly commenting in the same subreddits within a short time window
3. All bots respect a global "do-not-comment" list of excluded subreddits

## Database Schema

Two new tables were added to Supabase:

### 1. `subreddit_history`

Tracks when each bot comments in a subreddit.

```sql
CREATE TABLE subreddit_history (
  bot_id           text,
  subreddit        text,
  last_commented_at timestamp DEFAULT now(),
  PRIMARY KEY (bot_id, subreddit)
);
```

### 2. `excluded_subreddits`

Global list of subreddits that all bots should avoid.

```sql
CREATE TABLE excluded_subreddits (
  subreddit        text PRIMARY KEY,
  reason           text,
  added_at         timestamp DEFAULT now()
);
```

## How It Works

### Subreddit Selection Process

1. **Gather Potential Subreddits**
   - Combines fixed subreddits from the bot's configuration
   - Discovers additional subreddits based on keywords if needed

2. **Apply Exclusion Filters**
   - Removes any subreddits in the global exclusion list
   - Removes subreddits the bot has commented in during the last 3 days

3. **Randomize Selection**
   - Shuffles the remaining subreddits
   - Selects a random sample up to the configured maximum

4. **Fallback Logic**
   - If not enough subreddits remain after filtering, includes some recently used ones
   - Still respects the global exclusion list

### Tracking Subreddit History

After a bot comments in a subreddit:
- Records the interaction in the `subreddit_history` table
- Updates the timestamp if an entry already exists

## Configuration

### Adding Excluded Subreddits

To add subreddits to the global exclusion list:

```sql
INSERT INTO excluded_subreddits (subreddit, reason) VALUES
('politics', 'Controversial topics'),
('news', 'Too much negativity');
```

### Testing Subreddit Selection

Use the test script to see which subreddits would be selected:

```bash
python test_subreddit_selection.py <bot_id> <max_subreddits>
```

Example:
```bash
python test_subreddit_selection.py slime 3
```

## Benefits

- **More Natural Behavior**: Bots don't repeatedly comment in the same subreddits
- **Reduced Risk**: Global exclusion list prevents commenting in problematic subreddits
- **Variety**: Randomization ensures diverse subreddit selection
- **Centralized Management**: Global exclusion list applies to all bots

## Implementation Details

The feature is implemented across several files:

- `supabase_loader.py`: Added functions to get excluded subreddits and track history
- `bot_runner.py`: Updated subreddit selection logic
- `supabase_migration.sql`: SQL script to add the new tables to your database

## Applying the Migration

To add these tables to your existing Supabase database:

1. Open the Supabase SQL Editor
2. Copy the contents of `supabase_migration.sql`
3. Run the SQL in your Supabase project

The migration uses `IF NOT EXISTS` and `ON CONFLICT DO NOTHING` to safely apply changes without affecting existing data.
