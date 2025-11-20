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
import sys
import operator

# ==========================================
# ⚠️ CONFIGURATION
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("FATAL ERROR: DISCORD_TOKEN environment variable not found. Please set it and restart.")
    sys.exit()

DEFAULT_PREFIX = "!"

# ==========================================
# 🌐 24/7 UPTIME SERVER
# ==========================================
app = Flask('')
@app.route('/')
def home():
    return "I'm alive! The QueenAI Bot is running 24/7."
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# 🤖 BOT SETUP
# ==========================================
def get_prefix(bot, message):
    if not message.guild:
        return DEFAULT_PREFIX
    guild_config = get_guild_data(config_db, message.guild.id)
    return guild_config.get("prefix", DEFAULT_PREFIX)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# === DATABASE HANDLING (GUILD-SPECIFIC) ===
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f: return json.load(f)
        except (json.JSONDecodeError, IOError): return {}
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e: print(f"Error saving {filename}: {e}")

warnings_db = load_json("warnings.json")
levels_db = load_json("levels.json")
money_db = load_json("money.json")
config_db = load_json("config.json")
xp_cooldowns = {}

def get_guild_data(db, guild_id):
    guild_id = str(guild_id)
    if guild_id not in db: db[guild_id] = {}
    return db[guild_id]

# === PERMISSION CHECKS ===
def is_moderator():
    async def predicate(ctx):
        if ctx.author == ctx.guild.owner: return True
        guild_config = get_guild_data(config_db, ctx.guild.id)
        admin_role_id = guild_config.get("admin_role")
        mod_role_id = guild_config.get("mod_role")
        if not mod_role_id and not admin_role_id:
            raise commands.CheckFailure(f"Neither Moderator nor Admin roles are set. An admin must use `{get_prefix(bot, ctx.message)}setmodrole`.")
        
        mod_role = ctx.guild.get_role(mod_role_id) if mod_role_id else None
        admin_role = ctx.guild.get_role(admin_role_id) if admin_role_id else None
        
        if (mod_role and mod_role in ctx.author.roles) or (admin_role and admin_role in ctx.author.roles):
            return True
        raise commands.CheckFailure("You need the server's configured Moderator or Admin role to use this command.")
    return commands.check(predicate)

def is_admin():
    async def predicate(ctx):
        if ctx.author == ctx.guild.owner: return True
        guild_config = get_guild_data(config_db, ctx.guild.id)
        admin_role_id = guild_config.get("admin_role")
        if not admin_role_id:
            raise commands.CheckFailure(f"The Admin role is not set. The server owner must use `{get_prefix(bot, ctx.message)}setadminrole`.")
        
        admin_role = ctx.guild.get_role(admin_role_id)
        if admin_role and admin_role in ctx.author.roles:
            return True
        raise commands.CheckFailure("You need the server's configured Admin role to use this command.")
    return commands.check(predicate)

# === HELPER FUNCTIONS ===
def create_progress_bar(current, total, length=10):
    if total == 0: total = 1
    percent = min(current / total, 1.0)
    filled_length = int(length * percent)
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"[{bar}] {int(percent * 100)}%"

async def process_xp(guild_id, user_id, channel, member):
    guild_levels = get_guild_data(levels_db, guild_id)
    user_data = guild_levels.get(user_id, {"xp": 0, "level": 1})
    
    leveled_up = False
    while user_data["xp"] >= (user_data["level"] * 100):
        user_data["xp"] -= user_data["level"] * 100
        user_data["level"] += 1
        leveled_up = True
    
    guild_levels[user_id] = user_data
    if leveled_up:
        embed = discord.Embed(title="🎉 LEVEL UP!", description=f"Congrats {member.mention}!", color=discord.Color.gold())
        embed.add_field(name="New Level", value=f"**{user_data['level']}**")
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)
    save_json("levels.json", levels_db)

async def create_muted_role(guild):
    role = discord.utils.get(guild.roles, name="Muted")
    if not role:
        try:
            role = await guild.create_role(name="Muted", reason="Bot Auto-Create Muted Role")
            for channel in guild.text_channels: await channel.set_permissions(role, send_messages=False)
        except discord.Forbidden: return None
    return role

def safe_math_eval(expr):
    ops = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': operator.truediv, '^': operator.pow}
    expr = expr.replace(' ', '').replace('**', '^')
    if not all(c in '0123456789+-*/^().' for c in expr): raise ValueError("Invalid characters")
    import re
    tokens = re.findall(r"(\d+\.?\d*|[\+\-\*\/\^])", expr)
    if not tokens or len(tokens) % 2 == 0: raise ValueError("Invalid format")
    result = float(tokens[0])
    for i in range(1, len(tokens), 2): result = ops[tokens[i]](result, float(tokens[i+1]))
    return result

# ==========================================
# 🖥️ EVENTS
# ==========================================
@bot.event
async def on_ready():
    bot.uptime = datetime.now()
    print(f"\n┌{'─'*50}┐")
    print(f"  QueenAI Is Now Online!")
    print(f"  Logged in as: {bot.user}")
    print(f"└{'─'*50}┘\n")
    await bot.change_presence(activity=discord.Game(f"Type !tutorial to start!"))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    guild_id, user_id = str(message.guild.id), str(message.author.id)
    current_time = time.time()
    
    guild_config = get_guild_data(config_db, guild_id)
    cooldown_time = guild_config.get("xp_cooldown", 60)
    cooldown_key = f"{guild_id}-{user_id}"
    
    if cooldown_key not in xp_cooldowns or current_time > xp_cooldowns[cooldown_key]:
        guild_levels = get_guild_data(levels_db, guild_id)
        if user_id not in guild_levels: guild_levels[user_id] = {"xp": 0, "level": 1}
        guild_levels[user_id]["xp"] += random.randint(10, 20)
        xp_cooldowns[cooldown_key] = current_time + cooldown_time
        await process_xp(guild_id, user_id, message.channel, message.author)
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    guild_config = get_guild_data(config_db, member.guild.id)
    if autorole_id := guild_config.get("autorole"):
        if role := member.guild.get_role(autorole_id):
            try: await member.add_roles(role, reason="Autorole on join")
            except: pass # Ignore if permissions fail
    if welcome_channel_id := guild_config.get("welcome_channel"):
        if channel := member.guild.get_channel(welcome_channel_id):
            embed = discord.Embed(title=f"Welcome to {member.guild.name}!", description=f"Hello {member.mention}, we're glad to have you! 🎉", color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
            try: await channel.send(embed=embed)
            except: pass

@bot.event
async def on_member_remove(member):
    guild_config = get_guild_data(config_db, member.guild.id)
    if goodbye_channel_id := guild_config.get("goodbye_channel"):
        if channel := member.guild.get_channel(goodbye_channel_id):
            embed = discord.Embed(description=f"**{member.display_name}** has left the server. Goodbye! 👋", color=discord.Color.red())
            try: await channel.send(embed=embed)
            except: pass

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure): await ctx.send(f"❌ **Permission Denied:** {error}")
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(f"❌ **Missing Argument:** You forgot a required argument. Check `{get_prefix(bot, ctx.message)}{ctx.command.name}` usage.")
    elif isinstance(error, commands.BadArgument): await ctx.send(f"❌ **Invalid Argument:** You provided an invalid user, role, or channel.")
    elif isinstance(error, commands.CommandOnCooldown): await ctx.send(f"⏰ This command is on cooldown. Try again in **{error.retry_after:.2f} seconds**.")
    elif isinstance(error, commands.CommandNotFound): pass
    else:
        print(f"An unhandled error occurred in '{ctx.command}': {error}")
        await ctx.send("An unexpected error occurred. Please try again.")

# ==========================================
# 🛠️ SERVER SETUP & ADMIN COMMANDS
# ==========================================
@bot.command()
@commands.is_owner()
async def setadminrole(ctx, role: discord.Role):
    get_guild_data(config_db, ctx.guild.id)["admin_role"] = role.id
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Admin Role Set!** Users with `{role.name}` can use admin commands.")

@bot.command()
@is_admin()
async def setmodrole(ctx, role: discord.Role):
    get_guild_data(config_db, ctx.guild.id)["mod_role"] = role.id
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Moderator Role Set!** Users with `{role.name}` can use moderation commands.")

@bot.command()
@is_admin()
async def setprefix(ctx, new_prefix: str):
    if len(new_prefix) > 5: return await ctx.send("❌ Prefix cannot be longer than 5 characters.")
    get_guild_data(config_db, ctx.guild.id)["prefix"] = new_prefix
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Prefix Set!** My new prefix for this server is `{new_prefix}`.")

@bot.command()
@is_admin()
async def setwelcomechannel(ctx, channel: discord.TextChannel):
    get_guild_data(config_db, ctx.guild.id)["welcome_channel"] = channel.id
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Welcome Channel Set!** New members will be announced in {channel.mention}.")

@bot.command()
@is_admin()
async def setgoodbyechannel(ctx, channel: discord.TextChannel):
    get_guild_data(config_db, ctx.guild.id)["goodbye_channel"] = channel.id
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Goodbye Channel Set!** Departures will be announced in {channel.mention}.")

@bot.command()
@is_admin()
async def autorole(ctx, role: discord.Role):
    get_guild_data(config_db, ctx.guild.id)["autorole"] = role.id
    save_json("config.json", config_db)
    await ctx.send(f"✅ **Autorole Set!** New members will automatically get the `{role.name}` role.")

@bot.command()
@is_admin()
async def configview(ctx):
    guild_config = get_guild_data(config_db, ctx.guild.id)
    prefix = guild_config.get("prefix", DEFAULT_PREFIX)
    admin_role = ctx.guild.get_role(guild_config.get("admin_role"))
    mod_role = ctx.guild.get_role(guild_config.get("mod_role"))
    welcome_ch = ctx.guild.get_channel(guild_config.get("welcome_channel"))
    goodbye_ch = ctx.guild.get_channel(guild_config.get("goodbye_channel"))
    auto_role = ctx.guild.get_role(guild_config.get("autorole"))

    embed = discord.Embed(title=f"⚙️ Bot Configuration for {ctx.guild.name}", color=discord.Color.orange())
    embed.add_field(name="Prefix", value=f"`{prefix}`", inline=False)
    embed.add_field(name="Admin Role", value=admin_role.mention if admin_role else "Not Set", inline=False)
    embed.add_field(name="Moderator Role", value=mod_role.mention if mod_role else "Not Set", inline=False)
    embed.add_field(name="Welcome Channel", value=welcome_ch.mention if welcome_ch else "Not Set", inline=False)
    embed.add_field(name="Goodbye Channel", value=goodbye_ch.mention if goodbye_ch else "Not Set", inline=False)
    embed.add_field(name="Autorole", value=auto_role.mention if auto_role else "Not Set", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@is_admin()
async def resetserver(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id in warnings_db: del warnings_db[guild_id]
    if guild_id in levels_db: del levels_db[guild_id]
    if guild_id in money_db: del money_db[guild_id]
    save_json("warnings.json", warnings_db); save_json("levels.json", levels_db); save_json("money.json", money_db)
    await ctx.send(f"🔄 **Server Data Reset!** All warnings, levels, and economy data for **{ctx.guild.name}** have been cleared.")

@bot.command()
@is_admin()
async def announce(ctx, title: str, *, message: str):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(title=f"📢 {title}", description=message, color=discord.Color.red(), timestamp=datetime.now())
    embed.set_footer(text=f"Announcement by: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@bot.command()
@is_admin()
async def say(ctx, *, message: str):
    try: await ctx.message.delete()
    except: pass
    await ctx.send(message)

@bot.command()
@is_admin()
async def nuke(ctx):
    await ctx.send("⚠️ **DANGER!** This will delete and recreate the channel. Reply `confirm` to proceed.")
    try:
        check = lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"
        await bot.wait_for('message', check=check, timeout=15.0)
        pos = ctx.channel.position
        new_channel = await ctx.channel.clone(reason="Channel Nuke")
        await ctx.channel.delete()
        await new_channel.edit(position=pos)
        await new_channel.send("☢️ **NUKED!** This channel has been reset.")
    except asyncio.TimeoutError: await ctx.send("❌ Nuke cancelled.")
    except discord.Forbidden: await ctx.send("❌ Nuke failed. I lack 'Manage Channels' permission.")

@bot.command()
@is_admin()
async def addrole(ctx, member: discord.Member, *, role: discord.Role):
    try:
        await member.add_roles(role)
        await ctx.send(f"➕ Added role **{role.name}** to {member.mention}.")
    except discord.Forbidden: await ctx.send(f"❌ Could not add role. Check my role hierarchy.")

@bot.command()
@is_admin()
async def removerole(ctx, member: discord.Member, *, role: discord.Role):
    if role not in member.roles: return await ctx.send(f"❌ {member.mention} does not have the **{role.name}** role.")
    try:
        await member.remove_roles(role)
        await ctx.send(f"➖ Removed role **{role.name}** from {member.mention}.")
    except discord.Forbidden: await ctx.send("❌ Could not remove role. Check my role hierarchy.")

@bot.command(aliases=['prune'])
@is_admin()
async def masskick(ctx, days: int = 7):
    if not (0 < days <= 30): return await ctx.send("❌ Days must be between 1 and 30.")
    pruned_count = await ctx.guild.prune_members(days=days, compute_prune_count=False, reason=f"Mass kick by {ctx.author}")
    await ctx.send(f"🧹 Successfully kicked **{pruned_count}** members inactive for {days} days.")

@bot.command()
@is_admin()
async def createtextchannel(ctx, *, channel_name: str):
    await ctx.guild.create_text_channel(channel_name)
    await ctx.send(f"💬 Created new text channel: **#{channel_name}**")

@bot.command()
@is_admin()
async def createvoicechannel(ctx, *, channel_name: str):
    await ctx.guild.create_voice_channel(channel_name)
    await ctx.send(f"🔊 Created new voice channel: **{channel_name}**")

@bot.command()
@is_admin()
async def setlevel(ctx, member: discord.Member, level: int):
    if level < 1: return await ctx.send("❌ Level must be 1 or higher.")
    guild_levels = get_guild_data(levels_db, ctx.guild.id)
    guild_levels[str(member.id)] = {"xp": 0, "level": level}
    save_json("levels.json", levels_db)
    await ctx.send(f"👑 **Level Set:** {member.mention}'s level is now **{level}**.")

@bot.command()
@is_admin()
async def givexp(ctx, member: discord.Member, amount: int):
    if amount <= 0: return await ctx.send("❌ XP amount must be positive.")
    guild_levels = get_guild_data(levels_db, ctx.guild.id)
    user_id = str(member.id)
    if user_id not in guild_levels: guild_levels[user_id] = {"xp": 0, "level": 1}
    guild_levels[user_id]["xp"] += amount
    await ctx.send(f"👑 **XP Added:** Gave {member.mention} **{amount} XP**!")
    await process_xp(ctx.guild.id, user_id, ctx.channel, member)

@bot.command()
@is_admin()
async def addmoney(ctx, member: discord.Member, amount: int):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    user_id = str(member.id)
    guild_money[user_id] = guild_money.get(user_id, 0) + amount
    save_json("money.json", money_db)
    await ctx.send(f"👑 Added **{amount}** coins to {member.mention}'s balance.")

@bot.command()
@is_admin()
async def removemoney(ctx, member: discord.Member, amount: int):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    user_id = str(member.id)
    current_bal = guild_money.get(user_id, 0)
    guild_money[user_id] = max(0, current_bal - amount)
    save_json("money.json", money_db)
    await ctx.send(f"👑 Removed **{amount}** coins from {member.mention}'s balance.")

@bot.command()
@is_admin()
async def setxpcooldown(ctx, seconds: int):
    if not (10 <= seconds <= 300): return await ctx.send("❌ Cooldown must be between 10 and 300 seconds.")
    get_guild_data(config_db, ctx.guild.id)["xp_cooldown"] = seconds
    save_json("config.json", config_db)
    await ctx.send(f"⏳ XP earning cooldown set to **{seconds} seconds** for this server.")

# ==========================================
# 🛡️ MODERATION COMMANDS (Requires Moderator Role)
# ==========================================
@bot.command()
@is_moderator()
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner: return await ctx.send("❌ You cannot warn a member with an equal or higher role.")
    if member == ctx.author or member.bot: return await ctx.send("❌ You cannot warn yourself or a bot.")
    
    guild_warns = get_guild_data(warnings_db, ctx.guild.id)
    user_id = str(member.id)
    if user_id not in guild_warns: guild_warns[user_id] = {"count": 0, "reasons": []}
    guild_warns[user_id]["count"] += 1
    guild_warns[user_id]["reasons"].append(f"'{reason}' by {ctx.author.name} on {datetime.now().strftime('%Y-%m-%d')}")
    save_json("warnings.json", warnings_db)
    
    count = guild_warns[user_id]["count"]
    embed = discord.Embed(title="⚠️ WARNING ISSUED", description=f"**Reason:** {reason}", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention)
    embed.add_field(name="Total Warnings", value=f"**{count}**")
    await ctx.send(embed=embed)
    try: await member.send(f"You have been warned in **{ctx.guild.name}** for: **{reason}**.")
    except: pass

@bot.command(aliases=["unwarn", "removewarn"])
@is_moderator()
async def rmwarn(ctx, member: discord.Member):
    guild_warns = get_guild_data(warnings_db, ctx.guild.id)
    user_id = str(member.id)
    if user_id in guild_warns and guild_warns[user_id]["count"] > 0:
        guild_warns[user_id]["count"] -= 1
        removed_reason = guild_warns[user_id]["reasons"].pop()
        if guild_warns[user_id]["count"] == 0: del guild_warns[user_id]
        save_json("warnings.json", warnings_db)
        await ctx.send(f"✅ Removed one warning for {member.mention}. (Last reason was: {removed_reason})")
    else: await ctx.send("❌ This user has no warnings to remove.")

@bot.command(aliases=["warns"])
async def checkwarns(ctx, member: discord.Member = None):
    member = member or ctx.author
    guild_warns = get_guild_data(warnings_db, ctx.guild.id)
    data = guild_warns.get(str(member.id), {"count": 0, "reasons": []})
    embed = discord.Embed(title=f"Warnings for {member.display_name}", color=discord.Color.orange())
    embed.add_field(name="Total Warnings", value=str(data['count']))
    reasons = "\n".join([f"- {r}" for r in data["reasons"][-5:]]) if data["reasons"] else "Clean record! ✨"
    embed.add_field(name="Recent Reasons (Max 5)", value=reasons, inline=False)
    await ctx.send(embed=embed)

@bot.command()
@is_admin()
async def clearwarns(ctx, member: discord.Member):
    guild_warns = get_guild_data(warnings_db, ctx.guild.id)
    user_id = str(member.id)
    if user_id in guild_warns and guild_warns[user_id]["count"] > 0:
        del guild_warns[user_id]
        save_json("warnings.json", warnings_db)
        await ctx.send(f"✨ All warnings for {member.mention} have been cleared.")
    else: await ctx.send("This user already has a clean record.")

@bot.command()
@is_moderator()
async def mute(ctx, member: discord.Member, *, reason="No reason provided"):
    role = await create_muted_role(ctx.guild)
    if not role: return await ctx.send("❌ Could not find or create the 'Muted' role. Check my permissions.")
    try:
        await member.add_roles(role, reason=reason)
        await ctx.send(f"🤐 **Muted:** {member.mention} | Reason: {reason}")
    except discord.Forbidden: await ctx.send("❌ I don't have permission to assign the 'Muted' role.")

@bot.command()
@is_moderator()
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role and role in member.roles:
        try:
            await member.remove_roles(role, reason="Unmuted by command")
            await ctx.send(f"🔊 **Unmuted:** {member.mention} can now speak.")
        except discord.Forbidden: await ctx.send("❌ I don't have permission to remove the 'Muted' role.")
    else: await ctx.send("❌ This user is not currently muted.")

@bot.command(aliases=['tm'])
@is_moderator()
async def timeout(ctx, member: discord.Member, minutes: int, *, reason="No reason provided"):
    if minutes <= 0: return await ctx.send("❌ Duration must be a positive number.")
    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        await ctx.send(f"⏳ **Timeout:** {member.mention} for **{minutes} minutes**. Reason: {reason}")
    except discord.Forbidden: await ctx.send(f"❌ I don't have permission to time out {member.mention}. Check my role hierarchy.")

@bot.command()
@is_moderator()
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"🥾 **Kicked:** {member.mention} | Reason: {reason}")
    except discord.Forbidden: await ctx.send(f"❌ I can't kick this member. My role is likely lower than theirs.")

@bot.command()
@is_moderator()
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **Banned:** {member.mention} | Reason: {reason}")
    except discord.Forbidden: await ctx.send(f"❌ I can't ban this member. My role is likely lower than theirs.")

@bot.command()
@is_moderator()
async def unban(ctx, user_id: int, *, reason="No reason provided"):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"✅ **Unbanned:** {user.name}#{user.discriminator} has been unbanned.")
    except discord.NotFound: await ctx.send("❌ User not found in the ban list.")

@bot.command()
@is_moderator()
async def purge(ctx, amount: int):
    if not (0 < amount <= 100): return await ctx.send("❌ Please provide a number between 1 and 100.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🗑️ Deleted **{len(deleted) - 1}** messages.", delete_after=5)

@bot.command()
@is_moderator()
async def softban(ctx, member: discord.Member, *, reason="No reason provided"):
    try:
        await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
        await asyncio.sleep(1)
        await ctx.guild.unban(member, reason="Softban complete")
        await ctx.send(f"💨 **Softbanned:** {member.mention}. Their recent messages have been cleared.")
    except discord.Forbidden: await ctx.send(f"❌ I don't have permissions to softban this member.")

@bot.command()
@is_moderator()
async def slowmode(ctx, seconds: int):
    if not (0 <= seconds <= 21600): return await ctx.send("❌ Slowmode must be between 0 (off) and 21600 seconds (6 hours).")
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0: await ctx.send("✅ Slowmode has been disabled.")
    else: await ctx.send(f"🐌 Slowmode set to **{seconds} seconds**.")

@bot.command()
@is_moderator()
async def lock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 **CHANNEL LOCKED:** {channel.mention}.")

@bot.command()
@is_moderator()
async def unlock(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.set_permissions(ctx.guild.default_role, send_messages=None) # Use None to reset to default
    await ctx.send(f"🔓 **CHANNEL UNLOCKED:** {channel.mention}.")

@bot.command()
@is_moderator()
async def nickname(ctx, member: discord.Member, *, nick: str):
    await member.edit(nick=nick)
    await ctx.send(f"📝 Nickname changed for {member.mention} to **{nick}**.")

@bot.command()
@is_moderator()
async def resetnick(ctx, member: discord.Member):
    await member.edit(nick=None)
    await ctx.send(f"📝 Nickname reset for {member.mention}.")

# ==========================================
# 💸 XP & ECONOMY & FUN COMMANDS (For Everyone)
# ==========================================
@bot.command(aliases=["rank", "level"])
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author
    guild_levels = get_guild_data(levels_db, ctx.guild.id)
    data = guild_levels.get(str(member.id), {"xp": 0, "level": 1})
    xp, lvl = data["xp"], data["level"]
    needed = lvl * 100
    bar = create_progress_bar(xp, needed)
    
    embed = discord.Embed(title=f"📊 Rank Card: {member.display_name}", color=discord.Color.purple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Level", value=str(lvl), inline=True)
    embed.add_field(name="XP", value=f"{xp} / {needed}", inline=True)
    embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(aliases=["lb"])
async def leaderboard(ctx):
    guild_levels = get_guild_data(levels_db, ctx.guild.id)
    sorted_users = sorted(guild_levels.items(), key=lambda x: (x[1]['level'], x[1]['xp']), reverse=True)[:10]
    desc = ""
    for i, (uid, data) in enumerate(sorted_users, 1):
        try: member = await ctx.guild.fetch_member(int(uid)); name = member.display_name
        except: name = f"User Left (ID: {uid})"
        desc += f"**{i}.** {name} - Lvl {data['level']} ({data['xp']} XP)\n"
    embed = discord.Embed(title=f"🏆 XP LEADERBOARD - {ctx.guild.name}", description=desc or "No one has earned XP yet!", color=discord.Color.gold())
    await ctx.send(embed=embed)

@bot.command(aliases=['bal'])
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    guild_money = get_guild_data(money_db, ctx.guild.id)
    bal = guild_money.get(str(member.id), 0)
    await ctx.send(f"💰 **{member.display_name}** has **{bal}** coins.")

@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    user_id = str(ctx.author.id)
    reward = random.randint(250, 750)
    guild_money[user_id] = guild_money.get(user_id, 0) + reward
    save_json("money.json", money_db)
    await ctx.send(f"💵 You collected your daily reward of **{reward}** coins!")

@bot.command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def work(ctx):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    user_id = str(ctx.author.id)
    earnings = random.randint(100, 300)
    guild_money[user_id] = guild_money.get(user_id, 0) + earnings
    save_json("money.json", money_db)
    job = random.choice(["coding a Discord bot", "serving lugaw", "driving a jeepney", "selling fishball"])
    await ctx.send(f"💼 You earned **{earnings}** coins by {job}!")

@bot.command()
async def transfer(ctx, member: discord.Member, amount: int):
    if amount <= 0: return await ctx.send("❌ Amount must be positive.")
    if member.id == ctx.author.id: return await ctx.send("❌ You cannot transfer to yourself.")
    if member.bot: return await ctx.send("❌ You cannot transfer to a bot.")
    
    guild_money = get_guild_data(money_db, ctx.guild.id)
    sender_id, receiver_id = str(ctx.author.id), str(member.id)
    sender_bal = guild_money.get(sender_id, 0)

    if sender_bal < amount: return await ctx.send(f"❌ You don't have enough coins. Your balance: **{sender_bal}**.")
    
    guild_money[sender_id] -= amount
    guild_money[receiver_id] = guild_money.get(receiver_id, 0) + amount
    save_json("money.json", money_db)
    await ctx.send(f"💸 Successfully transferred **{amount}** coins to {member.mention}.")

@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def beg(ctx):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    user_id = str(ctx.author.id)
    if random.random() < 0.6: # 60% success
        earnings = random.randint(10, 50)
        guild_money[user_id] = guild_money.get(user_id, 0) + earnings
        save_json("money.json", money_db)
        await ctx.send(f"🙏 A kind stranger gave you **{earnings}** coins.")
    else: await ctx.send("😔 No one gave you anything. Better luck next time.")

@bot.command()
async def richestrank(ctx):
    guild_money = get_guild_data(money_db, ctx.guild.id)
    sorted_users = sorted(guild_money.items(), key=lambda x: x[1], reverse=True)[:10]
    desc = ""
    for i, (uid, amount) in enumerate(sorted_users, 1):
        try: member = await ctx.guild.fetch_member(int(uid)); name = member.display_name
        except: name = f"User Left (ID: {uid})"
        desc += f"**{i}.** {name} - {amount} Coins\n"
    embed = discord.Embed(title=f"💸 WEALTHIEST USERS - {ctx.guild.name}", description=desc or "No one has any money yet!", color=discord.Color.green())
    await ctx.send(embed=embed)

@bot.command(aliases=["av"])
async def avatar(ctx, *, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"🏰 Server Info: {guild.name}", color=discord.Color.green(), timestamp=datetime.now())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime('%b %d, %Y'), inline=True)
    embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    await ctx.send(embed=embed)

@bot.command(aliases=["info"])
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(title=f"User Info: {member.name}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Display Name", value=member.display_name, inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime('%b %d, %Y'), inline=True)
    embed.add_field(name="Joined Discord", value=member.created_at.strftime('%b %d, %Y'), inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def poll(ctx, *, question: str):
    try: await ctx.message.delete()
    except: pass
    embed = discord.Embed(title="📊 POLL", description=question, color=discord.Color.yellow())
    embed.set_footer(text=f"Poll by: {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("👍"); await msg.add_reaction("👎"); await msg.add_reaction("🤷")

@bot.command(aliases=["8ball"])
async def ask(ctx, *, question: str):
    responses = ["It is certain.", "Without a doubt.", "Yes, definitely.", "As I see it, yes.", "Most likely.", "Outlook good.", "Signs point to yes.", "Reply hazy, try again.", "Ask again later.", "Cannot predict now.", "Don't count on it.", "My reply is no.", "Outlook not so good.", "Very doubtful."]
    await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")

@bot.command()
async def coinflip(ctx):
    await ctx.send(f"🪙 The coin landed on: **{random.choice(['Heads', 'Tails'])}**")

@bot.command()
async def latency(ctx):
    await ctx.send(f"🏓 Pong! My latency is **{round(bot.latency * 1000)}ms**.")

@bot.command()
async def dice(ctx, sides: int = 6):
    if sides < 2: return await ctx.send("❌ A dice must have at least 2 sides.")
    await ctx.send(f"🎲 You rolled a d{sides} and got: **{random.randint(1, sides)}**")

@bot.command(aliases=['botinfo'])
async def whoami(ctx):
    embed = discord.Embed(title=f"About Me: {bot.user.name}", color=discord.Color.blurple())
    embed.add_field(name="Developer", value="Coded with ❤️", inline=True)
    embed.add_field(name="Library", value=f"discord.py v{discord.__version__}", inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def choose(ctx, *choices: str):
    if len(choices) < 2: return await ctx.send("❌ Please provide at least two options separated by spaces.")
    await ctx.send(f"🤔 Out of your choices, I pick: **{random.choice(choices)}**")

@bot.command()
async def roll(ctx, dice_string: str = "1d6"):
    try:
        num, sides = map(int, dice_string.lower().split('d'))
        if not (1 <= num <= 20 and 2 <= sides <= 1000): return await ctx.send("❌ Roll between 1-20 dice with 2-1000 sides.")
        results = [random.randint(1, sides) for _ in range(num)]
        await ctx.send(f"🎲 Rolling {num}d{sides}:\nResults: **{', '.join(map(str, results))}**\nTotal: **{sum(results)}**")
    except ValueError: await ctx.send("❌ Invalid format. Use `<number>d<sides>`, e.g., `3d6`.")

@bot.command()
async def weather(ctx, *, city: str):
    conditions = ["Sunny ☀️", "Cloudy ☁️", "Rainy 🌧️", "Stormy ⛈️", "Windy 💨"]
    temp = random.randint(18, 35)
    await ctx.send(f"**Weather for {city.title()}:** **{random.choice(conditions)}** at **{temp}°C**.")

@bot.command()
async def hug(ctx, member: discord.Member):
    if member == ctx.author: return await ctx.send("You can't hug yourself, but I can! 🤗")
    await ctx.send(f"🤗 {ctx.author.mention} gives {member.mention} a big, warm hug!")

@bot.command()
async def slap(ctx, member: discord.Member):
    if member == bot.user: return await ctx.send("Ouch! Why would you do that to me? 😢")
    await ctx.send(f"✋ {ctx.author.mention} slaps {member.mention} with a large trout!")

@bot.command(aliases=['ship'])
async def pairing(ctx, member1: discord.Member, member2: discord.Member):
    score = random.randint(0, 100)
    if score > 80: desc = "A match made in heaven! ❤️"
    elif score > 50: desc = "There's definite potential! 🥰"
    else: desc = "Maybe just friends... 💔"
    await ctx.send(f"💖 **Compatibility**\n`{member1.display_name}` + `{member2.display_name}`\nScore: **{score}%**\nVerdict: {desc}")

@bot.command(aliases=['hex'])
async def color(ctx, hex_code: str = None):
    try:
        color_val = int(hex_code.lstrip('#'), 16) if hex_code else random.randint(0, 0xFFFFFF)
        title = f"Color: #{hex(color_val)[2:].upper()}"
    except (ValueError, TypeError): return await ctx.send("❌ Invalid hex code.")
    embed = discord.Embed(title=title, color=discord.Color(color_val)); await ctx.send(embed=embed)

@bot.command(aliases=['inspire'])
async def quote(ctx):
    quotes = ["The only way to do great work is to love what you do.", "The mind is everything. What you think you become.", "You miss 100% of the shots you don't take.", "The best time to plant a tree was 20 years ago. The second best time is now."]
    await ctx.send(f"💬 *{random.choice(quotes)}*")

@bot.command(aliases=['reverse'])
async def backwards(ctx, *, text: str):
    await ctx.send(f"sdrawkcab si **{text[::-1]}**")

@bot.command()
async def math(ctx, *, expression: str):
    try:
        result = safe_math_eval(expression)
        await ctx.send(f"🧮 **Result:** `{expression}` = **{result}**")
    except Exception as e: await ctx.send(f"❌ Invalid expression. Error: {e}")

@bot.command()
async def remind(ctx, time_str: str, *, reminder: str):
    try:
        if 'm' in time_str: seconds, unit = int(time_str.strip('m')) * 60, "minutes"
        elif 'h' in time_str: seconds, unit = int(time_str.strip('h')) * 3600, "hours"
        elif 's' in time_str: seconds, unit = int(time_str.strip('s')), "seconds"
        else: raise ValueError
        if not (0 < seconds <= 86400): return await ctx.send("❌ Reminder must be between 1s and 24h.")
    except ValueError: return await ctx.send("❌ Invalid time format. Use `30s`, `10m`, or `1h`.")
    
    await ctx.send(f"✅ Okay, {ctx.author.mention}, I'll remind you in **{time_str}** about: `{reminder}`")
    await asyncio.sleep(seconds)
    try: await ctx.author.send(f"⏰ **Reminder from {ctx.guild.name}:**\n> {reminder}")
    except discord.Forbidden: await ctx.send(f"⏰ {ctx.author.mention}, your reminder is up! `{reminder}`")

@bot.command()
@is_moderator()
async def embed(ctx, title: str, color_hex: str, *, description: str):
    try:
        color = discord.Color(int(color_hex.lstrip('#'), 16))
        await ctx.message.delete()
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=f"Embed by {ctx.author.display_name}")
        await ctx.send(embed=embed)
    except ValueError: return await ctx.send("❌ Invalid color hex code.")

@bot.command()
async def count(ctx, *, word: str):
    target = word.lower()
    counter = 0
    async for message in ctx.channel.history(limit=200):
        if not message.author.bot and target in message.content.lower(): counter += 1
    await ctx.send(f"🔢 The word/phrase '**{word}**' appeared **{counter}** times in the last 200 messages.")

@bot.command(aliases=['botstats'])
async def bottats(ctx):
    delta = datetime.now() - bot.uptime
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    embed = discord.Embed(title="⚙️ Bot Status & Stats", color=discord.Color.teal())
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Total Users", value=len(bot.users), inline=True)
    embed.add_field(name="Uptime", value=f"{hours}h {minutes}m {seconds}s", inline=False)
    await ctx.send(embed=embed)

# ==========================================
# 🚑 HELP & TUTORIAL
# ==========================================
@bot.command()
async def tutorial(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="👋 Welcome to the Ultimate Mod Bot Tutorial!", description="Here's how to get your server set up.", color=discord.Color.blue())
    embed.add_field(name="Step 1: Set Admin & Mod Roles (Most Important!)", value=f"Only the **Server Owner** can do this first. This tells the bot who can use powerful commands.\n• `{prefix}setadminrole <role_name>`\n• `{prefix}setmodrole <role_name>`", inline=False)
    embed.add_field(name="Step 2: Configure Server Features (Optional)", value=f"Use these admin commands to enable automatic features.\n• `{prefix}setwelcomechannel <#channel>`\n• `{prefix}setgoodbyechannel <#channel>`\n• `{prefix}autorole <role_name>`\n• `{prefix}setprefix <new_prefix>`", inline=False)
    embed.add_field(name="Step 3: How to Use Commands", value=f"All commands start with `{prefix}`. To see all commands, type `{prefix}help`.", inline=False)
    embed.set_footer(text="Once Step 1 is done, your staff can start moderating!")
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    prefix = get_prefix(bot, ctx.message)
    embed = discord.Embed(title="🤖 COMMAND LIST", description=f"My prefix is `{prefix}`. Type `{prefix}tutorial` for setup.", color=discord.Color.blurple())
    embed.add_field(name="🛠️ Server Setup (Admin Only)", value="`setadminrole`, `setmodrole`, `setprefix`, `setwelcomechannel`, `setgoodbyechannel`, `autorole`, `configview`, `resetserver`", inline=False)
    embed.add_field(name="🛡️ Moderation (Moderator Role)", value="`warn`, `rmwarn`, `checkwarns`, `clearwarns`, `mute`, `unmute`, `timeout`, `kick`, `softban`, `ban`, `unban`, `purge`, `slowmode`, `lock`, `unlock`, `nickname`, `resetnick`, `embed`", inline=False)
    embed.add_field(name="👑 Admin (Admin Role)", value="`announce`, `say`, `nuke`, `addrole`, `removerole`, `masskick`, `createtextchannel`, `createvoicechannel`, `setlevel`, `givexp`, `addmoney`, `removemoney`, `setxpcooldown`", inline=False)
    embed.add_field(name="💸 XP & Economy", value="`rank`, `leaderboard`, `balance`, `daily`, `work`, `transfer`, `beg`, `richestrank`", inline=False)
    embed.add_field(name="🎉 Fun & Utility", value="`avatar`, `serverinfo`, `userinfo`, `poll`, `ask`, `coinflip`, `latency`, `dice`, `whoami`, `choose`, `roll`, `weather`, `hug`, `slap`, `pairing`, `color`, `quote`, `backwards`, `math`, `remind`, `count`, `bottats`", inline=False)
    embed.set_footer(text="Arguments: <required> [optional]")
    await ctx.send(embed=embed)

# ==========================================
# 🚀 START
# ==========================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
