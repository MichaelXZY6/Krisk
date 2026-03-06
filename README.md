# 🤖 Krisk — A Multi-Purpose Discord Bot

Krisk is a feature-rich Discord bot built with Python and discord.py. It offers fun commands, utility tools, messaging features, moderation tools, and more.

[![Discord](https://img.shields.io/badge/Add%20to%20Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.com/oauth2/authorize?client_id=1390048921534861352)

---

## ✨ Features

- 🎭 **Fun Commands** — Memes, roasts, dice rolls, 8-ball, ratings, and ship calculator
- 🛠️ **Utility Tools** — Weather, reminders, translation (Google Translate), and user lookup
- 📨 **Messaging** — Send DMs through the bot, with anonymous messaging and reply forwarding
- 🔧 **Moderation** — Ban, kick, mute, purge, and announcements (admin only)
- 💡 **Feedback System** — Users can submit ideas and bug reports directly to the developer
- 🚫 **Block System** — Block users from using the bot entirely
- 📋 **Message Logging** — All messaging commands are logged for moderation purposes

---

## 📖 Commands

### 🎭 Fun

| Command | Description |
|---------|-------------|
| `/meme` | Get a random meme from Reddit |
| `/echo [message] [times]` | Repeat your message (1-5 times) |
| `/repeat [message]` | Repeat your message 5 times |
| `/roast [user]` | Roast someone 🔥 |
| `/roll [dice]` | Roll dice (e.g. `2d6`, `1d20`) |
| `/8ball [question]` | Ask the Magic 8-Ball |
| `/rate [thing] [user]` | Rate anything from 0-10 |
| `/ship [user1] [user2]` | Ship two users and see their compatibility 💘 |

### 🛠️ Utility

| Command | Description |
|---------|-------------|
| `/weather [city]` | Get current weather for a city |
| `/remind [minutes] [reminder]` | Set a reminder (1-1440 minutes) |
| `/translate [target] [text] [source]` | Translate text between languages (auto-detect source) |
| `/tell [user] [text] [image]` | Send a DM to someone (shows your name) |
| `/privatetell [user] [text] [image]` | Send an anonymous DM to someone |
| `/check [user] [user_id]` | Look up detailed info about any Discord user |
| `/idea [message]` | Submit feedback or report a bug to the developer |

### 🏓 Other

| Command | Description |
|---------|-------------|
| `/ping` | Check bot latency |
| `/about` | Show live bot stats and info |
| `/dad` | Find out who made the bot |
| `/help` | Show all available commands |

### 🔧 Admin Only

These commands are restricted to bot administrators.

| Command | Description |
|---------|-------------|
| `/ban [user] [reason] [days]` | Ban a user (0 = permanent, auto-unban after duration) |
| `/unban [user]` | Unban a user (with autocomplete for banned users) |
| `/kick [user] [reason]` | Kick a user from the server |
| `/mute [user] [minutes] [reason]` | Timeout a user (1-40320 minutes) |
| `/unmute [user]` | Remove timeout from a user |
| `/purge [amount]` | Delete multiple messages (1-100) |
| `/announce [channel] [title] [message]` | Send an announcement to a channel |
| `/announcement [user] [message]` | Send a developer announcement DM to a user |
| `/block [user]` | Block a user from using the bot |
| `/unblock [user]` | Unblock a user |
| `/logs [user_id] [amount]` | View message logs |
| `/reply [user] [message]` | Reply to user feedback |
| `/getinvite [server_id]` | Get an invite link for any server the bot is in |
| `/leave` | Make the bot leave the current server |

---

## 💬 Messaging System

Krisk has a built-in messaging system that allows users to communicate through the bot:

- **`/tell`** — Send a DM with your name visible. The recipient can reply by clicking Reply on the bot's message.
- **`/privatetell`** — Send an anonymous DM. Replies are also anonymous.
- **Reply Forwarding** — When someone replies to a bot-forwarded message, the reply is automatically forwarded back to the original sender.
- **Image Support** — All messaging commands support image attachments.
- **Message Logging** — All messages sent through the bot are logged with timestamps and user IDs for moderation.

---

## 🚀 Self-Hosting Guide

### Prerequisites

- Python 3.10 or higher
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- (Optional) OpenWeatherMap API key for `/weather` ([Get one here](https://openweathermap.org/api))

### Setup

1. **Clone the repository**

```bash
git clone https://github.com/MichaelXZY6/Krisk.git
cd Krisk
```

2. **Create a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

3. **Install dependencies**

```bash
pip install discord.py aiohttp python-dotenv certifi deep-translator
```

4. **Configure environment variables**

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your bot token:

```
DISCORD_TOKEN=your_bot_token_here
WEATHER_API_KEY=your_openweathermap_key_here
```

5. **Configure the bot**

Open `bot.py` and update these values:

```python
MY_GUILD = discord.Object(id=YOUR_GUILD_ID)  # Your main server ID
DAD_ID = YOUR_USER_ID                         # Bot owner's user ID
ADMIN_IDS = (DAD_ID, OTHER_ADMIN_ID)          # Admin user IDs
```

6. **Enable required intents**

Go to [Developer Portal](https://discord.com/developers/applications) → Your Bot → Bot tab → Enable:

- ✅ Message Content Intent
- ✅ Server Members Intent
- ✅ Presence Intent

7. **Run the bot**

```bash
python bot.py
```

You should see:

```
✅ Bot is online! Logged in as Krisk#3425 (ID: 1390048921534861352)
✅ Slash commands synced (guild + global)!
```

---

## 📁 File Structure

```
Krisk/
├── bot.py                  # Main bot code
├── .env                    # Bot token and API keys (not uploaded)
├── .env.example            # Example environment variables
├── .gitignore              # Files excluded from git
├── message_log.json        # Message logs (auto-created)
├── message_tracker.json    # Reply tracking data (auto-created)
├── feedback_tracker.json   # Feedback tracking data (auto-created)
├── blocked_users.json      # Blocked users list (auto-created)
└── README.md               # This file
```

---

## 🔒 Privacy & Security

- Bot token and API keys are stored in `.env` and never uploaded to GitHub
- Message logs are stored locally and only accessible by bot administrators
- Anonymous messages are logged with sender info for moderation purposes
- Blocked users cannot use any bot commands or DM the bot
- See [Privacy Policy](https://docs.google.com/document/d/YOUR_PRIVACY_POLICY_ID) for full details

---

## 📝 Terms of Service

By using Krisk, you agree to our [Terms of Service](https://docs.google.com/document/d/YOUR_TOS_ID).

---

## 🤝 Contributing

Found a bug or have a feature idea? Use `/idea` in Discord to submit feedback, or open an issue on GitHub.

---

## 📜 License

This project is open source. Feel free to fork and modify for your own use.

---

## 💖 Credits

Made with love by **Michael**

Built with:
- [discord.py](https://github.com/Rapptz/discord.py)
- [deep-translator](https://github.com/nidhaloff/deep-translator)
- [OpenWeatherMap API](https://openweathermap.org/)
- [Meme API](https://github.com/D3vd/Meme_Api)
