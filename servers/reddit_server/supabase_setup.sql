/* 
Supabase test setup for Reddit Bot Multi-Account Configuration
Run this in the Supabase SQL Editor to set up the required table 
*/

-- Create the reddit_bots table
CREATE TABLE reddit_bots (
  id               text PRIMARY KEY,          -- e.g. 'slime', 'truck1'
  reddit_client_id text NOT NULL,
  reddit_secret    text NOT NULL,
  reddit_refresh   text NOT NULL,
  user_agent       text DEFAULT 'bot/1.0',
  keywords         text[],                    -- PostgreSQL array, e.g. '{slime, crafts}'
  fixed_subs       text[],                    -- optional curated sub list
  groq_prompt      text,                      -- custom system prompt
  bot_type         text DEFAULT 'general',    -- 'logistics', 'slime', 'general', etc.
  max_replies      int   DEFAULT 3,
  max_upvotes      int   DEFAULT 6,
  max_subs         int   DEFAULT 3,
  active           bool  DEFAULT true
);

-- Create a table to track subreddit interaction history
CREATE TABLE subreddit_history (
  bot_id           text,
  subreddit        text,
  last_commented_at timestamp DEFAULT now(),
  PRIMARY KEY (bot_id, subreddit)
);

-- Create a global table for excluded subreddits (opt-out list)
CREATE TABLE excluded_subreddits (
  subreddit        text PRIMARY KEY,          -- subreddit name to exclude
  reason           text,                      -- optional reason for exclusion
  added_at         timestamp DEFAULT now()    -- when it was added to the exclusion list
);

-- Optional: Create a runs_log table for tracking quota usage (stretch goal)
CREATE TABLE runs_log (
  id               SERIAL PRIMARY KEY,
  bot_id           text REFERENCES reddit_bots(id),
  run_date         timestamp DEFAULT CURRENT_TIMESTAMP,
  replies_made     int DEFAULT 0,
  upvotes_made     int DEFAULT 0,
  subreddits_used  text[],
  success          bool DEFAULT true,
  error_message    text
);

-- Example data for excluded subreddits
INSERT INTO excluded_subreddits (subreddit, reason) VALUES
('politics', 'Controversial topics'),
('news', 'Too much negativity'),
('worldnews', 'Too much negativity'),
('conspiracy', 'Controversial topics'),
('unpopularopinion', 'Controversial topics');

-- Example data for testing (DO NOT USE IN PRODUCTION - REPLACE WITH REAL CREDENTIALS)
INSERT INTO reddit_bots (id, reddit_client_id, reddit_secret, reddit_refresh, user_agent, keywords, fixed_subs, groq_prompt, bot_type, max_replies, max_upvotes, max_subs, active) VALUES 
(
  'slime', 
  'your_client_id_for_slime', 
  'your_client_secret_for_slime', 
  'your_refresh_token_for_slime', 
  'windows:bot:slime:1.0', 
  ARRAY['slime', 'crafts', 'kids', 'parenting', 'home', 'toys'], 
  ARRAY[
    'slime', 'crafts', 'DIY', 'crafting', 'kidscrafts', 'slimevideos', 
    'satisfyingslime', 'oddlysatisfying', 'asmr', 'slimeasmr', 
    'parenting', 'mommit', 'daddit', 'family', 'toddlers', 
    'homeimprovement', 'organization', 'declutter', 'cleaningtips', 'homehacks'
  ], 
  'You are a POSITIVE and SUPPORTIVE Reddit commenter who loves slime crafts. Keep replies super brief (1-2 sentences, max 25 words). Your replies MUST be warm, encouraging, and helpful - never confused, dismissive, or negative.', 
  'slime', 
  3, 
  6, 
  3, 
  true
),
(
  'truck1', 
  'your_client_id_for_truck1', 
  'your_client_secret_for_truck1', 
  'your_refresh_token_for_truck1', 
  'windows:bot:truck1:1.0', 
  ARRAY['trucks', 'vehicles', 'mechanics', 'automotive', 'offroad'], 
  NULL, 
  'You are a POSITIVE and SUPPORTIVE Reddit commenter who loves trucks and vehicles. Keep replies super brief (1-2 sentences, max 25 words). Your replies MUST be warm, encouraging, and helpful - never confused, dismissive, or negative.', 
  'logistics', 
  2, 
  4, 
  2, 
  true
),
(
  'truck2', 
  'your_client_id_for_truck2', 
  'your_client_secret_for_truck2', 
  'your_refresh_token_for_truck2', 
  'windows:bot:truck2:1.0', 
  ARRAY['trucks', 'trucking', 'logistics', 'transportation'], 
  ARRAY[
    'trucking', 'logistics', 'transportation', 'trucks', 'bigrig', 
    'cdl', 'truckers', 'freightbrokers', 'supplychain', 'logistics', 
    'shipping', 'truckersmp', 'trucksim', 'americantruck', 'eurotruck', 
    'diesel', 'mechanicadvice', 'truckmaintenance', 'trucking_jobs', 'truckdrivers'
  ], 
  'You are a POSITIVE and SUPPORTIVE Reddit commenter who works in the trucking industry. Keep replies super brief (1-2 sentences, max 25 words). Your replies MUST be warm, encouraging, and helpful - never confused, dismissive, or negative.', 
  'logistics', 
  2, 
  4, 
  3, 
  true
);

-- Create a row-level security policy to restrict access
ALTER TABLE reddit_bots ENABLE ROW LEVEL SECURITY;

-- Policy for the service role to read all bots
CREATE POLICY "Service can read all bots" 
  ON reddit_bots FOR SELECT 
  USING (auth.role() = 'service_role');

-- Policy for the service role to insert/update/delete bots
CREATE POLICY "Service can modify all bots" 
  ON reddit_bots FOR ALL 
  USING (auth.role() = 'service_role');

-- Enable RLS on the runs_log table too
ALTER TABLE runs_log ENABLE ROW LEVEL SECURITY;

-- Policy for the service role to read/write to runs_log
CREATE POLICY "Service can read/write runs_log" 
  ON runs_log FOR ALL 
  USING (auth.role() = 'service_role');
