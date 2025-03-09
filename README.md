# MCP Games Server

A Multi-Channel Platform (MCP) for game-related API integrations and tools. This project provides a unified way to interact with various gaming and community platforms through standardized interfaces.

## Overview

MCP Games Server is a collection of server implementations that follow the MCP (Multi-Channel Platform) protocol, allowing for standardized interaction with different online platforms and APIs. The servers can be used independently or together to create powerful gaming and community tools.

## Current Implementations

### Reddit MCP Server

A comprehensive server for interacting with Reddit's API, offering tools for browsing, searching, and interacting with Reddit content. See the [Reddit Server README](/servers/reddit_server/README.md) for detailed information.

**Features:**
- Browse and search subreddits
- Get post details with comments
- Search Reddit for specific content
- View user profiles
- Create posts and comments
- Vote on content
- Access subreddit rules

## Project Structure

```
mcp_games_server/
├── servers/             # Server implementations
│   └── reddit_server/   # Reddit API server implementation
│       ├── reddit_mcp.py       # Main server code
│       ├── requirements.txt    # Dependencies
│       ├── test_reddit_mcp.py  # Test suite
│       └── testreddit.py       # Mock test utilities
└── .gitignore           # Git ignore configuration
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- API credentials for the platforms you want to use (e.g., Reddit API credentials)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/mcp_games_server.git
   cd mcp_games_server
   ```

2. Choose the server implementation you want to use and install its dependencies:
   ```bash
   cd servers/reddit_server
   pip install -r requirements.txt
   ```

3. Configure API credentials:
   Create a `.env` file in the server directory with the required credentials. See the specific server's README for details.

4. Run the server:
   ```bash
   python reddit_mcp.py
   ```

## Using an MCP Server

MCP servers expose a standardized interface for interacting with different platforms. You can use them in your applications by:

1. Connecting to the server
2. Requesting available tools
3. Calling the desired tools with appropriate parameters

For specific usage patterns, refer to the README of each server implementation.

## Development

### Adding a New Server

To add a new platform integration:

1. Create a new directory under `servers/` for your implementation
2. Implement the MCP server protocol
3. Add appropriate documentation in a README.md file
4. Include tests and requirements

## License

This project is licensed under the MIT License.

## Acknowledgements

- The MCP protocol developers
- Platform API teams for their documentation and services
- Contributors to the various libraries used in this project
