import ssl
import certifi
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

import discord
from discord import app_commands
import asyncio
import random
import aiohttp
import os
import time
import platform
import datetime
import json
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
MY_GUILD = discord.Object(id=1477707527549485118)
DAD_ID = 1259348548722495608
ADMIN_IDS = (DAD_ID, 1263681901244448838)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
start_time = time.time()
rigged_ship = {}

# ── Message tracking (file-backed) ──────────────────
TRACKER_FILE = "message_tracker.json"

def load_tracker():
    try:
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_tracker():
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump(message_tracker, f)
    except Exception:
        pass

message_tracker = load_tracker()

# ── Feedback tracking (file-backed) ─────────────────
FEEDBACK_FILE = "feedback_tracker.json"

def load_feedback():
    try:
        with open(FEEDBACK_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_feedback():
    try:
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(feedback_tracker, f)
    except Exception:
        pass

feedback_tracker = load_feedback()

# ── Block list (file-backed) ────────────────────────
BLOCK_FILE = "blocked_users.json"

def load_blocked():
    try:
        with open(BLOCK_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_blocked():
    try:
        with open(BLOCK_FILE, "w") as f:
            json.dump(blocked_users, f)
    except Exception:
        pass

blocked_users = load_blocked()

# ── Message logging ──────────────────────────────────
LOG_FILE = "message_log.json"

def log_message(sender, recipient, text, msg_type, image_url=None):
    entry = {
        "time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "type": msg_type,
        "sender_id": sender.id,
        "sender_name": sender.name,
        "recipient_id": recipient.id,
        "recipient_name": recipient.name,
        "text": text,
    }
    if image_url:
        entry["image"] = image_url
    try:
        with open(LOG_FILE, "r") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []
    logs.append(entry)
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ── Helpers ──────────────────────────────────────────

def is_dad(interaction: discord.Interaction) -> bool:
    return interaction.user.id in ADMIN_IDS

async def block_check(interaction: discord.Interaction) -> bool:
    if interaction.user.id in blocked_users:
        await interaction.response.send_message("🚫 You have been blocked by Krisk.", ephemeral=True)
        return False
    return True

# ── Data ─────────────────────────────────────────────
ROASTS = [
    "Your code looks like spaghetti 🍝",
    "Even Google can't find a reason to like you 🔍",
    "You're the human version of a 404 error 💀",
    "Your WiFi personality is worse than 2G 📶",
    "You're proof that evolution can go backwards 🐒",
    "GPT refuses to roleplay as you 🤖",
    "Your existence is a loading screen that never ends ⏳",
    "You bring everyone so much joy... when you leave 👋",
    "I'd roast you, but my mom said I'm not allowed to burn trash 🗑️",
    "You're not stupid, you just have bad luck thinking 🧠",
    "If laziness was a sport, you'd still come second 🥈",
    "You're like a cloud — when you disappear, it's a beautiful day ☀️",
    "I've seen better comebacks in a dead-end street 🛣️",
    "Your vibe is just... off. Like Bluetooth that won't connect 📵",
    "You're the reason the gene pool needs a lifeguard 🏊",
]

COMPLIMENTS = [
    "You're literally the best person ever 👑",
    "Your vibe is immaculate, king 🔥",
    "Everyone wishes they were you 💯",
    "You make the sun jealous with how bright you shine ☀️",
    "Even AI can't find a single flaw in you 🤖",
    "You're too powerful to be roasted 🛡️",
    "The world doesn't deserve you 🌍",
    "Legends aren't born every day, but you were 🏆",
    "If perfection had a face, it'd be yours 😎",
    "You're the reason the word 'goat' exists 🐐",
]

EIGHT_BALL = [
    "✅ Absolutely yes!", "✅ Without a doubt!", "✅ Looking good!",
    "🤔 Hard to say...", "🤔 Ask again later", "🤔 Not sure about that",
    "❌ Definitely not", "❌ My sources say no", "❌ Don't count on it",
]

LANG_CHOICES = [
    app_commands.Choice(name="Auto Detect", value="auto"),
    app_commands.Choice(name="English", value="en"),
    app_commands.Choice(name="Chinese", value="zh-CN"),
    app_commands.Choice(name="Spanish", value="es"),
    app_commands.Choice(name="French", value="fr"),
    app_commands.Choice(name="Japanese", value="ja"),
    app_commands.Choice(name="Korean", value="ko"),
    app_commands.Choice(name="German", value="de"),
    app_commands.Choice(name="Italian", value="it"),
    app_commands.Choice(name="Russian", value="ru"),
    app_commands.Choice(name="Arabic", value="ar"),
]


# ════════════════════════════════════════════════════
#  Events
# ════════════════════════════════════════════════════

@client.event
async def on_guild_join(guild):
    target = guild.owner
    if target:
        try:
            embed = discord.Embed(
                title=f"🤖 Thanks for adding {client.user.name}!",
                description="Made with 💖 by Michael",
                color=0x5865F2,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            embed.set_thumbnail(url=client.user.display_avatar.url)
            embed.add_field(name="Get Started", value="Type `/help` to see all commands!", inline=False)
            embed.add_field(name="Features", value="🎭 Fun commands\n🛠️ Utility tools\n🌐 Translation\n📨 DM messaging\n💘 Ship calculator", inline=False)
            embed.add_field(name="Feedback", value="Use `/idea` to send feedback or report bugs!", inline=False)
            embed.set_footer(text="Use /help for the full command list")
            await target.send(embed=embed)
        except Exception:
            pass
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            try:
                embed = discord.Embed(
                    title=f"👋 Hey! I'm {client.user.name}!",
                    description="Thanks for adding me! Type `/help` to see what I can do.",
                    color=0x5865F2,
                )
                embed.set_thumbnail(url=client.user.display_avatar.url)
                await channel.send(embed=embed)
            except Exception:
                pass
            break

@client.event
async def on_ready():
    tree.copy_global_to(guild=MY_GUILD)
    await tree.sync(guild=MY_GUILD)
    await tree.sync()
    print(f"✅ Bot is online! Logged in as {client.user} (ID: {client.user.id})")
    print("✅ Slash commands synced (guild + global)!")
    await client.change_presence(activity=discord.Game("/help for commands"))

@client.event
async def on_message(message):
    if message.author.bot:
        return

    global rigged_ship

    # :setship command (admin only, hidden)
    if message.content.startswith(":setship") and message.author.id in ADMIN_IDS:
        try:
            val = int(message.content.split()[1])
            if 0 <= val <= 100:
                key = str(message.guild.id) if message.guild else str(message.channel.id)
                rigged_ship[key] = val
            await message.delete()
        except Exception:
            await message.delete()
        return

    # Block check
    if message.author.id in blocked_users:
        if isinstance(message.channel, discord.DMChannel):
            await message.channel.send("🚫 You have been blocked by Krisk.")
        return

    # Developer replying to feedback
    if isinstance(message.channel, discord.DMChannel) and message.reference and message.author.id in ADMIN_IDS:
        ref_id = str(message.reference.message_id)
        if ref_id in feedback_tracker:
            info = feedback_tracker[ref_id]
            try:
                target = await client.fetch_user(info["user_id"])
                embed = discord.Embed(title="💬 Developer Reply", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
                embed.add_field(name="Your Feedback", value=info["message"][:200], inline=False)
                embed.add_field(name="Reply", value=message.content, inline=False)
                embed.set_footer(text="Reply from Krisk Developer")
                await target.send(embed=embed)
                await message.add_reaction("✅")
            except Exception:
                await message.add_reaction("❌")
            return

    # DM help
    if isinstance(message.channel, discord.DMChannel) and not message.reference:
        embed = discord.Embed(
            title="Hey there! I'm Krisk 👋",
            description="I work with **slash commands**! Type `/` to see what I can do.",
            color=0x5865F2,
        )
        embed.add_field(
            name="💡 How to reply to forwarded messages",
            value="If someone sent you a message through me, just **click on my message** and hit **Reply** to send a response back!",
            inline=False,
        )
        embed.add_field(name="📖 Commands", value="Type `/help` to see all available commands.", inline=False)
        await message.channel.send(embed=embed)
        return

    # Reply forwarding
    if message.reference and message.reference.message_id:
        ref_id = message.reference.message_id
        if str(ref_id) in message_tracker:
            info = message_tracker[str(ref_id)]
            sender_id = info["sender_id"]
            anonymous = info["anonymous"]
            try:
                sender = await client.fetch_user(sender_id)
            except discord.NotFound:
                return
            try:
                if anonymous:
                    header = "💬 Someone replied to your anonymous message:"
                else:
                    header = f"💬 Reply from **{message.author.display_name}** ({message.author.name}):"
                content = header
                if message.content:
                    content += f"\n\n{message.content}"
                if message.attachments:
                    content += "\n" + "\n".join(a.url for a in message.attachments)
                if message.stickers:
                    for sticker in message.stickers:
                        content += f"\n{sticker.url}"
                content += "\n\n💡 *Reply to this message to chat back!*"
                bot_msg = await sender.send(content)
                message_tracker[str(bot_msg.id)] = {"sender_id": message.author.id, "anonymous": anonymous}
                save_tracker()
                log_message(message.author, sender, message.content or "[attachment]", "reply_anon" if anonymous else "reply")
                await message.add_reaction("✅")
            except discord.Forbidden:
                await message.add_reaction("❌")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message("🚫 You have been blocked by Krisk.", ephemeral=True)
    else:
        raise error


# ════════════════════════════════════════════════════
#  /help
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="help", description="Show all bot commands")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Bot Commands", description="Use `/` slash commands", color=0x5865F2)
    embed.add_field(name="🎭 Fun", value=(
        "`/meme` — Random meme from Reddit\n"
        "`/echo` — Repeat your message\n"
        "`/repeat` — Repeat your message 5 times\n"
        "`/roast` — Roast someone 🔥\n"
        "`/roll` — Roll dice (e.g. 2d6)\n"
        "`/8ball` — Magic 8-Ball\n"
        "`/rate` — Rate anything 0-10\n"
        "`/ship` — Ship two users 💘"
    ), inline=False)
    embed.add_field(name="🛠️ Utility", value=(
        "`/weather` — Get weather\n"
        "`/remind` — Set a reminder\n"
        "`/translate` — Translate between languages\n"
        "`/tell` — Send a DM (shows your name)\n"
        "`/privatetell` — Send an anonymous DM\n"
        "`/check` — Look up user info\n"
        "`/idea` — Submit feedback or report a bug"
    ), inline=False)
    embed.add_field(name="🏓 Other", value=(
        "`/ping` — Check bot latency\n"
        "`/about` — Bot stats & info\n"
        "`/dad` — Find out who made me"
    ), inline=False)
    await interaction.response.send_message(embed=embed)


# ════════════════════════════════════════════════════
#  /meme
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="meme", description="Get a random meme from Reddit")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as resp:
            if resp.status == 200:
                data = await resp.json()
                embed = discord.Embed(title=data["title"], color=0xFF6B6B)
                embed.set_image(url=data["url"])
                embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("😢 Failed to fetch a meme, try again!")


# ════════════════════════════════════════════════════
#  /echo
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="echo", description="Repeat your message")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(message="The message to repeat", times="How many times (1-5)")
async def echo(interaction: discord.Interaction, message: str, times: int = 1):
    times = max(1, min(times, 5))
    await interaction.response.send_message(message)
    for _ in range(times - 1):
        try:
            await interaction.channel.send(message)
        except discord.Forbidden:
            await interaction.followup.send(message)


# ════════════════════════════════════════════════════
#  /spam
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="repeat", description="Repeat your message 5 times")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(message="The message to spam", image="Optional image to include")
async def spam(interaction: discord.Interaction, message: str, image: discord.Attachment = None):
    content = f"{message}\n{image.url}" if image else message
    await interaction.response.send_message(content)
    for i in range(4):
        await interaction.followup.send(content)
        if i < 3:
            await asyncio.sleep(0.5)


# ════════════════════════════════════════════════════
#  /roast
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="roast", description="Roast someone 🔥")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(member="Who to roast")
async def roast(interaction: discord.Interaction, member: discord.User = None):
    target = member or interaction.user
    if target.id == DAD_ID:
        await interaction.response.send_message(f"🎯 {target.mention}, {random.choice(COMPLIMENTS)}")
        return
    await interaction.response.send_message(f"🎯 {target.mention}, {random.choice(ROASTS)}")


# ════════════════════════════════════════════════════
#  /roll
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="roll", description="Roll dice (e.g. 2d6)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(dice="Dice format like 2d6 or 1d20")
async def roll(interaction: discord.Interaction, dice: str = "1d6"):
    try:
        num, sides = dice.lower().split("d")
        num = int(num) if num else 1
        sides = int(sides)
        if num < 1 or num > 20 or sides < 2:
            raise ValueError
    except ValueError:
        await interaction.response.send_message("⚠️ Invalid format! Use something like `2d6` or `1d20`")
        return
    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls)
    if len(rolls) > 1:
        roll_str = " + ".join(str(r) for r in rolls)
        result = f"🎲 **{roll_str}** = **{total}**"
    else:
        result = f"🎲 Rolled: **{total}**"
    await interaction.response.send_message(result)


# ════════════════════════════════════════════════════
#  /8ball
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="8ball", description="Ask the Magic 8-Ball a question")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(question="Your question")
async def eight_ball(interaction: discord.Interaction, question: str):
    answer = random.choice(EIGHT_BALL)
    await interaction.response.send_message(f"🎱 *{question}*\n→ **{answer}**")


# ════════════════════════════════════════════════════
#  /rate
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="rate", description="Rate anything from 0 to 10")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(thing="What to rate", user="Rate a user instead", note="Add a note")
async def rate(interaction: discord.Interaction, thing: str = None, user: discord.User = None, note: str = None):
    if not thing and not user:
        await interaction.response.send_message("⚠️ Give me something or someone to rate!")
        return
    if user and user.id == DAD_ID:
        bars = "█" * 20 + "🔥"
        await interaction.response.send_message(f"⭐ I rate {user.mention} a **1,000,000,000,000/10**\n{bars}")
        return
    target = user.mention if user else f"**{thing}**"
    score = None
    if note and interaction.user.id in ADMIN_IDS:
        try:
            score = int(note)
        except ValueError:
            pass
    if score is None:
        score = random.randint(0, 10)
    if score > 10:
        bars = "█" * 20 + "💥"
    elif score < 0:
        bars = "💀" * min(abs(score), 20)
    else:
        bars = "█" * score + "░" * (10 - score)
    await interaction.response.send_message(f"⭐ I rate {target} a **{score:,}/10**\n{bars}")
# ════════════════════════════════════════════════════
#  /ship
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="ship", description="Ship two users and see their compatibility")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
@app_commands.describe(user1="First user", user2="Second user (random if not set)", note="Add a note")
async def ship(interaction: discord.Interaction, user1: discord.User, user2: discord.User = None, note: str = None):
    global rigged_ship
    if not user2:
        if interaction.guild:
            members = [m for m in interaction.guild.members if not m.bot and m.id != user1.id]
            if not members:
                await interaction.response.send_message("Not enough users in this server.", ephemeral=True)
                return
            user2 = random.choice(members)
        else:
            await interaction.response.send_message("Please specify a second user in group chats.", ephemeral=True)
            return
    score = None
    key = str(interaction.guild_id) if interaction.guild_id else str(interaction.channel_id)
    if key in rigged_ship:
        score = rigged_ship.pop(key)
    if score is None and note and interaction.user.id in ADMIN_IDS:
        try:
            val = int(note)
            if 0 <= val <= 100:
                score = val
        except ValueError:
            pass
    if score is None:
        score = random.randint(0, 100)
    filled = score // 10
    empty = 10 - filled
    bar = "❤️" * filled + "🖤" * empty
    if score >= 90:
        comment = "Soulmates! 💍"
    elif score >= 70:
        comment = "Great match! 💕"
    elif score >= 50:
        comment = "There's something there... 👀"
    elif score >= 30:
        comment = "Maybe as friends? 😅"
    elif score >= 10:
        comment = "Yikes... awkward 😬"
    else:
        comment = "Absolutely not 💀"
    embed = discord.Embed(title="💘 Ship Calculator", description=f"**{user1.display_name}** x **{user2.display_name}**", color=0xFF69B4)
    embed.add_field(name="Compatibility", value=f"**{score}%**\n{bar}", inline=False)
    embed.add_field(name="Verdict", value=comment, inline=False)
    embed.set_thumbnail(url=user1.display_avatar.url)
    await interaction.response.send_message(embed=embed)


# ════════════════════════════════════════════════════
#  /weather
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="weather", description="Get weather for a city")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(city="City name")
async def weather(interaction: discord.Interaction, city: str):
    if not WEATHER_API_KEY:
        await interaction.response.send_message("⚠️ No weather API key configured.")
        return
    await interaction.response.defer()
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await interaction.followup.send(f"😢 Couldn't find city **{city}**.")
                return
            data = await resp.json()
    desc = data["weather"][0]["description"].capitalize()
    temp = data["main"]["temp"]
    feels = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    embed = discord.Embed(title=f"🌍 Weather in {data['name']}", color=0x87CEEB)
    embed.add_field(name="Condition", value=desc, inline=True)
    embed.add_field(name="Temperature", value=f"{temp}°C (feels like {feels}°C)", inline=True)
    embed.add_field(name="Humidity", value=f"{humidity}%", inline=True)
    await interaction.followup.send(embed=embed)


# ════════════════════════════════════════════════════
#  /remind
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="remind", description="Set a reminder")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(minutes="Minutes (1-1440)", reminder="What to remind you about")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    if minutes < 1 or minutes > 1440:
        await interaction.response.send_message("⚠️ Please set between 1 and 1440 minutes.")
        return
    await interaction.response.send_message(f"⏰ Got it! I'll remind you in **{minutes} minute(s)**: *{reminder}*")
    await asyncio.sleep(minutes * 60)
    try:
        await interaction.channel.send(f"⏰ {interaction.user.mention} Reminder: **{reminder}**")
    except discord.Forbidden:
        try:
            await interaction.user.send(f"⏰ Reminder: **{reminder}**")
        except discord.Forbidden:
            pass


# ════════════════════════════════════════════════════
#  /translate
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="translate", description="Translate text between languages")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(target="Target language", text="Text to translate", source="Source language (auto-detect if not set)")
@app_commands.choices(source=LANG_CHOICES, target=LANG_CHOICES)
async def translate(interaction: discord.Interaction, target: app_commands.Choice[str], text: str, source: app_commands.Choice[str] = None):
    src_val = source.value if source else "auto"
    src_name = source.name if source else "Auto Detect"
    if source and source.value == target.value:
        await interaction.response.send_message("⚠️ Source and target language can't be the same!")
        return
    await interaction.response.defer()
    try:
        result = GoogleTranslator(source=src_val, target=target.value).translate(text)
        embed = discord.Embed(title="🌐 Translation", color=0x2ECC71)
        embed.add_field(name=f"Original ({src_name})", value=text, inline=False)
        embed.add_field(name=f"→ {target.name}", value=result, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception:
        await interaction.followup.send("😢 Translation failed, try again!")


# ════════════════════════════════════════════════════
#  /tell
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="tell", description="Send a DM to someone (shows your name)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to message", text="Message to send", image="Optional image to include")
async def tell(interaction: discord.Interaction, user: discord.User, text: str, image: discord.Attachment = None):
    try:
        content = f"📨 Message from **{interaction.user.display_name}** ({interaction.user.name}):\n\n{text}"
        if image:
            content += f"\n{image.url}"
        content += "\n\n💡 *Reply to this message to chat back!*"
        bot_msg = await user.send(content)
        message_tracker[str(bot_msg.id)] = {"sender_id": interaction.user.id, "anonymous": False}
        save_tracker()
        log_message(interaction.user, user, text, "tell", image.url if image else None)
        await interaction.response.send_message(f"✅ Message sent to **{user.display_name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Can't DM that user. They may have DMs disabled.", ephemeral=True)


# ════════════════════════════════════════════════════
#  /privatetell
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="privatetell", description="Send an anonymous DM to someone")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to message", text="Message to send", image="Optional image to include")
async def privatetell(interaction: discord.Interaction, user: discord.User, text: str, image: discord.Attachment = None):
    try:
        content = f"🕵️ Anonymous message:\n\n{text}"
        if image:
            content += f"\n{image.url}"
        content += "\n\n💡 *Reply to this message to chat back (your name will be hidden too)!*"
        bot_msg = await user.send(content)
        message_tracker[str(bot_msg.id)] = {"sender_id": interaction.user.id, "anonymous": True}
        save_tracker()
        log_message(interaction.user, user, text, "privatetell", image.url if image else None)
        await interaction.response.send_message(f"✅ Anonymous message sent to **{user.display_name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Can't DM that user. They may have DMs disabled.", ephemeral=True)


# ════════════════════════════════════════════════════
#  /ping
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="ping", description="Check bot latency")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    latency = round(client.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: **{latency}ms**")


# ════════════════════════════════════════════════════
#  /about
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="about", description="Show bot stats and info")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def about(interaction: discord.Interaction):
    uptime_seconds = int(time.time() - start_time)
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{days}d " if days else ""
    uptime_str += f"{hours}h {minutes}m {seconds}s"
    total_members = sum(g.member_count or 0 for g in client.guilds)
    total_channels = sum(len(g.channels) for g in client.guilds)
    text_channels = sum(len(g.text_channels) for g in client.guilds)
    voice_channels = sum(len(g.voice_channels) for g in client.guilds)
    embed = discord.Embed(title=f"🤖 {client.user.name}", description="Made with 💖 by Michael", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.set_thumbnail(url=client.user.display_avatar.url)
    embed.add_field(name="Servers", value=f"{len(client.guilds)}", inline=True)
    embed.add_field(name="Members", value=f"{total_members:,}", inline=True)
    embed.add_field(name="Channels", value=f"{total_channels:,} total\n{text_channels:,} text\n{voice_channels:,} voice", inline=True)
    embed.add_field(name="Latency", value=f"{round(client.latency * 1000)}ms", inline=True)
    embed.add_field(name="Uptime", value=uptime_str, inline=True)
    embed.add_field(name="Python", value=platform.python_version(), inline=True)
    embed.add_field(name="discord.py", value=discord.__version__, inline=True)
    embed.set_footer(text="Stats are live • Use /help to see all commands")
    await interaction.response.send_message(embed=embed)


# ════════════════════════════════════════════════════
#  /dad
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="dad", description="Find out who made me")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def dad(interaction: discord.Interaction):
    await interaction.response.send_message("My dad is **Michael** 👨")


# ════════════════════════════════════════════════════
#  /check
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="check", description="Look up detailed info about a user")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Select a user", user_id="Or enter a user ID")
async def check(interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
    if not user and not user_id:
        await interaction.response.send_message("Please provide a user or user ID.", ephemeral=True)
        return
    await interaction.response.defer()
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except (discord.NotFound, ValueError):
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    try:
        user = await client.fetch_user(user.id)
    except Exception:
        pass
    created = user.created_at.strftime("%Y-%m-%d %H:%M UTC")
    days_ago = (datetime.datetime.now(datetime.timezone.utc) - user.created_at).days
    embed = discord.Embed(title=f"{user.display_name}", color=user.accent_color or 0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
    embed.set_thumbnail(url=user.display_avatar.url)
    if user.banner:
        embed.set_image(url=user.banner.url)
    embed.add_field(name="Username", value=user.name, inline=True)
    embed.add_field(name="Display Name", value=user.display_name or "None", inline=True)
    embed.add_field(name="ID", value=str(user.id), inline=True)
    embed.add_field(name="Created", value=f"{created}\n({days_ago} days ago)", inline=True)
    embed.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
    badges = []
    flags = user.public_flags
    if flags.staff: badges.append("Discord Staff")
    if flags.partner: badges.append("Partner")
    if flags.hypesquad: badges.append("HypeSquad Events")
    if flags.hypesquad_bravery: badges.append("HypeSquad Bravery")
    if flags.hypesquad_brilliance: badges.append("HypeSquad Brilliance")
    if flags.hypesquad_balance: badges.append("HypeSquad Balance")
    if flags.bug_hunter: badges.append("Bug Hunter")
    if flags.bug_hunter_level_2: badges.append("Bug Hunter Lv2")
    if flags.early_supporter: badges.append("Early Supporter")
    if flags.verified_bot_developer: badges.append("Verified Bot Dev")
    if flags.active_developer: badges.append("Active Developer")
    if flags.discord_certified_moderator: badges.append("Certified Mod")
    embed.add_field(name="Badges", value=", ".join(badges) if badges else "None", inline=False)
    status_found = False
    for g in client.guilds:
        m = g.get_member(user.id)
        if m:
            status_map = {"online": "🟢 Online", "idle": "🌙 Idle", "dnd": "⛔ Do Not Disturb", "offline": "⚫ Offline"}
            embed.add_field(name="Status", value=status_map.get(str(m.status), str(m.status)), inline=True)
            if m.activities:
                act_lines = []
                for act in m.activities:
                    if isinstance(act, discord.CustomActivity):
                        emoji = str(act.emoji) + " " if act.emoji else ""
                        act_lines.append(f"{emoji}{act.name or ''}")
                    elif isinstance(act, discord.Spotify):
                        act_lines.append(f"🎵 Listening to **{act.title}** by {act.artist}")
                    elif isinstance(act, discord.Game):
                        act_lines.append(f"🎮 Playing **{act.name}**")
                    elif isinstance(act, discord.Streaming):
                        act_lines.append(f"📺 Streaming **{act.name}**")
                    elif isinstance(act, discord.Activity):
                        act_lines.append(f"{act.name}")
                if act_lines:
                    embed.add_field(name="Activity", value="\n".join(act_lines), inline=True)
            status_found = True
            break
    if not status_found:
        embed.add_field(name="Status", value="Unknown (no shared server)", inline=True)
    if interaction.guild:
        member = interaction.guild.get_member(user.id)
        if member:
            joined = member.joined_at.strftime("%Y-%m-%d %H:%M UTC") if member.joined_at else "Unknown"
            join_days = (datetime.datetime.now(datetime.timezone.utc) - member.joined_at).days if member.joined_at else 0
            roles = [r.mention for r in member.roles if r.name != "@everyone"]
            embed.add_field(name="Joined Server", value=f"{joined}\n({join_days} days ago)", inline=True)
            embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
            embed.add_field(name="Top Role", value=member.top_role.mention if member.top_role.name != "@everyone" else "None", inline=True)
            embed.add_field(name="Roles", value=" ".join(roles[:20]) if roles else "None", inline=False)
            if member.premium_since:
                embed.add_field(name="Boosting Since", value=member.premium_since.strftime("%Y-%m-%d"), inline=True)
            if member.timed_out_until:
                embed.add_field(name="Timed Out Until", value=member.timed_out_until.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    avatar_links = f"[Default]({user.display_avatar.url})"
    if user.avatar:
        avatar_links += f" | [User Avatar]({user.avatar.url})"
    if interaction.guild:
        member = interaction.guild.get_member(user.id)
        if member and member.guild_avatar:
            avatar_links += f" | [Server Avatar]({member.guild_avatar.url})"
    embed.add_field(name="Avatar Links", value=avatar_links, inline=False)
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.followup.send(embed=embed)


# ════════════════════════════════════════════════════
#  /idea
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="idea", description="Submit feedback or report a bug to the bot developer")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(message="Your idea, feedback, or bug report")
async def idea(interaction: discord.Interaction, message: str):
    dad = await client.fetch_user(DAD_ID)
    try:
        embed = discord.Embed(title="💡 New Feedback", color=0xFFD700, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="From", value=f"**{interaction.user.display_name}** ({interaction.user.name})\n`{interaction.user.id}`", inline=True)
        embed.add_field(name="Server", value=interaction.guild.name if interaction.guild else "DM", inline=True)
        embed.add_field(name="Message", value=message, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        bot_msg = await dad.send(embed=embed)
        feedback_tracker[str(bot_msg.id)] = {"user_id": interaction.user.id, "user_name": interaction.user.name, "message": message}
        save_feedback()
        await interaction.response.send_message("✅ Thanks for your feedback! It has been sent to the developer.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("❌ Could not send feedback. Try again later.", ephemeral=True)


# ════════════════════════════════════════════════════
#  /reply (Admin only)
# ════════════════════════════════════════════════════

@tree.command(name="reply", description="Reply to a user feedback (Admin only)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User to reply to", message="Your reply")
async def reply_feedback(interaction: discord.Interaction, user: discord.User, message: str):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    try:
        embed = discord.Embed(title="💬 Developer Reply", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="Message", value=message, inline=False)
        embed.set_footer(text="Reply from Krisk Developer")
        await user.send(embed=embed)
        await interaction.response.send_message(f"✅ Reply sent to **{user.name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot DM that user.", ephemeral=True)


# ════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ════════════════════════════════════════════════════

# ── /ban ─────────────────────────────────────────────

@tree.command(name="ban", description="Ban a user from the server")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User to ban", reason="Reason for ban", days="Ban duration in days (0 = permanent)")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided", days: int = 0):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    try:
        await interaction.guild.ban(user, reason=f"{reason} | Banned by {interaction.user.name}")
        try:
            notify = discord.Embed(title="🔨 You have been banned", color=0xFF0000)
            notify.add_field(name="Server", value=interaction.guild.name, inline=True)
            notify.add_field(name="Reason", value=reason, inline=True)
            if days > 0:
                unban_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
                notify.add_field(name="Duration", value=f"{days} day(s)\nUnban: {unban_date.strftime('%Y-%m-%d %H:%M UTC')}", inline=True)
            else:
                notify.add_field(name="Duration", value="Permanent", inline=True)
            await user.send(embed=notify)
        except Exception:
            pass
        confirm = discord.Embed(title="🔨 User Banned", color=0xFF0000)
        confirm.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
        confirm.add_field(name="Reason", value=reason, inline=True)
        confirm.add_field(name="Duration", value=f"{days} day(s)" if days > 0 else "Permanent", inline=True)
        await interaction.response.send_message(embed=confirm)
        if days > 0:
            await asyncio.sleep(days * 86400)
            try:
                await interaction.guild.unban(user, reason="Ban duration expired")
            except Exception:
                pass
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to ban this user.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


# ── /unban ───────────────────────────────────────────

async def unban_autocomplete(interaction: discord.Interaction, current: str):
    if not interaction.guild:
        return []
    try:
        banned = [entry async for entry in interaction.guild.bans()]
        return [app_commands.Choice(name=f"{e.user.name} ({e.user.id})", value=str(e.user.id)) for e in banned if current.lower() in e.user.name.lower() or current in str(e.user.id)][:25]
    except Exception:
        return []

@tree.command(name="unban", description="Unban a user from the server")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="Username or ID to unban (leave empty to see ban list)")
@app_commands.autocomplete(user=unban_autocomplete)
async def unban(interaction: discord.Interaction, user: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    await interaction.response.defer()
    banned_list = [entry async for entry in interaction.guild.bans()]
    if not banned_list:
        await interaction.followup.send("📋 No banned users found.")
        return
    if not user:
        bl = "\n".join(f"• **{e.user.name}** (ID: {e.user.id}) — {e.reason or 'No reason'}" for e in banned_list[:20])
        embed = discord.Embed(title="📋 Banned Users", description=bl, color=0xFF6B6B)
        embed.set_footer(text="Use /unban [username or ID] to unban someone")
        await interaction.followup.send(embed=embed)
        return
    target = None
    for ban_entry in banned_list:
        if user.lower() in ban_entry.user.name.lower() or user == str(ban_entry.user.id):
            target = ban_entry.user
            break
    if target:
        await interaction.guild.unban(target, reason=f"Unbanned by {interaction.user.name}")
        try:
            invite = await interaction.channel.create_invite(max_age=86400, max_uses=1, reason="Unban invite")
            embed = discord.Embed(title="🎉 You have been unbanned!", color=0x2ECC71)
            embed.add_field(name="Server", value=interaction.guild.name, inline=True)
            embed.add_field(name="Rejoin", value=f"[Click here to rejoin]({invite.url})", inline=True)
            await target.send(embed=embed)
            await interaction.followup.send(f"✅ **{target.name}** has been unbanned and notified!")
        except discord.Forbidden:
            await interaction.followup.send(f"✅ **{target.name}** has been unbanned! (Could not DM them)")
    else:
        bl = "\n".join(f"• **{e.user.name}** (ID: {e.user.id}) — {e.reason or 'No reason'}" for e in banned_list[:20])
        embed = discord.Embed(title="📋 Banned Users", description=bl, color=0xFF6B6B)
        await interaction.followup.send(f"⚠️ User **{user}** not found.", embed=embed)


# ── /kick ────────────────────────────────────────────

@tree.command(name="kick", description="Kick a user from the server")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    try:
        await user.kick(reason=f"{reason} | Kicked by {interaction.user.name}")
        try:
            notify = discord.Embed(title="👢 You have been kicked", color=0xFFA500)
            notify.add_field(name="Server", value=interaction.guild.name, inline=True)
            notify.add_field(name="Reason", value=reason, inline=True)
            await user.send(embed=notify)
        except Exception:
            pass
        confirm = discord.Embed(title="👢 User Kicked", color=0xFFA500)
        confirm.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
        confirm.add_field(name="Reason", value=reason, inline=True)
        await interaction.response.send_message(embed=confirm)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to kick this user.", ephemeral=True)


# ── /mute ────────────────────────────────────────────

@tree.command(name="mute", description="Timeout a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User to mute", minutes="Duration in minutes (1-40320)", reason="Reason for mute")
async def mute(interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    if minutes < 1 or minutes > 40320:
        await interaction.response.send_message("⚠️ Duration must be between 1 and 40320 minutes.", ephemeral=True)
        return
    try:
        await user.timeout(datetime.timedelta(minutes=minutes), reason=f"{reason} | Muted by {interaction.user.name}")
        confirm = discord.Embed(title="🔇 User Muted", color=0x808080)
        confirm.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
        confirm.add_field(name="Duration", value=f"{minutes} minute(s)", inline=True)
        confirm.add_field(name="Reason", value=reason, inline=True)
        await interaction.response.send_message(embed=confirm)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to mute this user.", ephemeral=True)


# ── /unmute ──────────────────────────────────────────

@tree.command(name="unmute", description="Remove timeout from a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User to unmute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    try:
        await user.timeout(None, reason=f"Unmuted by {interaction.user.name}")
        await interaction.response.send_message(f"🔊 **{user.display_name}** has been unmuted!")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to unmute this user.", ephemeral=True)


# ── /purge ───────────────────────────────────────────

@tree.command(name="purge", description="Delete multiple messages")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(amount="Number of messages to delete (1-100)")
async def purge(interaction: discord.Interaction, amount: int = 10):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    if amount < 1 or amount > 100:
        await interaction.response.send_message("⚠️ Amount must be between 1 and 100.", ephemeral=True)
        return
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🗑️ Deleted **{len(deleted)}** messages!", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to delete messages.", ephemeral=True)


# ── /announce ────────────────────────────────────────

@tree.command(name="announce", description="Send an announcement to a channel")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(channel="Channel to send to", title="Announcement title", message="Announcement message")
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    try:
        embed = discord.Embed(title=f"📢 {title}", description=message, color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to send messages in that channel.", ephemeral=True)


# ── /announcement (Admin only, DM user) ─────────────

@tree.command(name="announcement", description="Send a developer announcement to a user")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User to send to", message="Announcement message")
async def announcement(interaction: discord.Interaction, user: discord.User, message: str):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        embed = discord.Embed(title="📢 Developer Announcement", description=message, color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_footer(text="From Krisk Developer Team")
        await user.send(embed=embed)
        await interaction.response.send_message(f"✅ Announcement sent to **{user.name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ Cannot DM that user.", ephemeral=True)


# ── /block ───────────────────────────────────────────

@tree.command(name="block", description="Block a user from using the bot")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User to block")
async def block(interaction: discord.Interaction, user: discord.User):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    if user.id in blocked_users:
        await interaction.response.send_message(f"⚠️ **{user.name}** is already blocked.", ephemeral=True)
        return
    blocked_users.append(user.id)
    save_blocked()
    await interaction.response.send_message(f"🚫 **{user.name}** (`{user.id}`) has been blocked.", ephemeral=True)


# ── /unblock ─────────────────────────────────────────

async def unblock_autocomplete(interaction: discord.Interaction, current: str):
    results = []
    for uid in blocked_users:
        try:
            u = await client.fetch_user(uid)
            name = f"{u.name} ({uid})"
        except Exception:
            name = f"Unknown ({uid})"
        if current.lower() in name.lower() or current in str(uid):
            results.append(app_commands.Choice(name=name, value=str(uid)))
    return results[:25]

@tree.command(name="unblock", description="Unblock a user from the bot")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User to unblock")
@app_commands.autocomplete(user=unblock_autocomplete)
async def unblock(interaction: discord.Interaction, user: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    if not user:
        if not blocked_users:
            await interaction.response.send_message("📋 No blocked users.", ephemeral=True)
            return
        lines = []
        for uid in blocked_users:
            try:
                u = await client.fetch_user(uid)
                lines.append(f"• **{u.name}** (`{uid}`)")
            except Exception:
                lines.append(f"• Unknown (`{uid}`)")
        embed = discord.Embed(title="🚫 Blocked Users", description="\n".join(lines), color=0xFF6B6B)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    uid = int(user)
    if uid not in blocked_users:
        await interaction.response.send_message("⚠️ That user is not blocked.", ephemeral=True)
        return
    blocked_users.remove(uid)
    save_blocked()
    try:
        u = await client.fetch_user(uid)
        name = u.name
    except Exception:
        name = str(uid)
    await interaction.response.send_message(f"✅ **{name}** has been unblocked.", ephemeral=True)


# ── /logs ────────────────────────────────────────────

@tree.command(name="logs", description="View message logs")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user_id="Filter by sender ID (optional)", amount="Number of recent logs (default 10)")
async def logs(interaction: discord.Interaction, user_id: str = None, amount: int = 10):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        with open(LOG_FILE, "r") as f:
            all_logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await interaction.response.send_message("No logs found.", ephemeral=True)
        return
    if user_id:
        all_logs = [l for l in all_logs if str(l["sender_id"]) == user_id]
    recent = all_logs[-amount:]
    if not recent:
        await interaction.response.send_message("No matching logs.", ephemeral=True)
        return
    lines = []
    for l in recent:
        tag = "🕵️" if l["type"] in ("privatetell", "reply_anon") else "📨"
        lines.append(f"{tag} `{l['time']}`\n**{l['sender_name']}** (`{l['sender_id']}`) → **{l['recipient_name']}** (`{l['recipient_id']}`)\n{l['text'][:100]}")
    desc = "\n\n".join(lines)
    if len(desc) > 4000:
        desc = desc[:4000] + "\n..."
    embed = discord.Embed(title="📋 Message Logs", description=desc, color=0x5865F2)
    embed.set_footer(text=f"Showing {len(recent)} of {len(all_logs)} logs")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /getinvite ───────────────────────────────────────

async def server_autocomplete(interaction: discord.Interaction, current: str):
    return [app_commands.Choice(name=f"{g.name} ({g.member_count} members)", value=str(g.id)) for g in client.guilds if current.lower() in g.name.lower() or current in str(g.id)][:25]

@tree.command(name="getinvite", description="Get an invite link for a server the bot is in")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(server_id="Server ID (leave empty to list all)")
@app_commands.autocomplete(server_id=server_autocomplete)
async def getinvite(interaction: discord.Interaction, server_id: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    if not server_id:
        sl = "\n".join(f"**{g.name}** — `{g.id}`" for g in client.guilds)
        embed = discord.Embed(title="Bot is in these servers", description=sl, color=0x5865F2)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    guild = client.get_guild(int(server_id))
    if not guild:
        await interaction.response.send_message("Bot is not in that server.", ephemeral=True)
        return
    try:
        channel = guild.text_channels[0]
        invite = await channel.create_invite(max_age=86400, max_uses=1, reason="Requested by bot owner")
        await interaction.response.send_message(f"**{guild.name}** invite:\n{invite.url}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Bot doesn't have permission to create invites.", ephemeral=True)


# ── /leave ───────────────────────────────────────────

@tree.command(name="leave", description="Make the bot leave the current server")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def leave(interaction: discord.Interaction):
    if not is_dad(interaction):
        await interaction.response.send_message("🚫 No permission.", ephemeral=True)
        return
    guild_name = interaction.guild.name
    await interaction.response.send_message(f"👋 Leaving **{guild_name}**... Goodbye!")
    await interaction.guild.leave()


# ════════════════════════════════════════════════════
#  Run
# ════════════════════════════════════════════════════

if __name__ == "__main__":
    client.run(TOKEN)
