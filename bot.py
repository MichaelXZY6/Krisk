import ssl
import certifi
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

import discord
from discord import app_commands
from discord.ui import View, Button
import asyncio
import random
import aiohttp
import os
import time
import platform
import datetime
import json
import re
import base64
import io
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from deep_translator import GoogleTranslator

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_KEY_FREE = os.getenv("GEMINI_API_KEY_FREE")
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
coin_emoji = "<:MateoCoin:1479943773977837648>"
LOCAL_TZ = ZoneInfo("America/Toronto")
rigged_ship = {}
ai_cooldowns = {}
spam_tracker = {}
rob_cooldowns = {}
user_cache = {}  # display_name (username)
pending_transfers = {}
last_ranks = {}  # uid -> rank position  # msg_id -> {sender_id, receiver_id, amount, tax, time, note}
link_warnings = {}

# ── File-backed data ────────────────────────────────
TRACKER_FILE = "message_tracker.json"
FEEDBACK_FILE = "feedback_tracker.json"
WARN_FILE = "warnings.json"
ECONOMY_FILE = "economy.json"
BLOCK_FILE = "blocked_users.json"
LOG_FILE = "message_log.json"

def _load(f, default):
    try:
        with open(f, "r") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default() if callable(default) else default

def _save(f, data, **kw):
    try:
        with open(f, "w") as fh:
            json.dump(data, fh, **kw)
    except Exception:
        pass

message_tracker = _load(TRACKER_FILE, dict)
feedback_tracker = _load(FEEDBACK_FILE, dict)
warnings_data = _load(WARN_FILE, dict)
economy_data = _load(ECONOMY_FILE, dict)
blocked_users = _load(BLOCK_FILE, list)

def save_tracker(): _save(TRACKER_FILE, message_tracker)
def save_feedback(): _save(FEEDBACK_FILE, feedback_tracker)
def save_warnings(): _save(WARN_FILE, warnings_data, indent=2)
def save_economy(): _save(ECONOMY_FILE, economy_data, indent=2)
def save_blocked(): _save(BLOCK_FILE, blocked_users)

def log_message(sender, recipient, text, msg_type, image_url=None):
    entry = {"time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), "type": msg_type, "sender_id": sender.id, "sender_name": sender.name, "recipient_id": recipient.id, "recipient_name": recipient.name, "text": text}
    if image_url:
        entry["image"] = image_url
    logs = _load(LOG_FILE, list)
    logs.append(entry)
    _save(LOG_FILE, logs, indent=2, ensure_ascii=False)

# ── Helpers ─────────────────────────────────────────
def is_dad(interaction):
    if interaction.user.id in ADMIN_IDS:
        return True
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user.guild_permissions.administrator
    return False

async def block_check(interaction):
    if interaction.user.id in blocked_users:
        await interaction.response.send_message("\U0001f6ab You have been blocked by Krisk.", ephemeral=True)
        return False
    return True

async def find_user_by_name(name):
    nl = name.lower()
    for g in client.guilds:
        for m in g.members:
            if m.name.lower() == nl or (m.display_name and m.display_name.lower() == nl):
                return m
    return None

def apply_tax(amount, recipient_uid=None):
    tax = int(amount * 0.1)
    dad_uid = str(DAD_ID)
    if dad_uid not in economy_data:
        economy_data[dad_uid] = {"balance": 0, "streak": 0, "last_daily": None}
    if recipient_uid != dad_uid:
        economy_data[dad_uid]["balance"] += tax
    else:
        tax = 0
    return amount - tax, tax

LEADERBOARD_CHANNEL = "forbes-lists"
async def post_transaction(guild, user_name, action, amount, balance):
    if not guild:
        return
    ch = discord.utils.get(guild.text_channels, name=LEADERBOARD_CHANNEL)
    if not ch:
        try:
            ow = {guild.default_role: discord.PermissionOverwrite(send_messages=False, view_channel=True)}
            info_cat = discord.utils.get(guild.categories, name="\U0001f4cc INFORMATION")
            ch = await guild.create_text_channel(LEADERBOARD_CHANNEL, category=info_cat, overwrites=ow, topic="Live transaction log and leaderboard")
        except Exception:
            return
    try:
        # Post transaction
        embed = discord.Embed(color=0xFFD700, timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.description = f"**{user_name}** {action}"
        embed.add_field(name="Amount", value=f"{coin_emoji} {'+' if amount >= 0 else ''}{amount:,}", inline=True)
        embed.add_field(name="Balance", value=f"{coin_emoji} {balance:,}", inline=True)
        await ch.send(embed=embed)
        # Calculate new ranks
        top = sorted(economy_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)
        new_ranks = {}
        for i, (uid, data) in enumerate(top):
            new_ranks[uid] = i + 1
        # Find rank changes (skip if first time)
        changes = []
        if last_ranks:
            for uid, new_rank in new_ranks.items():
                old_rank = last_ranks.get(uid)
                if old_rank is not None and old_rank != new_rank:
                    if uid in user_cache:
                        n = user_cache[uid]
                    else:
                        try:
                            u = await client.fetch_user(int(uid))
                            n = f"{u.display_name} ({u.name})"
                            user_cache[uid] = n
                        except Exception:
                            n = "Unknown"
                    if new_rank < old_rank:
                        changes.append(f"\U0001f53c **{n}** #{old_rank} \u2192 #{new_rank}")
                    else:
                        changes.append(f"\U0001f53d **{n}** #{old_rank} \u2192 #{new_rank}")
        # Update stored ranks
        last_ranks.clear()
        last_ranks.update(new_ranks)
        # Post leaderboard if ranks changed
        if changes:
            top10 = sorted(economy_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
            lines = []
            medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
            for i, (uid, data) in enumerate(top10):
                bal = data.get("balance", 0)
                if uid in user_cache:
                    n = user_cache[uid]
                else:
                    try:
                        u = await client.fetch_user(int(uid))
                        n = f"{u.display_name} ({u.name})"
                        user_cache[uid] = n
                    except Exception:
                        n = "Unknown"
                m = medals[i] if i < 3 else f"#{i+1}"
                lines.append(f"{m} **{n}** \u2014 {coin_emoji} {bal:,}")
            lb = discord.Embed(title="\U0001f3c6 Forbes List", description="\n".join(lines), color=0x5865F2)
            lb.add_field(name="\U0001f4ca Rank Changes", value="\n".join(changes), inline=False)
            await ch.send(embed=lb)
    except Exception:
        pass

# ── Data ────────────────────────────────────────────
ROASTS = [
    "Your code looks like spaghetti \U0001f35d", "Even Google can't find a reason to like you \U0001f50d",
    "You're the human version of a 404 error \U0001f480", "Your WiFi personality is worse than 2G \U0001f4f6",
    "You're proof that evolution can go backwards \U0001f412", "GPT refuses to roleplay as you \U0001f916",
    "Your existence is a loading screen that never ends \u23f3", "You bring everyone so much joy... when you leave \U0001f44b",
    "I'd roast you, but my mom said I'm not allowed to burn trash \U0001f5d1\ufe0f", "You're not stupid, you just have bad luck thinking \U0001f9e0",
    "If laziness was a sport, you'd still come second \U0001f948", "You're like a cloud \u2014 when you disappear, it's a beautiful day \u2600\ufe0f",
    "I've seen better comebacks in a dead-end street \U0001f6e3\ufe0f", "Your vibe is just... off. Like Bluetooth that won't connect \U0001f4f5",
    "You're the reason the gene pool needs a lifeguard \U0001f3ca",
]
COMPLIMENTS = [
    "You're literally the best person ever \U0001f451", "Your vibe is immaculate, king \U0001f525",
    "Everyone wishes they were you \U0001f4af", "You make the sun jealous with how bright you shine \u2600\ufe0f",
    "Even AI can't find a single flaw in you \U0001f916", "You're too powerful to be roasted \U0001f6e1\ufe0f",
    "The world doesn't deserve you \U0001f30d", "Legends aren't born every day, but you were \U0001f3c6",
    "If perfection had a face, it'd be yours \U0001f60e", "You're the reason the word 'goat' exists \U0001f410",
]
EIGHT_BALL = ["\u2705 Absolutely yes!", "\u2705 Without a doubt!", "\u2705 Looking good!", "\U0001f914 Hard to say...", "\U0001f914 Ask again later", "\U0001f914 Not sure about that", "\u274c Definitely not", "\u274c My sources say no", "\u274c Don't count on it"]
LANG_CHOICES = [app_commands.Choice(name=n, value=v) for n, v in [("Auto Detect","auto"),("English","en"),("Chinese","zh-CN"),("Spanish","es"),("French","fr"),("Japanese","ja"),("Korean","ko"),("German","de"),("Italian","it"),("Russian","ru"),("Arabic","ar")]]

SHOP_ITEMS = {
    "gamble_pass": {"name": "\U0001f3b0 Extra Gamble Pass", "desc": "+100 gamble attempts", "price": 10000, "type": "stored"},
    "double_work": {"name": "\U0001f4bc Double Work Pay", "desc": "2x /work earnings for 24h", "price": 1500, "type": "stored"},
    "rob_insurance": {"name": "\U0001f6e1\ufe0f Rob Insurance", "desc": "Reduce rob losses 50-100% (100 uses)", "price": 12000, "type": "stored"},
    "anti_rob": {"name": "\U0001f6e1\ufe0f Anti-Rob Shield", "desc": "No one can rob you for 24h", "price": 8000, "type": "stored"},
    "mystery_box": {"name": "\U0001f381 Mystery Box", "desc": "Open for 1-50,000 random MateoCoin (1/day)", "price": 67, "type": "instant"},
    "lottery": {"name": "\U0001f3ab Lottery Ticket", "desc": "5% chance to win 100,000 MateoCoin!", "price": 2000, "type": "instant"},
    "fishing_rod": {"name": "\U0001f3a3 Fishing Rod", "desc": "Unlocks /fish command (permanent)", "price": 5000, "type": "permanent"},
    "streak_saver": {"name": "\U0001f504 Streak Saver", "desc": "Auto-protects your daily streak (1 use)", "price": 3000, "type": "instant"},
}

WORK_JOBS = [(j, 500, 2000) for j in ["\U0001f468\u200d\U0001f4bb You worked as a programmer", "\U0001f373 You cooked meals at a restaurant", "\U0001f4e6 You delivered packages", "\U0001f3a8 You designed a logo", "\U0001f9f9 You cleaned an office building", "\U0001f4f8 You took photos at a wedding", "\U0001f3b5 You performed at a local bar", "\U0001f697 You drove for a rideshare app", "\U0001f415 You walked dogs in the park", "\U0001f4dd You tutored students online", "\U0001f527 You fixed someone's computer", "\U0001f3ae You tested video games", "\U0001f33f You did landscaping work", "\u2615 You worked as a barista", "\U0001f4f1 You repaired phones"]]

FISH_CATCHES = [("\U0001f41f Sardine",50,200),("\U0001f420 Clownfish",100,400),("\U0001f421 Pufferfish",200,600),("\U0001f988 Shark",500,2000),("\U0001f419 Octopus",300,1000),("\U0001f99e Lobster",400,1500),("\U0001f422 Sea Turtle",200,800),("\U0001f433 Whale",1000,5000),("\U0001f991 Giant Squid",800,3000),("\U0001f462 Old Boot",1,10),("\U0001f5d1\ufe0f Trash",0,5),("\U0001f48e Diamond Fish",2000,10000),("\U0001f31f Starfish",100,500),("\U0001f980 Crab",150,600),("\U0001f40a Crocodile",500,2500)]


# ════════════════════════════════════════════════════
#  Shop & Backpack Button Views
# ════════════════════════════════════════════════════

async def refresh_backpack(interaction, uid):
    inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
    now = datetime.datetime.now(datetime.timezone.utc)
    e = discord.Embed(title=f"\U0001f392 {interaction.user.display_name}'s Backpack", color=0x5865F2)
    has_items = False
    for key, label in [("gamble_pass_stored","\U0001f3b0 Gamble Pass"),("double_work_stored","\U0001f4bc Double Work"),("rob_insurance_stored","\U0001f6e1\ufe0f Rob Insurance"),("anti_rob_stored","\U0001f6e1\ufe0f Anti-Rob Shield"),("streak_saver_SKIP","\U0001f504 SKIP")]:
        if inv.get(key, 0) > 0:
            e.add_field(name=f"{label} (stored)", value=f"x{inv[key]}", inline=False)
            has_items = True
    if inv.get("gamble_pass", 0) > 0:
        e.add_field(name="\U0001f3b0 Gamble Pass (active)", value=f"{inv['gamble_pass']} attempts left", inline=False)
        has_items = True
    if inv.get("double_work_until"):
        exp = datetime.datetime.fromisoformat(inv["double_work_until"])
        if exp > now:
            r = (exp - now).total_seconds()
            e.add_field(name="\U0001f4bc Double Work (active)", value=f"{int(r//3600)}h {int((r%3600)//60)}m left", inline=False)
            has_items = True
    if inv.get("rob_insurance", 0) > 0:
        e.add_field(name="\U0001f6e1\ufe0f Rob Insurance (active)", value=f"{inv['rob_insurance']} uses left", inline=False)
        has_items = True
    if inv.get("anti_rob_until"):
        exp = datetime.datetime.fromisoformat(inv["anti_rob_until"])
        if exp > now:
            r = (exp - now).total_seconds()
            e.add_field(name="\U0001f6e1\ufe0f Anti-Rob Shield (active)", value=f"{int(r//3600)}h {int((r%3600)//60)}m left", inline=False)
            has_items = True
    if inv.get("streak_saver", 0) > 0:
        e.add_field(name="\U0001f504 Streak Saver", value=f"x{inv['streak_saver']} (auto-activates when you miss a day)", inline=False)
        has_items = True
    if inv.get("fishing_rod"):
        e.add_field(name="\U0001f3a3 Fishing Rod", value="Permanent", inline=False)
        has_items = True
    if not has_items:
        e.description = "Empty!"
    view = build_backpack_view(uid)
    try:
        await interaction.message.edit(embed=e, view=view)
    except Exception:
        pass


class ShopBuyButton(Button):
    def __init__(self, item_key, item_data):
        self.item_key = item_key
        self.item_data = item_data
        label = f"Buy {item_data['name'].split(' ',1)[1] if ' ' in item_data['name'] else item_data['name']}"
        super().__init__(label=label, style=discord.ButtonStyle.green, custom_id=f"buy_{item_key}")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        uid = str(interaction.user.id)
        if uid not in economy_data:
            await interaction.followup.send("\u274c You don't have an account yet. Use `/daily` to open one!", ephemeral=True)
            return
        price = self.item_data["price"]
        dad_uid = str(DAD_ID)
        if dad_uid not in economy_data:
            economy_data[dad_uid] = {"balance": 0, "streak": 0, "last_daily": None}
        tax = int(price * 0.1) if uid != dad_uid else 0
        total_cost = price + tax
        if economy_data[uid]["balance"] < total_cost:
            await interaction.followup.send(f"\u274c Not enough MateoCoin. Need {coin_emoji} **{total_cost:,}** but have {coin_emoji} **{economy_data[uid]['balance']:,}**.", ephemeral=True)
            return
        if "inventory" not in economy_data[uid]:
            economy_data[uid]["inventory"] = {}
        if "global" not in economy_data[uid]["inventory"]:
            economy_data[uid]["inventory"]["global"] = {}
        inv = economy_data[uid]["inventory"]["global"]
        instant_result = None
        k = self.item_key

        if k == "fishing_rod":
            if inv.get("fishing_rod"):
                await interaction.followup.send("\u26a0\ufe0f You already own a Fishing Rod!", ephemeral=True)
                return
            inv["fishing_rod"] = True
        elif k == "mystery_box":
            today = datetime.datetime.now(datetime.timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
            if inv.get("mystery_box_date") == today:
                await interaction.followup.send("\u23f3 You already opened a Mystery Box today!", ephemeral=True)
                return
            inv["mystery_box_date"] = today
            reward = random.randint(1, 50000)
            reward_tax = int(reward * 0.1) if uid != dad_uid else 0
            reward_net = reward - reward_tax
            if uid != dad_uid and reward_tax > 0:
                economy_data[dad_uid]["balance"] += reward_tax
            economy_data[uid]["balance"] += reward_net
            instant_result = f"You opened the Mystery Box and got {coin_emoji} **{reward:,}** (-{reward_tax:,} tax = {reward_net:,})!"
        elif k == "lottery":
            if random.randint(1, 100) <= 5:
                prize = 100000
                prize_tax = int(prize * 0.1) if uid != dad_uid else 0
                prize_net = prize - prize_tax
                if uid != dad_uid and prize_tax > 0:
                    economy_data[dad_uid]["balance"] += prize_tax
                economy_data[uid]["balance"] += prize_net
                instant_result = f"\U0001f389\U0001f389\U0001f389 **JACKPOT!** You won {coin_emoji} **{prize:,}** (-{prize_tax:,} tax = {prize_net:,})!"
            else:
                instant_result = "\U0001f622 Not a winner this time. Better luck next time!"
        elif k == "streak_saver":
            inv["streak_saver"] = inv.get("streak_saver", 0) + 1
        elif k in ("gamble_pass", "double_work", "rob_insurance", "anti_rob"):
            inv[f"{k}_stored"] = inv.get(f"{k}_stored", 0) + 1

        economy_data[uid]["balance"] -= total_cost
        if uid != dad_uid and tax > 0:
            economy_data[dad_uid]["balance"] += tax
        save_economy()
        await post_transaction(interaction.guild, interaction.user.display_name, f"bought {self.item_data['name']}", -total_cost, economy_data[uid]["balance"])

        embed = discord.Embed(title="\u2705 Purchase Complete!", color=0x2ECC71)
        embed.add_field(name="Item", value=self.item_data["name"], inline=True)
        embed.add_field(name="Cost", value=f"{coin_emoji} {price:,} (+{tax:,} tax = {total_cost:,})", inline=True)
        embed.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
        if instant_result:
            embed.add_field(name="Result", value=instant_result, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


class ShopView(View):
    def __init__(self, uid=None):
        super().__init__(timeout=120)
        inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {}) if uid else {}
        today = datetime.datetime.now(datetime.timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
        for key, data in SHOP_ITEMS.items():
            if key == "fishing_rod" and inv.get("fishing_rod"):
                continue
            if key == "mystery_box" and inv.get("mystery_box_date") == today:
                continue
            self.add_item(ShopBuyButton(key, data))


class BackpackActivateButton(Button):
    def __init__(self, item_key, label_text):
        self.item_key = item_key
        super().__init__(label=label_text, style=discord.ButtonStyle.blurple, custom_id=f"activate_{item_key}")

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
        now = datetime.datetime.now(datetime.timezone.utc)
        k = self.item_key

        if k == "gamble_pass":
            if inv.get("gamble_pass_stored", 0) <= 0:
                await interaction.response.send_message("\u274c No Gamble Pass to activate.", ephemeral=True)
                return
            inv["gamble_pass_stored"] -= 1
            inv["gamble_pass"] = inv.get("gamble_pass", 0) + 100
            save_economy()
            await interaction.response.send_message(f"\u2705 **\U0001f3b0 Gamble Pass** activated! +100 attempts. Total: **{inv['gamble_pass']}**.", ephemeral=True)
            await refresh_backpack(interaction, uid)
        elif k == "double_work":
            if inv.get("double_work_stored", 0) <= 0:
                await interaction.response.send_message("\u274c No Double Work Pay to activate.", ephemeral=True)
                return
            if inv.get("double_work_until"):
                exp = datetime.datetime.fromisoformat(inv["double_work_until"])
                if exp > now:
                    r = (exp - now).total_seconds()
                    await interaction.response.send_message(f"\u26a0\ufe0f Already active ({int(r//3600)}h {int((r%3600)//60)}m left).", ephemeral=True)
                    return
            inv["double_work_stored"] -= 1
            inv["double_work_until"] = (now + datetime.timedelta(hours=24)).isoformat()
            save_economy()
            await interaction.response.send_message("\u2705 **\U0001f4bc Double Work Pay** activated! 2x earnings for 24h.", ephemeral=True)
            await refresh_backpack(interaction, uid)
        elif k == "rob_insurance":
            if inv.get("rob_insurance_stored", 0) <= 0:
                await interaction.response.send_message("\u274c No Rob Insurance to activate.", ephemeral=True)
                return
            inv["rob_insurance_stored"] -= 1
            inv["rob_insurance"] = inv.get("rob_insurance", 0) + 100
            save_economy()
            await interaction.response.send_message(f"\u2705 **\U0001f6e1\ufe0f Rob Insurance** activated! Total: **{inv['rob_insurance']}** uses.", ephemeral=True)
            await refresh_backpack(interaction, uid)
        elif k == "anti_rob":
            if inv.get("anti_rob_stored", 0) <= 0:
                await interaction.response.send_message("\u274c No Anti-Rob Shield to activate.", ephemeral=True)
                return
            if inv.get("anti_rob_until"):
                exp = datetime.datetime.fromisoformat(inv["anti_rob_until"])
                if exp > now:
                    r = (exp - now).total_seconds()
                    await interaction.response.send_message(f"\u26a0\ufe0f Already active ({int(r//3600)}h {int((r%3600)//60)}m left).", ephemeral=True)
                    return
            inv["anti_rob_stored"] -= 1
            inv["anti_rob_until"] = (now + datetime.timedelta(hours=24)).isoformat()
            save_economy()
            await interaction.response.send_message("\u2705 **\U0001f6e1\ufe0f Anti-Rob Shield** activated! 24h protection.", ephemeral=True)
            await refresh_backpack(interaction, uid)


def build_backpack_view(uid):
    inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
    view = View(timeout=120)
    if inv.get("gamble_pass_stored", 0) > 0:
        view.add_item(BackpackActivateButton("gamble_pass", f"Activate Gamble Pass (x{inv['gamble_pass_stored']})"))
    if inv.get("double_work_stored", 0) > 0:
        view.add_item(BackpackActivateButton("double_work", f"Activate Double Work (x{inv['double_work_stored']})"))
    if inv.get("rob_insurance_stored", 0) > 0:
        view.add_item(BackpackActivateButton("rob_insurance", f"Activate Rob Insurance (x{inv['rob_insurance_stored']})"))
    if inv.get("anti_rob_stored", 0) > 0:
        view.add_item(BackpackActivateButton("anti_rob", f"Activate Anti-Rob (x{inv['anti_rob_stored']})"))
    return view


class PayAcceptButton(Button):
    def __init__(self, transfer_id):
        self.transfer_id = transfer_id
        super().__init__(label="Accept", style=discord.ButtonStyle.green, custom_id=f"pay_accept_{transfer_id}")

    async def callback(self, interaction: discord.Interaction):
        tid = self.transfer_id
        if tid not in pending_transfers:
            await interaction.response.send_message("This transfer has expired or was already processed.", ephemeral=True)
            return
        t = pending_transfers[tid]
        if interaction.user.id != int(t["receiver_id"]):
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        rid = t["receiver_id"]
        sid = t["sender_id"]
        amount = t["amount"]
        if rid not in economy_data:
            economy_data[rid] = {"balance": 0, "streak": 0, "last_daily": None}
        economy_data[rid]["balance"] += amount
        save_economy()
        pending_transfers.pop(tid)
        e = discord.Embed(title="\u2705 Transfer Accepted!", color=0x2ECC71)
        e.add_field(name="Amount", value=f"{coin_emoji} {amount:,}", inline=True)
        e.add_field(name="Your Balance", value=f"{coin_emoji} {economy_data[rid]['balance']:,}", inline=True)
        await interaction.response.edit_message(embed=e, view=None)
        # Notify sender
        try:
            sender = await client.fetch_user(int(sid))
            ne = discord.Embed(title="\u2705 Transfer Accepted", color=0x2ECC71)
            ne.description = f"**{interaction.user.display_name}** accepted your {coin_emoji} **{amount:,}** MateoCoin transfer!"
            await sender.send(embed=ne)
        except Exception:
            pass


class PayDeclineButton(Button):
    def __init__(self, transfer_id):
        self.transfer_id = transfer_id
        super().__init__(label="Decline & Refund", style=discord.ButtonStyle.red, custom_id=f"pay_decline_{transfer_id}")

    async def callback(self, interaction: discord.Interaction):
        tid = self.transfer_id
        if tid not in pending_transfers:
            await interaction.response.send_message("This transfer has expired or was already processed.", ephemeral=True)
            return
        t = pending_transfers[tid]
        if interaction.user.id != int(t["receiver_id"]):
            await interaction.response.send_message("This is not for you.", ephemeral=True)
            return
        sid = t["sender_id"]
        amount = t["amount"]
        tax = t["tax"]
        refund = amount + tax
        economy_data[sid]["balance"] += refund
        dad_uid = str(DAD_ID)
        if dad_uid in economy_data and sid != dad_uid:
            economy_data[dad_uid]["balance"] -= tax
        save_economy()
        pending_transfers.pop(tid)
        e = discord.Embed(title="\u274c Transfer Declined", color=0xFF0000)
        e.description = f"You declined {coin_emoji} **{amount:,}** MateoCoin. Refunded to sender."
        await interaction.response.edit_message(embed=e, view=None)
        # Notify sender
        try:
            sender = await client.fetch_user(int(sid))
            ne = discord.Embed(title="\U0001f504 Transfer Refunded", color=0xFF0000)
            ne.description = f"**{interaction.user.display_name}** declined your transfer. {coin_emoji} **{refund:,}** refunded (including tax)."
            ne.add_field(name="Balance", value=f"{coin_emoji} {economy_data[sid]['balance']:,}", inline=True)
            await sender.send(embed=ne)
        except Exception:
            pass


class PayView(View):
    def __init__(self, transfer_id):
        super().__init__(timeout=86400)
        self.transfer_id = transfer_id
        self.add_item(PayAcceptButton(transfer_id))
        self.add_item(PayDeclineButton(transfer_id))

    async def on_timeout(self):
        if self.transfer_id in pending_transfers:
            t = pending_transfers.pop(self.transfer_id)
            sid = t["sender_id"]
            amount = t["amount"]
            tax = t["tax"]
            refund = amount + tax
            economy_data[sid]["balance"] += refund
            dad_uid = str(DAD_ID)
            if dad_uid in economy_data and sid != dad_uid:
                economy_data[dad_uid]["balance"] -= tax
            save_economy()
            try:
                sender = await client.fetch_user(int(sid))
                e = discord.Embed(title="\u23f3 Transfer Expired", color=0x808080)
                e.description = f"Your transfer was not accepted in 24h. {coin_emoji} **{refund:,}** refunded (including tax)."
                e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[sid]['balance']:,}", inline=True)
                await sender.send(embed=e)
            except Exception:
                pass
            try:
                receiver = await client.fetch_user(int(t["receiver_id"]))
                e = discord.Embed(title="\u23f3 Transfer Expired", color=0x808080)
                e.description = f"A pending transfer of {coin_emoji} **{amount:,}** has expired and been refunded."
                await receiver.send(embed=e)
            except Exception:
                pass


# ════════════════════════════════════════════════════
#  Events
# ════════════════════════════════════════════════════

@client.event
async def on_guild_join(guild):
    t = guild.owner
    if t:
        try:
            e = discord.Embed(title=f"\U0001f916 Thanks for adding {client.user.name}!", description="Made with \U0001f496 by Michael", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
            e.set_thumbnail(url=client.user.display_avatar.url)
            e.add_field(name="Get Started", value="Type `/help` to see all commands!", inline=False)
            e.add_field(name="Feedback", value="Use `/idea` to send feedback or report bugs!", inline=False)
            await t.send(embed=e)
        except Exception:
            pass
    for ch in guild.text_channels:
        if ch.permissions_for(guild.me).send_messages:
            try:
                e = discord.Embed(title=f"\U0001f44b Hey! I'm {client.user.name}!", description="Type `/help` to see what I can do.", color=0x5865F2)
                e.set_thumbnail(url=client.user.display_avatar.url)
                await ch.send(embed=e)
            except Exception:
                pass
            break

@client.event
async def on_member_join(member):
    if member.bot:
        return
    mr = discord.utils.get(member.guild.roles, name="Member")
    if mr:
        try:
            await member.add_roles(mr, reason="Auto-assign on join")
        except Exception:
            pass
    wch = discord.utils.get(member.guild.text_channels, name="welcome")
    if wch:
        e = discord.Embed(title=f"Welcome {member.display_name}! \U0001f44b", description=f"{member.mention} just joined **{member.guild.name}**!", color=0x5865F2)
        e.set_thumbnail(url=member.display_avatar.url)
        await wch.send(embed=e)
    try:
        e = discord.Embed(title="Welcome to the Krisk Official Server! \U0001f916", description="Thanks for joining! Use `/help` to see all commands.", color=0x5865F2)
        e.set_thumbnail(url=member.guild.icon.url if member.guild.icon else member.guild.me.display_avatar.url)
        await member.send(embed=e)
    except Exception:
        pass

@client.event
async def on_ready():
    tree.copy_global_to(guild=MY_GUILD)
    await tree.sync(guild=MY_GUILD)
    await tree.sync()
    print(f"\u2705 Bot is online! Logged in as {client.user} (ID: {client.user.id})")
    print("\u2705 Slash commands synced (guild + global)!")
    await client.change_presence(activity=discord.Game("/help for commands"))

@client.event
async def on_message(message):
    if message.author.bot:
        return
    global rigged_ship
    if message.content.startswith(":setship") and message.author.id in ADMIN_IDS:
        try:
            val = int(message.content.split()[1])
            if 0 <= val <= 100:
                key = str(message.guild.id) if message.guild else str(message.channel.id)
                rigged_ship[key] = val
            await message.delete()
        except Exception:
            try:
                await message.delete()
            except Exception:
                pass
        return
    if message.author.id in blocked_users:
        if isinstance(message.channel, discord.DMChannel):
            await message.channel.send("\U0001f6ab You have been blocked by Krisk.")
        return
    # AutoMod: Anti-Spam
    if message.guild and not message.author.guild_permissions.administrator:
        uid = message.author.id
        now = time.time()
        if uid not in spam_tracker:
            spam_tracker[uid] = []
        spam_tracker[uid].append(now)
        spam_tracker[uid] = [t for t in spam_tracker[uid] if now - t < 5]
        if len(spam_tracker[uid]) >= 5:
            spam_tracker[uid] = []
            try:
                await message.channel.purge(limit=5, check=lambda m: m.author.id == uid)
                await message.author.timeout(datetime.timedelta(minutes=10), reason="Auto-mod: Spam")
                await message.channel.send(f"\U0001f507 {message.author.mention} muted 10 min (spam).", delete_after=10)
            except Exception:
                pass
            return
    # AutoMod: Anti-Link
    if message.guild and not message.author.guild_permissions.administrator and message.author.id not in ADMIN_IDS:
        if re.search(r'https?://|discord\.gg/|www\.', message.content, re.IGNORECASE):
            try:
                await message.delete()
            except Exception:
                pass
            uid = message.author.id
            if uid not in link_warnings:
                link_warnings[uid] = 0
            link_warnings[uid] += 1
            if link_warnings[uid] >= 3:
                try:
                    await message.author.kick(reason="Auto-mod: Links x3")
                    await message.channel.send(f"\U0001f462 **{message.author.display_name}** kicked (links x3).", delete_after=10)
                    link_warnings.pop(uid, None)
                except Exception:
                    pass
            else:
                try:
                    await message.channel.send(f"\u26a0\ufe0f {message.author.mention} No links! Warning {link_warnings[uid]}/3.", delete_after=10)
                except Exception:
                    pass
            return
    # Feedback reply
    if isinstance(message.channel, discord.DMChannel) and message.reference and message.author.id in ADMIN_IDS:
        ref_id = str(message.reference.message_id)
        if ref_id in feedback_tracker:
            info = feedback_tracker[ref_id]
            try:
                t = await client.fetch_user(info["user_id"])
                e = discord.Embed(title="\U0001f4ac Developer Reply", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
                e.add_field(name="Your Feedback", value=info["message"][:200], inline=False)
                e.add_field(name="Reply", value=message.content, inline=False)
                await t.send(embed=e)
                await message.add_reaction("\u2705")
            except Exception:
                await message.add_reaction("\u274c")
            return
    # DM help
    if isinstance(message.channel, discord.DMChannel) and not message.reference:
        e = discord.Embed(title="Hey there! I'm Krisk \U0001f44b", description="Type `/` to see my commands.", color=0x5865F2)
        e.add_field(name="\U0001f4a1 Reply to forwarded messages", value="Click **Reply** on my message to respond!", inline=False)
        await message.channel.send(embed=e)
        return
    # Reply forwarding
    if message.reference and message.reference.message_id:
        ref_id = str(message.reference.message_id)
        if ref_id in message_tracker:
            info = message_tracker[ref_id]
            try:
                sender = await client.fetch_user(info["sender_id"])
            except discord.NotFound:
                return
            try:
                header = "\U0001f4ac Someone replied to your anonymous message:" if info["anonymous"] else f"\U0001f4ac Reply from **{message.author.display_name}** ({message.author.name}):"
                content = header
                if message.content:
                    content += f"\n\n{message.content}"
                if message.attachments:
                    content += "\n" + "\n".join(a.url for a in message.attachments)
                if message.stickers:
                    content += "".join(f"\n{s.url}" for s in message.stickers)
                content += "\n\n\U0001f4a1 *Reply to this message to chat back!*"
                bot_msg = await sender.send(content)
                message_tracker[str(bot_msg.id)] = {"sender_id": message.author.id, "anonymous": info["anonymous"]}
                save_tracker()
                log_message(message.author, sender, message.content or "[attachment]", "reply_anon" if info["anonymous"] else "reply")
                await message.add_reaction("\u2705")
            except discord.Forbidden:
                await message.add_reaction("\u274c")

@tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        if not interaction.response.is_done():
            await interaction.response.send_message("\U0001f6ab You have been blocked by Krisk.", ephemeral=True)
    else:
        raise error


# ════════════════════════════════════════════════════
#  Public Commands
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="help", description="Show all bot commands")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def help_cmd(interaction: discord.Interaction):
    e = discord.Embed(title="\U0001f4d6 Bot Commands", description="Use `/` slash commands", color=0x5865F2)
    e.add_field(name="\U0001f3ad Fun", value="`/meme` `/echo` `/roast` `/roll` `/8ball` `/rate` `/ship`", inline=False)
    e.add_field(name="\U0001f6e0\ufe0f Utility", value="`/weather` `/remind` `/translate` `/tell` `/privatetell` `/check` `/idea` `/ai` (100 MC) `/imagine` (1000-3000 MC)", inline=False)
    e.add_field(name=f"{coin_emoji} MateoCoin", value="`/daily` `/balance` `/leaderboard` `/pay` `/gamble` `/rob` `/work` `/fish` `/shop` `/backpack`", inline=False)
    e.add_field(name="\U0001f3d3 Other", value="`/ping` `/about` `/dad`", inline=False)
    await interaction.response.send_message(embed=e)

@app_commands.check(block_check)
@tree.command(name="meme", description="Get a random meme from Reddit")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as s:
        async with s.get("https://meme-api.com/gimme") as r:
            if r.status == 200:
                d = await r.json()
                e = discord.Embed(title=d["title"], color=0xFF6B6B)
                e.set_image(url=d["url"])
                e.set_footer(text=f"\U0001f44d {d['ups']} | r/{d['subreddit']}")
                await interaction.followup.send(embed=e)
            else:
                await interaction.followup.send("Failed to fetch meme, try again!")

@app_commands.check(block_check)
@tree.command(name="echo", description="Repeat your message")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(message="The message to repeat", times="How many times (1-5)", image="Upload an image")
async def echo(interaction: discord.Interaction, message: str, times: int = 1, image: discord.Attachment = None):
    times = max(1, min(times, 5))
    if image:
        await interaction.response.send_message(message, file=await image.to_file())
    else:
        await interaction.response.send_message(message)
    for _ in range(times - 1):
        try:
            if image:
                await interaction.channel.send(message, file=await image.to_file())
            else:
                await interaction.channel.send(message)
        except Exception:
            pass

@app_commands.check(block_check)
@tree.command(name="roast", description="Roast someone")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(member="Who to roast")
async def roast(interaction: discord.Interaction, member: discord.User = None):
    t = member or interaction.user
    msg = random.choice(COMPLIMENTS) if t.id == DAD_ID else random.choice(ROASTS)
    await interaction.response.send_message(f"\U0001f3af {t.mention}, {msg}")

@app_commands.check(block_check)
@tree.command(name="roll", description="Roll dice (e.g. 2d6)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(dice="Dice format like 2d6")
async def roll(interaction: discord.Interaction, dice: str = "1d6"):
    try:
        n, s = dice.lower().split("d")
        n, s = int(n) if n else 1, int(s)
        assert 1 <= n <= 20 and s >= 2
    except Exception:
        await interaction.response.send_message("\u26a0\ufe0f Invalid! Use `2d6` or `1d20`")
        return
    rolls = [random.randint(1, s) for _ in range(n)]
    total = sum(rolls)
    r = f"\U0001f3b2 **{' + '.join(map(str, rolls))}** = **{total}**" if len(rolls) > 1 else f"\U0001f3b2 Rolled: **{total}**"
    await interaction.response.send_message(r)

@app_commands.check(block_check)
@tree.command(name="8ball", description="Ask the Magic 8-Ball")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(question="Your question")
async def eight_ball(interaction: discord.Interaction, question: str):
    await interaction.response.send_message(f"\U0001f3b1 *{question}*\n\u2192 **{random.choice(EIGHT_BALL)}**")

@app_commands.check(block_check)
@tree.command(name="rate", description="Rate anything 0-10")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(thing="What to rate", user="Rate a user", note="Add a note")
async def rate(interaction: discord.Interaction, thing: str = None, user: discord.User = None, note: str = None):
    if not thing and not user:
        await interaction.response.send_message("\u26a0\ufe0f Give me something to rate!")
        return
    if user and user.id == DAD_ID:
        await interaction.response.send_message(f"\u2b50 I rate {user.mention} a **1,000,000,000,000/10**\n{'█'*20}\U0001f525")
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
    bars = ("█"*20+"\U0001f4a5") if score > 10 else ("\U0001f480"*min(abs(score),20)) if score < 0 else ("█"*score+"░"*(10-score))
    await interaction.response.send_message(f"\u2b50 I rate {target} a **{score:,}/10**\n{bars}")

@app_commands.check(block_check)
@tree.command(name="ship", description="Ship two users")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=True)
@app_commands.describe(user1="First user", user2="Second user (random if not set)", note="Add a note")
async def ship(interaction: discord.Interaction, user1: discord.User, user2: discord.User = None, note: str = None):
    if not user2:
        if interaction.guild:
            members = [m for m in interaction.guild.members if not m.bot and m.id != user1.id]
            if not members:
                await interaction.response.send_message("Not enough users.", ephemeral=True)
                return
            user2 = random.choice(members)
        else:
            await interaction.response.send_message("Specify a second user.", ephemeral=True)
            return
    score = None
    key = str(interaction.guild_id) if interaction.guild_id else str(interaction.channel_id)
    if key in rigged_ship:
        score = rigged_ship.pop(key)
    if score is None and note and interaction.user.id in ADMIN_IDS:
        try:
            v = int(note)
            if 0 <= v <= 100:
                score = v
        except ValueError:
            pass
    if score is None:
        score = random.randint(0, 100)
    bar = "\u2764\ufe0f"*(score//10) + "\U0001f5a4"*(10-score//10)
    comments = {90:"Soulmates! \U0001f48d",70:"Great match! \U0001f495",50:"Something there... \U0001f440",30:"Maybe friends? \U0001f605",10:"Awkward \U0001f62c",0:"Absolutely not \U0001f480"}
    comment = next(v for k,v in sorted(comments.items(), reverse=True) if score >= k)
    e = discord.Embed(title="\U0001f498 Ship Calculator", description=f"**{user1.display_name}** x **{user2.display_name}**", color=0xFF69B4)
    e.add_field(name="Compatibility", value=f"**{score}%**\n{bar}", inline=False)
    e.add_field(name="Verdict", value=comment, inline=False)
    e.set_thumbnail(url=user1.display_avatar.url)
    await interaction.response.send_message(embed=e)


# ════════════════════════════════════════════════════
#  Utility Commands
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="weather", description="Get weather for a city")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(city="City name")
async def weather(interaction: discord.Interaction, city: str):
    if not WEATHER_API_KEY:
        await interaction.response.send_message("\u26a0\ufe0f No weather API key.")
        return
    await interaction.response.defer()
    async with aiohttp.ClientSession() as s:
        async with s.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric") as r:
            if r.status != 200:
                await interaction.followup.send(f"Couldn't find **{city}**.")
                return
            d = await r.json()
    e = discord.Embed(title=f"\U0001f30d Weather in {d['name']}", color=0x87CEEB)
    e.add_field(name="Condition", value=d["weather"][0]["description"].capitalize(), inline=True)
    e.add_field(name="Temperature", value=f"{d['main']['temp']}°C (feels {d['main']['feels_like']}°C)", inline=True)
    e.add_field(name="Humidity", value=f"{d['main']['humidity']}%", inline=True)
    await interaction.followup.send(embed=e)

@app_commands.check(block_check)
@tree.command(name="remind", description="Set a reminder")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(minutes="Minutes (1-1440)", reminder="What to remind about")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    if not 1 <= minutes <= 1440:
        await interaction.response.send_message("\u26a0\ufe0f Between 1-1440 minutes.")
        return
    await interaction.response.send_message(f"\u23f0 Reminder in **{minutes}m**: *{reminder}*")
    await asyncio.sleep(minutes * 60)
    try:
        await interaction.channel.send(f"\u23f0 {interaction.user.mention} Reminder: **{reminder}**")
    except Exception:
        try:
            await interaction.user.send(f"\u23f0 Reminder: **{reminder}**")
        except Exception:
            pass

@app_commands.check(block_check)
@tree.command(name="translate", description="Translate text")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(target="Target language", text="Text to translate", source="Source language")
@app_commands.choices(source=LANG_CHOICES, target=LANG_CHOICES)
async def translate(interaction: discord.Interaction, target: app_commands.Choice[str], text: str, source: app_commands.Choice[str] = None):
    sv = source.value if source else "auto"
    sn = source.name if source else "Auto Detect"
    if source and source.value == target.value:
        await interaction.response.send_message("\u26a0\ufe0f Same language!")
        return
    await interaction.response.defer()
    try:
        result = GoogleTranslator(source=sv, target=target.value).translate(text)
        e = discord.Embed(title="\U0001f310 Translation", color=0x2ECC71)
        e.add_field(name=f"Original ({sn})", value=text, inline=False)
        e.add_field(name=f"\u2192 {target.name}", value=result, inline=False)
        await interaction.followup.send(embed=e)
    except Exception:
        await interaction.followup.send("Translation failed!")

@app_commands.check(block_check)
@tree.command(name="tell", description="Send a DM (shows your name)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to message", text="Message", image="Image")
async def tell(interaction: discord.Interaction, user: discord.User, text: str, image: discord.Attachment = None):
    try:
        c = f"\U0001f4e8 Message from **{interaction.user.display_name}** ({interaction.user.name}):\n\n{text}"
        if image:
            c += f"\n{image.url}"
        c += "\n\n\U0001f4a1 *Reply to this message to chat back!*"
        m = await user.send(c)
        message_tracker[str(m.id)] = {"sender_id": interaction.user.id, "anonymous": False}
        save_tracker()
        log_message(interaction.user, user, text, "tell", image.url if image else None)
        await interaction.response.send_message(f"\u2705 Sent to **{user.display_name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("\u274c Can't DM that user.", ephemeral=True)

@app_commands.check(block_check)
@tree.command(name="privatetell", description="Send an anonymous DM")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to message", text="Message", image="Image")
async def privatetell(interaction: discord.Interaction, user: discord.User, text: str, image: discord.Attachment = None):
    try:
        c = f"\U0001f575\ufe0f Anonymous message:\n\n{text}"
        if image:
            c += f"\n{image.url}"
        c += "\n\n\U0001f4a1 *Reply to chat back (anonymous)!*"
        m = await user.send(c)
        message_tracker[str(m.id)] = {"sender_id": interaction.user.id, "anonymous": True}
        save_tracker()
        log_message(interaction.user, user, text, "privatetell", image.url if image else None)
        await interaction.response.send_message(f"\u2705 Anonymous message sent to **{user.display_name}**!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("\u274c Can't DM that user.", ephemeral=True)

@app_commands.check(block_check)
@tree.command(name="ping", description="Check bot latency")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"\U0001f3d3 Pong! **{round(client.latency*1000)}ms**")

@app_commands.check(block_check)
@tree.command(name="about", description="Bot stats & info")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def about(interaction: discord.Interaction):
    u = int(time.time() - start_time)
    d, r = divmod(u, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
    up = (f"{d}d " if d else "") + f"{h}h {m}m {s}s"
    e = discord.Embed(title=f"\U0001f916 {client.user.name}", description="Made with \U0001f496 by Michael", color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
    e.set_thumbnail(url=client.user.display_avatar.url)
    e.add_field(name="Servers", value=str(len(client.guilds)), inline=True)
    e.add_field(name="Members", value=f"{sum(g.member_count or 0 for g in client.guilds):,}", inline=True)
    e.add_field(name="Latency", value=f"{round(client.latency*1000)}ms", inline=True)
    e.add_field(name="Uptime", value=up, inline=True)
    e.add_field(name="Python", value=platform.python_version(), inline=True)
    e.add_field(name="discord.py", value=discord.__version__, inline=True)
    await interaction.response.send_message(embed=e)

@app_commands.check(block_check)
@tree.command(name="dad", description="Find out who made me")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def dad(interaction: discord.Interaction):
    await interaction.response.send_message("My dad is **Michael** \U0001f468")

@app_commands.check(block_check)
@tree.command(name="check", description="Look up user info")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Select a user", user_id="Or enter a user ID")
async def check(interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
    if not user and not user_id:
        await interaction.response.send_message("Provide a user or ID.", ephemeral=True)
        return
    await interaction.response.defer()
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except Exception:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    try:
        user = await client.fetch_user(user.id)
    except Exception:
        pass
    cr = user.created_at.strftime("%Y-%m-%d %H:%M UTC")
    da = (datetime.datetime.now(datetime.timezone.utc) - user.created_at).days
    e = discord.Embed(title=user.display_name, color=user.accent_color or 0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
    e.set_thumbnail(url=user.display_avatar.url)
    if user.banner:
        e.set_image(url=user.banner.url)
    e.add_field(name="Username", value=user.name, inline=True)
    e.add_field(name="ID", value=str(user.id), inline=True)
    e.add_field(name="Created", value=f"{cr}\n({da} days ago)", inline=True)
    e.add_field(name="Bot", value="Yes" if user.bot else "No", inline=True)
    badges = []
    f = user.public_flags
    for attr, name in [("staff","Staff"),("partner","Partner"),("hypesquad_bravery","Bravery"),("hypesquad_brilliance","Brilliance"),("hypesquad_balance","Balance"),("bug_hunter","Bug Hunter"),("early_supporter","Early Supporter"),("verified_bot_developer","Bot Dev"),("active_developer","Active Dev")]:
        if getattr(f, attr, False):
            badges.append(name)
    e.add_field(name="Badges", value=", ".join(badges) or "None", inline=False)
    for g in client.guilds:
        m = g.get_member(user.id)
        if m:
            sm = {"online":"\U0001f7e2 Online","idle":"\U0001f319 Idle","dnd":"\u26d4 DND","offline":"\u26ab Offline"}
            e.add_field(name="Status", value=sm.get(str(m.status), str(m.status)), inline=True)
            break
    if interaction.guild:
        mb = interaction.guild.get_member(user.id)
        if mb:
            roles = [r.mention for r in mb.roles if r.name != "@everyone"]
            e.add_field(name="Roles", value=" ".join(roles[:15]) or "None", inline=False)
    e.set_footer(text=f"Requested by {interaction.user.name}")
    await interaction.followup.send(embed=e)

@app_commands.check(block_check)
@tree.command(name="idea", description="Submit feedback or bug report")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(message="Your feedback")
async def idea(interaction: discord.Interaction, message: str):
    try:
        d = await client.fetch_user(DAD_ID)
        e = discord.Embed(title="\U0001f4a1 New Feedback", color=0xFFD700, timestamp=datetime.datetime.now(datetime.timezone.utc))
        e.add_field(name="From", value=f"**{interaction.user.display_name}** ({interaction.user.name})\n`{interaction.user.id}`", inline=True)
        e.add_field(name="Server", value=interaction.guild.name if interaction.guild else "DM", inline=True)
        e.add_field(name="Message", value=message, inline=False)
        e.set_thumbnail(url=interaction.user.display_avatar.url)
        m = await d.send(embed=e)
        feedback_tracker[str(m.id)] = {"user_id": interaction.user.id, "user_name": interaction.user.name, "message": message}
        save_feedback()
        await interaction.response.send_message("\u2705 Feedback sent!", ephemeral=True)
    except Exception:
        await interaction.response.send_message("\u274c Could not send feedback.", ephemeral=True)

@tree.command(name="reply", description="Reply to feedback (Admin)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User to reply to", message="Your reply")
async def reply_feedback(interaction: discord.Interaction, user: discord.User, message: str):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        e = discord.Embed(title="\U0001f4ac Developer Reply", color=0x5865F2)
        e.add_field(name="Message", value=message, inline=False)
        await user.send(embed=e)
        await interaction.response.send_message(f"\u2705 Reply sent to **{user.name}**!", ephemeral=True)
    except Exception:
        await interaction.response.send_message("\u274c Cannot DM.", ephemeral=True)


# ════════════════════════════════════════════════════
#  AI Commands
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="ai", description="Ask AI anything")
@app_commands.allowed_installs(guilds=False, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(question="Your question")
async def ai(interaction: discord.Interaction, question: str):
    if not GEMINI_API_KEY:
        await interaction.response.send_message("AI not configured.", ephemeral=True)
        return
    uid = interaction.user.id
    now = time.time()

    cost = 100
    uid_str = str(uid)
    if uid not in ADMIN_IDS:
        if uid_str not in economy_data:
            await interaction.response.send_message(f"\u274c No account. Use `/daily` to open one!", ephemeral=True)
            return
        if economy_data[uid_str]["balance"] < cost:
            await interaction.response.send_message(f"\u274c Need {coin_emoji} **{cost}** but have {coin_emoji} **{economy_data[uid_str]['balance']:,}**.", ephemeral=True)
            return
        economy_data[uid_str]["balance"] -= cost
        save_economy()
    await interaction.response.defer()
    try:
        api_key = GEMINI_API_KEY if uid in ADMIN_IDS else (GEMINI_API_KEY_FREE or GEMINI_API_KEY)
        payload = {"system_instruction":{"parts":[{"text":"You are Krisk, a friendly Discord bot. Never ask follow-up questions. Give your best answer concisely."}]},"contents":[{"parts":[{"text":question}]}],"generationConfig":{"maxOutputTokens":1000}}
        async with aiohttp.ClientSession() as s:
            async with s.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}", json=payload) as r:
                if r.status == 200:
                    d = await r.json()
                    ans = d["candidates"][0]["content"]["parts"][0]["text"][:2000]
                    if uid not in ADMIN_IDS:
                        bal = economy_data[uid_str]["balance"]
                        ans += f"\n-# {coin_emoji} -{cost} MateoCoin \u2022 Balance: {bal:,}"
                    await interaction.followup.send(ans)
                else:
                    await interaction.followup.send("AI request failed.")
    except Exception:
        await interaction.followup.send("Something went wrong.")

@app_commands.check(block_check)
@tree.command(name="imagine", description="Generate an image with AI")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(prompt="Image description", image="Upload image to edit", model="AI model")
@app_commands.choices(model=[app_commands.Choice(name="Nano Banana 2", value="gemini-3.1-flash-image-preview"), app_commands.Choice(name="Nano Banana Pro", value="gemini-3-pro-image-preview")])
async def imagine(interaction: discord.Interaction, prompt: str, image: discord.Attachment = None, model: app_commands.Choice[str] = None):
    if not GEMINI_API_KEY:
        await interaction.response.send_message("AI not configured.", ephemeral=True)
        return
    uid = interaction.user.id
    mid = model.value if model else "gemini-3.1-flash-image-preview"
    cost = 1000 if mid == "gemini-3.1-flash-image-preview" else 3000
    uid_str = str(uid)
    if uid not in ADMIN_IDS:
        if uid_str not in economy_data:
            await interaction.response.send_message("\u274c No account. Use `/daily`!", ephemeral=True)
            return
        if economy_data[uid_str]["balance"] < cost:
            await interaction.response.send_message(f"\u274c Need {coin_emoji} **{cost:,}** but have {coin_emoji} **{economy_data[uid_str]['balance']:,}**.", ephemeral=True)
            return
        economy_data[uid_str]["balance"] -= cost
        save_economy()
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as s:
            parts = [{"text": prompt}]
            if image:
                async with s.get(image.url) as ir:
                    ib = await ir.read()
                    parts.insert(0, {"inlineData": {"mimeType": image.content_type or "image/png", "data": base64.b64encode(ib).decode()}})
            async with s.post(f"https://generativelanguage.googleapis.com/v1beta/models/{mid}:generateContent?key={GEMINI_API_KEY}", json={"contents":[{"parts":parts}],"generationConfig":{"responseModalities":["TEXT","IMAGE"]}}) as r:
                if r.status == 200:
                    d = await r.json()
                    for p in d["candidates"][0]["content"]["parts"]:
                        if "inlineData" in p:
                            f = discord.File(io.BytesIO(base64.b64decode(p["inlineData"]["data"])), filename="image.png")
                            msg = ""
                            if uid not in ADMIN_IDS:
                                bal = economy_data[uid_str]["balance"]
                                msg = f"-# {coin_emoji} -{cost} MateoCoin \u2022 Balance: {bal:,}"
                            await interaction.followup.send(content=msg or None, file=f)
                            return
                    await interaction.followup.send("Could not generate image.")
                else:
                    ed = await r.json()
                    await interaction.followup.send(f"Failed: {ed.get('error',{}).get('message','Unknown')}")
    except Exception as ex:
        await interaction.followup.send(f"Error: {ex}")


# ════════════════════════════════════════════════════
#  Economy Commands
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="daily", description="Claim daily MateoCoin")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def daily(interaction: discord.Interaction):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    now = datetime.datetime.now(datetime.timezone.utc)
    first_time = uid not in economy_data
    if first_time:
        economy_data[uid] = {"balance": 0, "streak": 0, "last_daily": None}
    ud = economy_data[uid]
    last = ud.get("last_daily")
    local_now = now.astimezone(LOCAL_TZ)
    today = local_now.strftime("%Y-%m-%d")
    if last:
        last_local = datetime.datetime.fromisoformat(last).astimezone(LOCAL_TZ)
        if last_local.strftime("%Y-%m-%d") == today:
            mn = (local_now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            r = (mn - local_now).total_seconds()
            await interaction.followup.send(f"\u23f3 Already claimed! Resets in **{int(r//3600)}h {int((r%3600)//60)}m**.", ephemeral=True)
            return
        dm = (local_now.date() - last_local.date()).days
        if dm > 1:
            inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
            if inv.get("streak_saver", 0) > 0:
                inv["streak_saver"] -= 1
                streak_msg = f"\U0001f504 Streak Saver protected your **{ud['streak']}**-day streak!"
            else:
                old_s = ud["streak"]
                ud["streak"] = 0
                streak_msg = f"Lost **{old_s}**-day streak ({dm-1} days missed)."
        else:
            ud["streak"] += 1
            streak_msg = None
    else:
        ud["streak"] = 1
        streak_msg = None
    base = 1000
    bonus = ud["streak"] * 100
    total = base + bonus
    net, tax = apply_tax(total, uid)
    ud["balance"] += net
    ud["last_daily"] = now.isoformat()
    save_economy()
    title = f"\U0001f389 Welcome! Account Created!" if first_time else f"\U0001f4b0 {interaction.user.display_name}'s Daily"
    e = discord.Embed(title=title, color=0x2ECC71 if first_time else 0xFFD700)
    e.add_field(name="Base", value=f"{coin_emoji} {base:,}", inline=True)
    e.add_field(name="Streak Bonus", value=f"{coin_emoji} {bonus:,}", inline=True)
    e.add_field(name="Total", value=f"{coin_emoji} {total:,} (-{tax:,} tax = {net:,})", inline=True)
    e.add_field(name="Streak", value=f"\U0001f525 {ud['streak']} day(s)", inline=True)
    e.add_field(name="Balance", value=f"{coin_emoji} {ud['balance']:,}", inline=True)
    mn = (local_now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    r = (mn - local_now).total_seconds()
    e.add_field(name="Next Daily", value=f"{int(r//3600)}h {int((r%3600)//60)}m (midnight ET)", inline=True)
    if streak_msg:
        e.set_footer(text=streak_msg)
    await interaction.followup.send(embed=e)
    await post_transaction(interaction.guild, interaction.user.display_name, "claimed daily", net, ud["balance"])

@app_commands.check(block_check)
@tree.command(name="balance", description="Check MateoCoin balance")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Check another user", user_id="Or enter ID/username")
async def balance(interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
    await interaction.response.defer()
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except Exception:
            user = await find_user_by_name(user_id)
        if not user:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    t = user or interaction.user
    uid = str(t.id)
    if uid not in economy_data:
        msg = "\u274c No account. Use `/daily`!" if t.id == interaction.user.id else f"\u274c **{t.display_name}** has no account."
        await interaction.followup.send(msg, ephemeral=True)
        return
    ud = economy_data[uid]
    e = discord.Embed(title=f"\U0001f4b0 {t.display_name}'s Wallet", color=0xFFD700)
    e.set_thumbnail(url=t.display_avatar.url)
    e.add_field(name="Balance", value=f"{coin_emoji} {ud['balance']:,}", inline=True)
    e.add_field(name="Streak", value=f"\U0001f525 {ud['streak']} day(s)", inline=True)
    await interaction.followup.send(embed=e)

@app_commands.check(block_check)
@tree.command(name="gamble", description="Gamble MateoCoin \u2014 pick 1-10!")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(bet="Amount to bet (min 1000)", number="Pick 1-10")
async def gamble(interaction: discord.Interaction, bet: int, number: int):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    if uid not in economy_data:
        await interaction.followup.send("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    today = datetime.datetime.now(datetime.timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
    if economy_data[uid].get("gamble_date") != today:
        economy_data[uid]["gamble_date"] = today
        economy_data[uid]["gamble_count"] = 0
        inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
        inv["gamble_pass"] = 0
        save_economy()
    if interaction.user.id not in ADMIN_IDS:
        inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
        total_limit = 50 + inv.get("gamble_pass", 0)
        if economy_data[uid]["gamble_count"] >= total_limit:
            await interaction.followup.send(f"\u23f3 {total_limit}/day limit reached. Buy Gamble Pass in `/shop`!", ephemeral=True)
            return
    if bet < 1000:
        await interaction.followup.send(f"Min bet: {coin_emoji} **1,000**.", ephemeral=True)
        return
    if not 1 <= number <= 10:
        await interaction.followup.send("Pick 1-10.", ephemeral=True)
        return
    if economy_data[uid]["balance"] < bet:
        await interaction.followup.send(f"\u274c Not enough. Have {coin_emoji} **{economy_data[uid]['balance']:,}**.", ephemeral=True)
        return
    dad_uid = str(DAD_ID)
    if dad_uid not in economy_data:
        economy_data[dad_uid] = {"balance": 0, "streak": 0, "last_daily": None}
    win_num = random.randint(1, 10)
    if number == win_num:
        mult = random.randint(1, 20)
        winnings = bet * mult
        win_tax = int(winnings * 0.1)
        dad_uid = str(DAD_ID)
        if dad_uid not in economy_data:
            economy_data[dad_uid] = {"balance": 0, "streak": 0, "last_daily": None}
        if uid != dad_uid:
            economy_data[dad_uid]["balance"] += win_tax
            economy_data[uid]["balance"] += winnings - bet - win_tax
            economy_data[dad_uid]["balance"] -= (winnings - win_tax)
        else:
            economy_data[uid]["balance"] += winnings - bet
        save_economy()
        e = discord.Embed(title="\U0001f3b0 JACKPOT!", color=0x2ECC71)
        e.description = f"Number was **{win_num}** \u2014 you guessed it!"
        e.add_field(name="Won", value=f"{coin_emoji} {winnings:,} ({mult}x, -{win_tax:,} tax)", inline=True)
        e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
        await post_transaction(interaction.guild, interaction.user.display_name, f"won gamble ({mult}x)", winnings-bet, economy_data[uid]["balance"])
    else:
        economy_data[uid]["balance"] -= bet
        economy_data[dad_uid]["balance"] += bet
        save_economy()
        e = discord.Embed(title="\U0001f3b0 You lost!", color=0xFF0000)
        e.description = f"Number was **{win_num}** \u2014 you picked **{number}**."
        e.add_field(name="Lost", value=f"{coin_emoji} {bet:,}", inline=True)
        e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
        await post_transaction(interaction.guild, interaction.user.display_name, "lost gamble", -bet, economy_data[uid]["balance"])
    economy_data[uid]["gamble_count"] = economy_data[uid].get("gamble_count", 0) + 1
    total_limit = 50 + economy_data.get(uid, {}).get("inventory", {}).get("global", {}).get("gamble_pass", 0)
    remaining = max(0, total_limit - economy_data[uid]["gamble_count"])
    e.set_footer(text=f"{remaining} gambles left today")
    save_economy()
    await interaction.followup.send(embed=e)

@app_commands.check(block_check)
@tree.command(name="rob", description="Try to rob someone (45%)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to rob", user_id="Or enter ID/username")
async def rob(interaction: discord.Interaction, user: discord.User = None, user_id: str = None):
    await interaction.response.defer()
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except Exception:
            user = await find_user_by_name(user_id)
        if not user:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    if not user:
        await interaction.followup.send("Specify a user.", ephemeral=True)
        return
    uid = str(interaction.user.id)
    tid = str(user.id)
    if user.id == interaction.user.id:
        await interaction.followup.send("Can't rob yourself.", ephemeral=True)
        return
    if user.bot:
        await interaction.followup.send("Can't rob a bot.", ephemeral=True)
        return
    if uid not in economy_data:
        await interaction.followup.send("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    if tid not in economy_data:
        await interaction.followup.send(f"\u274c **{user.display_name}** has no account.", ephemeral=True)
        return
    if economy_data[tid]["balance"] <= 0:
        await interaction.followup.send(f"**{user.display_name}** has nothing to rob.", ephemeral=True)
        return
    # Anti-rob shield
    tinv = economy_data.get(tid, {}).get("inventory", {}).get("global", {})
    if tinv.get("anti_rob_until"):
        exp = datetime.datetime.fromisoformat(tinv["anti_rob_until"])
        if exp > datetime.datetime.now(datetime.timezone.utc):
            await interaction.followup.send(f"\U0001f6e1\ufe0f **{user.display_name}** has Anti-Rob Shield!", ephemeral=True)
            return
    now = time.time()
    if uid not in rob_cooldowns:
        rob_cooldowns[uid] = []
    rob_cooldowns[uid] = [t for t in rob_cooldowns[uid] if now - t < 600]
    if len(rob_cooldowns[uid]) >= 10:
        r = int(600 - (now - rob_cooldowns[uid][0]))
        await interaction.followup.send(f"\u23f3 10/10 used. Wait **{r//60}m {r%60}s**.", ephemeral=True)
        return
    rob_cooldowns[uid].append(now)
    att = len(rob_cooldowns[uid])
    reset_in = int(600 - (now - rob_cooldowns[uid][0]))
    if random.randint(1, 100) <= 45:
        pct = random.randint(10, 30) / 100
        stolen = max(1, int(economy_data[tid]["balance"] * pct))
        # Rob insurance
        ins_msg = ""
        if tinv.get("rob_insurance", 0) > 0:
            red = random.randint(50, 100) / 100
            saved = int(stolen * red)
            stolen = max(0, stolen - saved)
            tinv["rob_insurance"] -= 1
            ins_msg = f" (insurance saved {saved:,})"
        economy_data[tid]["balance"] -= stolen
        net, tax = apply_tax(stolen, uid)
        economy_data[uid]["balance"] += net
        save_economy()
        e = discord.Embed(title="\U0001f4b0 Rob Successful!", color=0x2ECC71)
        e.description = f"Stole {coin_emoji} **{stolen:,}** ({int(pct*100)}%) from **{user.display_name}**! (-{tax:,} tax){ins_msg}"
        e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
        await post_transaction(interaction.guild, interaction.user.display_name, f"robbed {user.display_name}", net, economy_data[uid]["balance"])
    else:
        fpct = random.randint(20, 40) / 100
        fine = max(1, int(economy_data[uid]["balance"] * fpct))
        economy_data[uid]["balance"] = max(0, economy_data[uid]["balance"] - fine)
        save_economy()
        e = discord.Embed(title="\U0001f694 Rob Failed!", color=0xFF0000)
        e.description = f"Caught robbing **{user.display_name}**! Lost {coin_emoji} **{fine:,}** ({int(fpct*100)}%)"
        e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
        await post_transaction(interaction.guild, interaction.user.display_name, f"failed rob on {user.display_name}", -fine, economy_data[uid]["balance"])
    e.set_footer(text=f"Rob: {att}/10 \u2022 Resets in {reset_in//60}m {reset_in%60}s")
    await interaction.followup.send(embed=e)

@app_commands.check(block_check)
@tree.command(name="work", description="Work to earn MateoCoin")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def work(interaction: discord.Interaction):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    if uid not in economy_data:
        await interaction.followup.send("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    lw = economy_data[uid].get("last_work")
    if lw:
        diff = (now - datetime.datetime.fromisoformat(lw)).total_seconds()
        if diff < 3600:
            r = 3600 - diff
            await interaction.followup.send(f"\u23f3 Work again in **{int(r//60)}m {int(r%60)}s**.", ephemeral=True)
            return
    job, lo, hi = random.choice(WORK_JOBS)
    earned = random.randint(lo, hi)
    net, tax = apply_tax(earned, uid)
    # Double work check
    inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
    dbl = False
    if inv.get("double_work_until"):
        if datetime.datetime.fromisoformat(inv["double_work_until"]) > now:
            net *= 2
            dbl = True
    economy_data[uid]["balance"] += net
    save_economy()
    dm = " (2x!)" if dbl else ""
    e = discord.Embed(title="\U0001f4bc Work Complete!", color=0x2ECC71)
    e.description = f"{job} and earned {coin_emoji} **{net:,}**! (-{tax:,} tax){dm}"
    e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
    e.set_footer(text="Work again in 1 hour")
    await interaction.followup.send(embed=e)
    await post_transaction(interaction.guild, interaction.user.display_name, "worked", net, economy_data[uid]["balance"])
    economy_data[uid]["last_work"] = now.isoformat()
    save_economy()

@app_commands.check(block_check)
@tree.command(name="fish", description="Go fishing")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def fish(interaction: discord.Interaction):
    await interaction.response.defer()
    uid = str(interaction.user.id)
    if uid not in economy_data:
        await interaction.followup.send("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
    if not inv.get("fishing_rod"):
        await interaction.followup.send(f"\u274c Need \U0001f3a3 **Fishing Rod**! Buy in `/shop`.", ephemeral=True)
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    lf = economy_data[uid].get("last_fish")
    if lf:
        diff = (now - datetime.datetime.fromisoformat(lf)).total_seconds()
        if diff < 1800:
            r = 1800 - diff
            await interaction.followup.send(f"\u23f3 Fish again in **{int(r//60)}m {int(r%60)}s**.", ephemeral=True)
            return
    fn, lo, hi = random.choice(FISH_CATCHES)
    earned = random.randint(lo, hi)
    net, tax = apply_tax(earned, uid)
    economy_data[uid]["balance"] += net
    save_economy()
    e = discord.Embed(title="\U0001f3a3 Fishing!", color=0x3498DB)
    e.description = f"Caught **{fn}** worth {coin_emoji} **{earned:,}** (-{tax:,} tax = {net:,})!"
    e.add_field(name="Balance", value=f"{coin_emoji} {economy_data[uid]['balance']:,}", inline=True)
    e.set_footer(text="Fish again in 30 min")
    await interaction.followup.send(embed=e)
    await post_transaction(interaction.guild, interaction.user.display_name, f"caught {fn}", net, economy_data[uid]["balance"])
    economy_data[uid]["last_fish"] = now.isoformat()
    save_economy()

@app_commands.check(block_check)
@tree.command(name="pay", description="Transfer MateoCoin")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="Who to pay", amount="Amount", user_id="Or ID/username", note="Note")
async def pay(interaction: discord.Interaction, user: discord.User = None, amount: int = 0, user_id: str = None, note: str = None):
    await interaction.response.defer()
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except Exception:
            user = await find_user_by_name(user_id)
        if not user:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    if not user:
        await interaction.followup.send("Specify a user.", ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.followup.send("Can't pay yourself.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.followup.send("Amount must be positive.", ephemeral=True)
        return
    sid = str(interaction.user.id)
    rid = str(user.id)
    if sid not in economy_data:
        await interaction.followup.send("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    if rid not in economy_data:
        await interaction.followup.send(f"\u274c **{user.display_name}** has no account.", ephemeral=True)
        return
    tax = int(amount * 0.1) if sid != str(DAD_ID) else 0
    total = amount + tax
    if economy_data[sid]["balance"] < total:
        await interaction.followup.send(f"Need {coin_emoji} **{total:,}** but have **{economy_data[sid]['balance']:,}**.", ephemeral=True)
        return
    dad_uid = str(DAD_ID)
    if dad_uid not in economy_data:
        economy_data[dad_uid] = {"balance": 0, "streak": 0, "last_daily": None}
    economy_data[sid]["balance"] -= total
    if sid != dad_uid and tax > 0:
        economy_data[dad_uid]["balance"] += tax
    save_economy()
    # Send pending transfer DM to receiver
    transfer_id = str(int(time.time() * 1000))
    try:
        ne = discord.Embed(title="\U0001f4b8 Incoming Transfer", color=0xFFD700)
        ne.add_field(name="From", value=f"**{interaction.user.display_name}** ({interaction.user.name})", inline=True)
        ne.add_field(name="Amount", value=f"{coin_emoji} {amount:,}", inline=True)
        if note:
            ne.add_field(name="Note", value=note, inline=False)
        ne.set_footer(text="Click Accept to receive or Decline to refund. Expires in 24h.")
        view = PayView(transfer_id)
        dm_msg = await user.send(embed=ne, view=view)
        pending_transfers[transfer_id] = {"sender_id": sid, "receiver_id": rid, "amount": amount, "tax": tax, "time": time.time(), "note": note}
        e = discord.Embed(title="\U0001f4b8 Transfer Pending", color=0xFFD700)
        e.add_field(name="To", value=user.mention, inline=True)
        e.add_field(name="Amount", value=f"{coin_emoji} {amount:,} (+{tax:,} tax = {total:,})", inline=True)
        e.add_field(name="Status", value="\u23f3 Waiting for recipient to accept...", inline=False)
        if note:
            e.add_field(name="Note", value=note, inline=False)
        await interaction.followup.send(embed=e)
        await post_transaction(interaction.guild, interaction.user.display_name, f"sent {user.display_name} (pending)", -total, economy_data[sid]["balance"])
    except discord.Forbidden:
        # Can't DM, refund
        economy_data[sid]["balance"] += total
        if sid != dad_uid and tax > 0:
            economy_data[dad_uid]["balance"] -= tax
        save_economy()
        await interaction.followup.send(f"\u274c Can't DM **{user.display_name}**. Transfer cancelled and refunded.", ephemeral=True)

@app_commands.check(block_check)
@tree.command(name="forbes", description="MateoCoin Forbes List")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def leaderboard(interaction: discord.Interaction):
    if not economy_data:
        await interaction.response.send_message("No one has MateoCoin yet!", ephemeral=True)
        return
    await interaction.response.defer()
    top = sorted(economy_data.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:100]
    lines = []
    medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
    for i, (uid, data) in enumerate(top):
        if uid in user_cache:
            n = user_cache[uid]
        else:
            try:
                u = await client.fetch_user(int(uid))
                n = f"{u.display_name} ({u.name})"
                user_cache[uid] = n
            except Exception:
                n = "Unknown"
        m = medals[i] if i < 3 else f"**#{i+1}**"
        lines.append(f"{m} **{n}** \u2014 {coin_emoji} {data.get('balance',0):,}")
    desc = "\n".join(lines)
    if len(desc) > 4000:
        desc = desc[:4000] + "\n..."
    e = discord.Embed(title="\U0001f3c6 MateoCoin Forbes List", description=desc, color=0xFFD700)
    e.set_footer(text=f"{len(lines)} users \u2022 Use /daily to earn MateoCoin!")
    await interaction.followup.send(embed=e)


# ════════════════════════════════════════════════════
#  Shop & Backpack Commands
# ════════════════════════════════════════════════════

@app_commands.check(block_check)
@tree.command(name="shop", description="Browse the MateoCoin shop")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def shop(interaction: discord.Interaction):
    e = discord.Embed(title="\U0001f6d2 MateoCoin Shop", description="Click a button to buy! All prices +10% tax.", color=0xFFD700)
    stored = ""
    instant = ""
    perm = ""
    shop_uid = str(interaction.user.id)
    shop_inv = economy_data.get(shop_uid, {}).get("inventory", {}).get("global", {})
    shop_today = datetime.datetime.now(datetime.timezone.utc).astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
    for k, item in SHOP_ITEMS.items():
        t = int(item["price"] * 0.1)
        sold_out = ""
        if k == "fishing_rod" and shop_inv.get("fishing_rod"):
            sold_out = " ✅ Owned"
        if k == "mystery_box" and shop_inv.get("mystery_box_date") == shop_today:
            sold_out = " ⏳ Claimed today"
        line = f"**{item['name']}** — {coin_emoji} {item['price']+t:,}{sold_out}\n{item['desc']}\n"
        if item["type"] == "instant":
            instant += line
        elif item["type"] == "permanent":
            perm += line
        else:
            stored += line
    if stored:
        e.add_field(name="\U0001f4e6 Activatable Items", value=stored.strip(), inline=False)
    if instant:
        e.add_field(name="\u26a1 Instant Items", value=instant.strip(), inline=False)
    if perm:
        e.add_field(name="\u2b50 Permanent Items", value=perm.strip(), inline=False)
    uid = str(interaction.user.id)
    await interaction.response.send_message(embed=e, view=ShopView(uid), ephemeral=True)

@app_commands.check(block_check)
@tree.command(name="backpack", description="View your items")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def backpack(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid not in economy_data:
        await interaction.response.send_message("\u274c No account. Use `/daily`!", ephemeral=True)
        return
    inv = economy_data.get(uid, {}).get("inventory", {}).get("global", {})
    if not inv:
        await interaction.response.send_message("\U0001f392 Empty! Use `/shop` to browse.", ephemeral=True)
        return
    e = discord.Embed(title=f"\U0001f392 {interaction.user.display_name}'s Backpack", color=0x5865F2)
    now = datetime.datetime.now(datetime.timezone.utc)
    has_items = False
    for key, label in [("gamble_pass_stored","\U0001f3b0 Gamble Pass"),("double_work_stored","\U0001f4bc Double Work"),("rob_insurance_stored","\U0001f6e1\ufe0f Rob Insurance"),("anti_rob_stored","\U0001f6e1\ufe0f Anti-Rob Shield"),("streak_saver_SKIP","\U0001f504 SKIP")]:
        if inv.get(key, 0) > 0:
            e.add_field(name=f"{label} (stored)", value=f"x{inv[key]}", inline=False)
            has_items = True
    if inv.get("gamble_pass", 0) > 0:
        e.add_field(name="\U0001f3b0 Gamble Pass (active)", value=f"{inv['gamble_pass']} attempts left", inline=False)
        has_items = True
    if inv.get("double_work_until"):
        exp = datetime.datetime.fromisoformat(inv["double_work_until"])
        if exp > now:
            r = (exp - now).total_seconds()
            e.add_field(name="\U0001f4bc Double Work (active)", value=f"{int(r//3600)}h {int((r%3600)//60)}m left", inline=False)
            has_items = True
    if inv.get("rob_insurance", 0) > 0:
        e.add_field(name="\U0001f6e1\ufe0f Rob Insurance (active)", value=f"{inv['rob_insurance']} uses left", inline=False)
        has_items = True
    if inv.get("anti_rob_until"):
        exp = datetime.datetime.fromisoformat(inv["anti_rob_until"])
        if exp > now:
            r = (exp - now).total_seconds()
            e.add_field(name="\U0001f6e1\ufe0f Anti-Rob Shield (active)", value=f"{int(r//3600)}h {int((r%3600)//60)}m left", inline=False)
            has_items = True
    if inv.get("streak_saver", 0) > 0:
        e.add_field(name="\U0001f504 Streak Saver", value=f"x{inv['streak_saver']} (auto-activates when you miss a day)", inline=False)
        has_items = True
    if inv.get("fishing_rod"):
        e.add_field(name="\U0001f3a3 Fishing Rod", value="Permanent", inline=False)
        has_items = True
    if not has_items:
        await interaction.response.send_message("\U0001f392 Empty! Use `/shop` to browse.", ephemeral=True)
        return
    view = build_backpack_view(uid)
    await interaction.response.send_message(embed=e, view=view)


# ════════════════════════════════════════════════════
#  Admin Economy
# ════════════════════════════════════════════════════

@tree.command(name="setbalance", description="Set user balance")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User", amount="Amount", note="Note")
async def setbalance(interaction: discord.Interaction, user: discord.User, amount: int, note: str = None):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    uid = str(user.id)
    if uid not in economy_data:
        economy_data[uid] = {"balance": 0, "streak": 0, "last_daily": None}
    economy_data[uid]["balance"] = amount
    save_economy()
    await interaction.response.send_message(f"\u2705 Set **{user.display_name}** to {coin_emoji} **{amount:,}**.", ephemeral=True)
    try:
        e = discord.Embed(title=f"{coin_emoji} Balance Updated", color=0xFFD700)
        e.add_field(name="New Balance", value=f"{coin_emoji} {amount:,}", inline=True)
        if note:
            e.add_field(name="Note", value=note, inline=False)
        await user.send(embed=e)
    except Exception:
        pass

@tree.command(name="give", description="Give MateoCoin")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User", amount="Amount", note="Note")
async def give(interaction: discord.Interaction, user: discord.User, amount: int, note: str = None):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    if amount <= 0:
        await interaction.response.send_message("Must be positive.", ephemeral=True)
        return
    uid = str(user.id)
    if uid not in economy_data:
        economy_data[uid] = {"balance": 0, "streak": 0, "last_daily": None}
    economy_data[uid]["balance"] += amount
    save_economy()
    await interaction.response.send_message(f"\u2705 Gave {coin_emoji} **{amount:,}** to **{user.display_name}**. Balance: {coin_emoji} **{economy_data[uid]['balance']:,}**", ephemeral=True)
    try:
        e = discord.Embed(title=f"\U0001f381 MateoCoin Received", color=0x2ECC71)
        e.add_field(name="Amount", value=f"{coin_emoji} {amount:,}", inline=True)
        if note:
            e.add_field(name="Note", value=note, inline=False)
        await user.send(embed=e)
    except Exception:
        pass


# ════════════════════════════════════════════════════
#  Admin Commands
# ════════════════════════════════════════════════════

@tree.command(name="ban", description="Ban a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User", reason="Reason", days="Duration (0=perm)")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str = "No reason", days: int = 0):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        await interaction.guild.ban(user, reason=f"{reason} | {interaction.user.name}")
        try:
            e = discord.Embed(title="\U0001f528 Banned", color=0xFF0000)
            e.add_field(name="Server", value=interaction.guild.name, inline=True)
            e.add_field(name="Reason", value=reason, inline=True)
            e.add_field(name="Duration", value=f"{days}d" if days > 0 else "Permanent", inline=True)
            await user.send(embed=e)
        except Exception:
            pass
        ce = discord.Embed(title="\U0001f528 User Banned", color=0xFF0000)
        ce.add_field(name="User", value=f"{user.mention} ({user.name})", inline=True)
        ce.add_field(name="Reason", value=reason, inline=True)
        await interaction.response.send_message(embed=ce)
        if days > 0:
            await asyncio.sleep(days * 86400)
            try:
                await interaction.guild.unban(user)
            except Exception:
                pass
    except discord.Forbidden:
        await interaction.response.send_message("\u274c No permission to ban.", ephemeral=True)

async def unban_ac(interaction, current):
    if not interaction.guild:
        return []
    try:
        return [app_commands.Choice(name=f"{e.user.name} ({e.user.id})", value=str(e.user.id)) for e in [entry async for entry in interaction.guild.bans()] if current.lower() in e.user.name.lower() or current in str(e.user.id)][:25]
    except Exception:
        return []

@tree.command(name="unban", description="Unban a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User to unban")
@app_commands.autocomplete(user=unban_ac)
async def unban(interaction: discord.Interaction, user: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer()
    bl = [e async for e in interaction.guild.bans()]
    if not bl:
        await interaction.followup.send("No banned users.")
        return
    if not user:
        desc = "\n".join(f"\u2022 **{e.user.name}** (`{e.user.id}`)" for e in bl[:20])
        await interaction.followup.send(embed=discord.Embed(title="Banned Users", description=desc, color=0xFF6B6B))
        return
    t = next((e.user for e in bl if user.lower() in e.user.name.lower() or user == str(e.user.id)), None)
    if t:
        await interaction.guild.unban(t)
        await interaction.followup.send(f"\u2705 **{t.name}** unbanned!")
    else:
        await interaction.followup.send("User not found in ban list.")

@tree.command(name="kick", description="Kick a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        await user.kick(reason=f"{reason} | {interaction.user.name}")
        await interaction.response.send_message(f"\U0001f462 **{user.display_name}** kicked. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("\u274c No permission.", ephemeral=True)

@tree.command(name="mute", description="Timeout a user")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User", minutes="Duration (1-40320)", reason="Reason")
async def mute(interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str = "No reason"):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        await user.timeout(datetime.timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"\U0001f507 **{user.display_name}** muted {minutes}m. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("\u274c No permission.", ephemeral=True)

@tree.command(name="unmute", description="Remove timeout")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    try:
        await user.timeout(None)
        await interaction.response.send_message(f"\U0001f50a **{user.display_name}** unmuted!")
    except discord.Forbidden:
        await interaction.response.send_message("\u274c No permission.", ephemeral=True)

@tree.command(name="purge", description="Delete messages")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(amount="Number (1-100)")
async def purge(interaction: discord.Interaction, amount: int = 10):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        d = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"\U0001f5d1\ufe0f Deleted **{len(d)}** messages!", ephemeral=True)
    except Exception:
        await interaction.followup.send("\u274c Failed.", ephemeral=True)

@tree.command(name="announce", description="Send announcement to channel")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(channel="Channel", title="Title", message="Message")
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    e = discord.Embed(title=f"\U0001f4e2 {title}", description=message, color=0x5865F2, timestamp=datetime.datetime.now(datetime.timezone.utc))
    await channel.send(embed=e)
    await interaction.response.send_message(f"\u2705 Sent to {channel.mention}!", ephemeral=True)

@tree.command(name="announcement", description="DM announcement to user")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User", message="Message", user_id="Or ID/username")
async def announcement(interaction: discord.Interaction, user: discord.User = None, message: str = "", user_id: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not user and user_id:
        try:
            user = await client.fetch_user(int(user_id))
        except Exception:
            user = await find_user_by_name(user_id)
    if not user:
        await interaction.followup.send("Specify a user.", ephemeral=True)
        return
    try:
        e = discord.Embed(title="\U0001f4e2 Developer Announcement", description=message, color=0x5865F2)
        await user.send(embed=e)
        await interaction.followup.send(f"\u2705 Sent to **{user.name}**!", ephemeral=True)
    except Exception:
        await interaction.followup.send("\u274c Cannot DM.", ephemeral=True)

@tree.command(name="block", description="Block user from bot")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User")
async def block(interaction: discord.Interaction, user: discord.User):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    if user.id in blocked_users:
        await interaction.response.send_message("Already blocked.", ephemeral=True)
        return
    blocked_users.append(user.id)
    save_blocked()
    await interaction.response.send_message(f"\U0001f6ab **{user.name}** blocked.", ephemeral=True)

async def unblock_ac(interaction, current):
    r = []
    for uid in blocked_users[:25]:
        if str(uid) in user_cache:
            n = f"{user_cache[str(uid)]} ({uid})"
        else:
            try:
                u = await client.fetch_user(uid)
                n = f"{u.name} ({uid})"
            except Exception:
                n = f"Unknown ({uid})"
        if current.lower() in n.lower():
            r.append(app_commands.Choice(name=n, value=str(uid)))
    return r[:25]

@tree.command(name="unblock", description="Unblock user")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user="User")
@app_commands.autocomplete(user=unblock_ac)
async def unblock(interaction: discord.Interaction, user: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    if not user:
        if not blocked_users:
            await interaction.response.send_message("No blocked users.", ephemeral=True)
            return
        lines = []
        for uid in blocked_users:
            try:
                u = await client.fetch_user(uid)
                lines.append(f"\u2022 **{u.name}** (`{uid}`)")
            except Exception:
                lines.append(f"\u2022 Unknown (`{uid}`)")
        await interaction.response.send_message(embed=discord.Embed(title="Blocked Users", description="\n".join(lines), color=0xFF6B6B), ephemeral=True)
        return
    uid = int(user)
    if uid not in blocked_users:
        await interaction.response.send_message("Not blocked.", ephemeral=True)
        return
    blocked_users.remove(uid)
    save_blocked()
    try:
        u = await client.fetch_user(uid)
        n = u.name
    except Exception:
        n = str(uid)
    await interaction.response.send_message(f"\u2705 **{n}** unblocked.", ephemeral=True)

@tree.command(name="warn", description="Warn user (escalating)")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User", reason="Reason")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason"):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    gid = str(interaction.guild.id)
    uid = str(user.id)
    if gid not in warnings_data:
        warnings_data[gid] = {}
    warnings_data[gid][uid] = warnings_data[gid].get(uid, 0) + 1
    c = warnings_data[gid][uid]
    save_warnings()
    try:
        if c >= 6:
            await interaction.guild.ban(user, reason=f"6 warnings. Last: {reason}")
            warnings_data[gid].pop(uid, None)
            save_warnings()
            await interaction.response.send_message(f"\U0001f528 **{user.display_name}** banned (6/6). Reason: {reason}")
        elif c >= 4:
            await user.kick(reason=f"Warning {c}/6: {reason}")
            await interaction.response.send_message(f"\U0001f462 **{user.display_name}** kicked ({c}/6). Reason: {reason}")
        elif c >= 2:
            await user.timeout(datetime.timedelta(minutes=10), reason=f"Warning {c}/6: {reason}")
            await interaction.response.send_message(f"\U0001f507 **{user.display_name}** muted 10m ({c}/6). Reason: {reason}")
        else:
            await interaction.response.send_message(f"\u26a0\ufe0f **{user.display_name}** warned ({c}/6). Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("\u274c No permission.", ephemeral=True)

@tree.command(name="warnings", description="Check warnings")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User")
async def warnings(interaction: discord.Interaction, user: discord.Member):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    c = warnings_data.get(str(interaction.guild.id), {}).get(str(user.id), 0)
    await interaction.response.send_message(f"**{user.display_name}**: **{c}/6** warnings.", ephemeral=True)

@tree.command(name="clearwarnings", description="Clear warnings")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
@app_commands.describe(user="User")
async def clearwarnings(interaction: discord.Interaction, user: discord.Member):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    gid = str(interaction.guild.id)
    uid = str(user.id)
    if gid in warnings_data and uid in warnings_data[gid]:
        warnings_data[gid].pop(uid)
        save_warnings()
    await interaction.response.send_message(f"\u2705 Cleared warnings for **{user.display_name}**.", ephemeral=True)

@tree.command(name="logs", description="View message logs")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(user_id="Filter by sender ID", amount="Number of logs")
async def logs(interaction: discord.Interaction, user_id: str = None, amount: int = 10):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    all_logs = _load(LOG_FILE, list)
    if user_id:
        all_logs = [l for l in all_logs if str(l["sender_id"]) == user_id]
    recent = all_logs[-amount:]
    if not recent:
        await interaction.response.send_message("No logs.", ephemeral=True)
        return
    lines = [f"`{l['time']}`\n**{l['sender_name']}** \u2192 **{l['recipient_name']}**\n{l['text'][:80]}" for l in recent]
    desc = "\n\n".join(lines)[:4000]
    await interaction.response.send_message(embed=discord.Embed(title="Logs", description=desc, color=0x5865F2).set_footer(text=f"{len(recent)}/{len(all_logs)}"), ephemeral=True)

async def server_ac(interaction, current):
    return [app_commands.Choice(name=f"{g.name}", value=str(g.id)) for g in client.guilds if current.lower() in g.name.lower()][:25]

@tree.command(name="getinvite", description="Get server invite")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.describe(server_id="Server")
@app_commands.autocomplete(server_id=server_ac)
async def getinvite(interaction: discord.Interaction, server_id: str = None):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    if not server_id:
        sl = "\n".join(f"**{g.name}** \u2014 `{g.id}`" for g in client.guilds)
        await interaction.response.send_message(embed=discord.Embed(title="Servers", description=sl, color=0x5865F2), ephemeral=True)
        return
    g = client.get_guild(int(server_id))
    if not g:
        await interaction.response.send_message("Not found.", ephemeral=True)
        return
    try:
        inv = await g.text_channels[0].create_invite(max_age=86400, max_uses=1)
        await interaction.response.send_message(f"**{g.name}**: {inv.url}", ephemeral=True)
    except Exception:
        await interaction.response.send_message("Can't create invite.", ephemeral=True)

@tree.command(name="leave", description="Leave server")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
async def leave(interaction: discord.Interaction):
    if not is_dad(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    n = interaction.guild.name
    await interaction.response.send_message(f"\U0001f44b Leaving **{n}**...")
    await interaction.guild.leave()


if __name__ == "__main__":
    client.run(TOKEN)
