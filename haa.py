# ================================================
# ULTIMATE PINOY MOD BOT v2.0 - FULLY FIXED
# Uses os.getenv("DISCORD_TOKEN") SAFELY
# Works on Pydroid 3, Termux, Replit, VPS
# ================================================

import discord
from discord.ext import commands
import json
import os
import random
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
import asyncio
import time

# ==========================================
# TOKEN - SAFE os.getenv() WITH ERROR CHECK
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("\n" + "═" * 60)
    print("   ERROR: DISCORD_TOKEN NOT FOUND!")
    print("")
    print("   HOW TO FIX:")
    print("   1. Open Terminal in Pydroid 3 / Termux")
    print("   2. Run this command (replace with your real token):")
    print("")
    print('   export DISCORD_TOKEN="YOUR_REAL_BOT_TOKEN_HERE"')
    print("")
    print("   3. Then run this script again.")
    print("═" * 60 + "\n")
    exit(1)

PREFIX = "!"
COOLDOWN_TIME = 60

# ==========================================
# 24/7 KEEP-ALIVE SERVER
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Ultimate Pinoy Mod Bot is ALIVE & READY! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# BOT SETUP
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.presences = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# Databases
warnings_file = "warnings.json"
levels_file = "levels.json"
money_file = "money.json"
xp_cooldowns = {}

warnings_db = {}
levels_db = {}
money_db = {}

def load_json(file, default={}):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default
    return default

warnings_db = load_json(warnings_file)
levels_db = load_json(levels_file)
money_db = load_json(money_file)

def save_data():
    with open(warnings_file, "w", encoding="utf-8") as f:
        json.dump(warnings_db, f, indent=4, ensure_ascii=False)
    with open(levels_file, "w", encoding="utf-8") as f:
        json.dump(levels_db, f, indent=4, ensure_ascii=False)
    with open(money_file, "w", encoding="utf-8") as f:
        json.dump(money_db, f, indent=4, ensure_ascii=False)

# Helper Functions
def create_progress_bar(current, total, length=10):
    percent = min(current / total, 1.0)
    filled = int(length * percent)
    return f"[{('█' * filled) + ('░' * (length - filled))}] {int(percent * 100)}%"

async def process_xp(user_id, channel, member):
    leveled_up = False
    while True:
        current_lvl = levels_db[user_id]["level"]
        xp_needed = current_lvl * 100
        if levels_db[user_id]["xp"] >= xp_needed:
            levels_db[user_id]["xp"] -= xp_needed
            levels_db[user_id]["level"] += 1
            leveled_up = True
        else:
            break
    if leveled_up:
        embed = discord.Embed(title="LEVEL UP!", description=f"Congrats {member.mention}!", color=0xFFD700)
        embed.add_field(name="New Level", value=f"**{levels_db[user_id]['level']}**", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)
    save_data()

async def create_muted_role(guild):
    role = discord.utils.get(guild.roles, name="Muted")
    if not role:
        role = await guild.create_role(name="Muted", reason="Auto-created by Ultimate Pinoy Mod Bot")
        for channel in guild.channels:
            try:
                await channel.set_permissions(role, send_messages=False, speak=False, add_reactions=False)
            except:
                pass
    return role

# ==========================================
# EVENTS
# ==========================================
@bot.event
async def on_ready():
    bot.uptime = datetime.now()
    print(f"\n┌{'─'*56}┐")
    print(f"  ULTIMATE PINOY MOD BOT IS NOW ONLINE!")
    print(f"  Logged in as: {bot.user}")
    print(f"  Serving {len(bot.guilds)} servers | {len(bot.users)} users")
    print(f"  Prefix: {PREFIX} | Use {PREFIX}help")
    print(f"└{'─'*56}┘\n")
    await bot.change_presence(activity=discord.Game(name=f"Pinoy Power | {PREFIX}help"))

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    now = time.time()

    # XP System
    if user_id not in xp_cooldowns or now > xp_cooldowns[user_id]:
        if user_id not in levels_db:
            levels_db[user_id] = {"xp": 0, "level": 1}
        levels_db[user_id]["xp"] += random.randint(10, 20)
        xp_cooldowns[user_id] = now + COOLDOWN_TIME
        await process_xp(user_id, message.channel, message.author)

    await bot.process_commands(message)

# ==========================================
# MODERATION COMMANDS
# ==========================================
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason given"):
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        return await ctx.send("You cannot warn someone with higher/equal role!")
    user_id = str(member.id)
    if user_id not in warnings_db:
        warnings_db[user_id] = {"count": 0, "reasons": []}
    warnings_db[user_id]["count"] += 1
    warnings_db[user_id]["reasons"].append(f"{reason} - {datetime.now().strftime('%Y-%m-%d')}")
    save_data()

    embed = discord.Embed(title="Warning Issued", color=0xFF0000)
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=warnings_db[user_id]["count"], inline=False)
    await ctx.send(embed=embed)

    count = warnings_db[user_id]["count"]
    if count == 3:
        role = await create_muted_role(ctx.guild)
        await member.add_roles(role)
        await ctx.send(f"{member.mention} has been **auto-muted** (3 warnings)")
    elif count == 5:
        try:
            await member.kick(reason="5 warnings reached")
            await ctx.send(f"{member.mention} has been **auto-kicked** (5 warnings)")
        except:
            await ctx.send("Auto-kick failed (hierarchy)")
    elif count >= 7:
        try:
            await member.ban(reason="7+ warnings")
            await ctx.send(f"{member.mention} has been **permanently banned** (7+ warnings)")
        except:
            await ctx.send("Auto-ban failed")

@bot.command(aliases=["unwarn"])
@commands.has_permissions(manage_messages=True)
async def removewarn(ctx, member: discord.Member):
    user_id = str(member.id)
    if user_id in warnings_db and warnings_db[user_id]["count"] > 0:
        warnings_db[user_id]["count"] -= 1
        warnings_db[user_id]["reasons"].pop()
        save_data()
        await ctx.send(f"One warning removed from {member.mention}")
    else:
        await ctx.send("This user has no warnings.")

@bot.command(aliases=["warns"])
async def checkwarns(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    data = warnings_db.get(user_id, {"count": 0, "reasons": []})
    embed = discord.Embed(title=f"Warnings: {member}", color=0xFFA500)
    embed.add_field(name="Total", value=data["count"], inline=True)
    reasons = "\n".join(data["reasons"][-5:]) if data["reasons"] else "No warnings!"
    embed.add_field(name="Recent Reasons", value=reasons, inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    user_id = str(member.id)
    if user_id in warnings_db:
        del warnings_db[user_id]
        save_data()
        await ctx.send(f"All warnings cleared for {member.mention}")
    else:
        await ctx.send("No warnings to clear.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def mute(ctx, member: discord.Member):
    role = await create_muted_role(ctx.guild)
    await member.add_roles(role)
    await ctx.send(f"{member.mention} has been muted.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"{member.mention} has been unmuted.")
    else:
        await ctx.send("User is not muted.")

@bot.command(aliases=['tempmute', 'tm'])
@commands.has_permissions(manage_roles=True)
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason"):
    if minutes > 40320:  # 28 days max
        return await ctx.send("Max timeout is 28 days!")
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        await ctx.send(f"{member.mention} timed out for **{minutes} minutes**.")
    except:
        role = await create_muted_role(ctx.guild)
        await member.add_roles(role)
        await ctx.send(f"Role-muted {member.mention} for {minutes} minutes (fallback).")
        await asyncio.sleep(minutes * 60)
        await member.remove_roles(role)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason"):
    await member.kick(reason=reason)
    await ctx.send(f"{member.mention} has been kicked.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"{member.mention} has been banned.")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(f"{user} has been unbanned.")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {amount} messages.", delete_after=3)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def slowmode(ctx, seconds: int):
    if seconds > 21600:
        return await ctx.send("Max 6 hours!")
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"Slowmode set to {seconds}s")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("Channel locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("Channel unlocked.")

# ==========================================
# ECONOMY & LEVELING
# ==========================================
@bot.command(aliases=["rank", "level"])
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    if user_id not in levels_db:
        levels_db[user_id] = {"xp": 0, "level": 1}
        save_data()
    xp = levels_db[user_id]["xp"]
    lvl = levels_db[user_id]["level"]
    needed = lvl * 100
    bar = create_progress_bar(xp, needed)
    embed = discord.Embed(title=f"{member.display_name}'s Rank", color=0x9B59B6)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=lvl, inline=True)
    embed.add_field(name="XP", value=f"{xp}/{needed}", inline=True)
    embed.add_field(name="Progress", value=bar, inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def leaderboard(ctx):
    top = sorted(levels_db.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
    desc = ""
    for i, (uid, data) in enumerate(top, 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else "Unknown User"
        desc += f"{i}. **{name}** — Level {data['level']} ({data['xp']} XP)\n"
    embed = discord.Embed(title="Top 10 Players", description=desc or "No data yet!", color=0xFFD700)
    await ctx.send(embed=embed)

@bot.command(aliases=['bal'])
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)
    money_db[user_id] = money_db.get(user_id, 0)
    await ctx.send(f"{member.display_name} has **{money_db[user_id]}** coins")

@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx):
    user_id = str(ctx.author.id)
    money_db[user_id] = money_db.get(user_id, 0) + 500
    save_data()
    await ctx.send("You claimed your **500 coins** daily reward!")

@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work(ctx):
    earnings = random.randint(100, 400)
    user_id = str(ctx.author.id)
    money_db[user_id] = money_db.get(user_id, 0) + earnings
    save_data()
    jobs = ["coding", "driving Grab", "selling siomai", "streaming"]
    await ctx.send(f"You worked as a **{random.choice(jobs)}** and earned **{earnings}** coins!")

@bot.command()
async def transfer(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        return await ctx.send("Amount must be positive!")
    sender = str(ctx.author.id)
    receiver = str(member.id)
    if money_db.get(sender, 0) < amount:
        return await ctx.send("Not enough coins!")
    money_db[sender] = money_db.get(sender, 0) - amount
    money_db[receiver] = money_db.get(receiver, 0) + amount
    save_data()
    await ctx.send(f"Transferred **{amount}** coins to {member.mention}")

# ==========================================
# FUN COMMANDS
# ==========================================
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}'s Avatar", color=0x3498DB)
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def hug(ctx, member: discord.Member):
    await ctx.send(f"{ctx.author.mention} hugs {member.mention} tightly!")

@bot.command()
async def slap(ctx, member: discord.Member):
    await ctx.send(f"{ctx.author.mention} slaps {member.mention} across the face!")

@bot.command()
async def coinflip(ctx):
    await ctx.send(f"**{random.choice(['HEADS', 'TAILS'])}!**")

@bot.command()
async def dice(ctx, sides: int = 6):
    await ctx.send(f"Rolled a **{random.randint(1, sides)}** on a d{sides}!")

# ==========================================
# HELP COMMAND
# ==========================================
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Ultimate Pinoy Mod Bot", color=0x00FF00)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="Moderation", value="`warn mute kick ban purge slowmode lock unlock`", inline=False)
    embed.add_field(name="Economy", value="`bal daily work transfer rank leaderboard`", inline=False)
    embed.add_field(name="Fun", value="`avatar hug slap coinflip dice`", inline=False)
    embed.add_field(name="Info", value=f"Prefix: `{PREFIX}` • {len(bot.commands)} commands", inline=False)
    embed.set_footer(text="Made with ❤️ for Pinoy Discord Servers")
    await ctx.send(embed=embed)

# ==========================================
# START BOT
# ==========================================
if __name__ == "__main__":
    print("Starting 24/7 keep-alive server...")
    keep_alive()
    print("Logging in to Discord...")
    bot.run(TOKEN)