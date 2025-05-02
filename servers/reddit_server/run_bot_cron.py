import time
import os
import subprocess

def run_bot():
    print("Running bot script...")
    subprocess.run([
        "python", "bot_runner.py",
        "--max-subreddits", "10",
        "--max-replies", "5",
        "--max-upvotes", "10"
    ])

while True:
    run_bot()
    print("Sleeping for 8 hours...")
    time.sleep(8 * 60 * 60)  # Run every 8 hours
