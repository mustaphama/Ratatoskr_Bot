import discord
from discord.ext import commands
from collections import deque
import random
import json

# Create the bot with necessary intents
intents = discord.Intents.all()
intents.messages = True  # Needed for on_message
bot = commands.Bot(command_prefix="r!", intents=intents, help_command=None)

# Queue for channels and active links
channel_queue = deque()
active_channel_pairs = {}  # {channel_id: (linked_channel_id, webhook)}

# Load the JSON file with topics and games data
with open("topics.json", "r") as file:
    topics_data = json.load(file)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command(aliases=["c"])
async def call(ctx):
    """Connect the current channel with another channel."""
    channel = ctx.channel

    # Check if already connected
    if channel.id in active_channel_pairs:
        await ctx.send("You are already in call! Type `r!hangup` to disconnect.")
        return

    # Link with a queued channel or add to the queue
    if channel_queue:
        partner_channel_id = channel_queue.popleft()
        partner_channel = bot.get_channel(partner_channel_id)

        # Create webhooks for both channels
        webhook_a = await partner_channel.create_webhook(name="ChannelLinker")
        webhook_b = await channel.create_webhook(name="ChannelLinker")

        # Store link data
        active_channel_pairs[channel.id] = (partner_channel.id, webhook_a)
        active_channel_pairs[partner_channel.id] = (channel.id, webhook_b)

        await ctx.send(f"Call picked up! Say Hi.")
        await partner_channel.send(f"Call picked up! You're connected.")
    else:
        channel_queue.append(channel.id)
        await ctx.send("Waiting for someone to pick up...")

@bot.command(aliases=["h"])
async def hangup(ctx):
    """Disconnect the current channel from its linked channel."""
    channel = ctx.channel

    # Check if the channel is linked
    if channel.id not in active_channel_pairs:
        await ctx.send("You're not in call. Type `r!call` to start one.")
        return

    # Get linked channel and webhooks
    partner_channel_id, webhook = active_channel_pairs.pop(channel.id)
    partner_webhook = active_channel_pairs.pop(partner_channel_id)[1]

    partner_channel = bot.get_channel(partner_channel_id)

    # Delete webhooks for both channels
    await delete_all_webhooks(channel)
    await delete_all_webhooks(partner_channel)

    await ctx.send("You hung up.")
    await partner_channel.send("The other side hung up.")

async def delete_all_webhooks(channel):
    """Delete all webhooks created by the bot in the given channel."""
    webhooks = await channel.webhooks()
    for webhook in webhooks:
        if webhook.user == bot.user:
            await webhook.delete()

@bot.command(aliases=["s"])
async def skip(ctx):
    channel = ctx.channel

    # Check if the channel is linked
    if channel.id not in active_channel_pairs:
        await ctx.send("You're not in call. Type `r!call` to start one.")
        return

    # await ctx.send("You skipped.")
    #Hanging up first
    await hangup(ctx)
    #Then starting another call
    await call(ctx)

@bot.command(aliases=["t"])
async def topic(ctx, category: str = "random"):
    """Get a random topic to talk about."""
    category = category.lower()

    if category == "random":
        # Pick a random category from the available categories
        category = random.choice(list(topics_data["topics"].keys()))

    if category in topics_data["topics"]:
        # Pick a random topic from the selected category
        topic = random.choice(topics_data["topics"][category])

        # Create an embed for the message
        embed = discord.Embed(
            title=f"Topic from `{category}`",
            description=topic,
            color=discord.Color.blue()
        )

        message = f"{ctx.author.display_name} choose a topic from `{category}`"
    else:
        embed = discord.Embed(
            title="Error",
            description=f"Category `{category}` not found. Available categories: {', '.join(topics_data['topics'].keys())}",
            color=discord.Color.red()
        )
        message = None

    # Send the embed to both the current and linked channel (if any)
    await send_to_linked_channels(ctx, message, embed)

@bot.command(aliases=["wyr"])
async def wouldyourather(ctx):
    """Ask a random 'Would You Rather' question."""
    question = random.choice(topics_data["would_you_rather"])

    # Create an embed for the message
    embed = discord.Embed(
        title="Would You Rather",
        description=question,
        color=discord.Color.green()
    )

    message = f"{ctx.author.display_name} used Would You Rather"

    # Send the embed to both the current and linked channel (if any)
    await send_to_linked_channels(ctx, message, embed)

@bot.command(aliases=["tod"])
async def truthordare(ctx, choice: str = "random"):
    """Play Truth or Dare!"""
    choice = choice.lower()
    if choice not in ["truth", "dare", "random"]:
        await ctx.send("Invalid choice! Choose from: `truth`, `dare`, or leave it blank for random.")
        return

    if choice == "random":
        # Choose either "truth" or "dare" randomly
        choice = random.choice(["truth", "dare"])

    # Pick a random prompt from the chosen "truth" or "dare"
    prompt = random.choice(topics_data["truth_or_dare"][choice])

    # Create an embed for the message
    embed = discord.Embed(
        title=f"{choice.capitalize()} Time!",
        description=prompt,
        color=discord.Color.purple()
    )

    message = f"{ctx.author.display_name} choose {choice.capitalize()}"

    # Send the embed to both the current and linked channel (if any)
    await send_to_linked_channels(ctx, message, embed)

async def send_to_linked_channels(ctx, message, embed):
    """Send the message to both the current channel and its linked channel."""
    channel = ctx.channel

    # Check if the channel is linked to another channel
    if channel.id in active_channel_pairs:
        partner_channel_id, webhook = active_channel_pairs[channel.id]
        partner_channel = bot.get_channel(partner_channel_id)

        # Send the message to the partner channel using webhook
        await webhook.send(
            content=message,
            username=bot.user.display_name,  # Ensure the bot responds as itself
            avatar_url=bot.user.display_avatar.url,
            embed=embed  # Send the embed along with the message
        )

        # Send the message to the current channel
        await ctx.send(embed=embed)

    else:
        # If no active call, just send the embed to the current channel
        await ctx.send(embed=embed)

@bot.command()
async def help(ctx, command: str = None):
    """Displays the help menu or detailed info about a specific command."""
    if not command:
        # General help menu
        embed = discord.Embed(
            title="Ratatoskr Commands",
            description=(
                "Call and connect with other people. Below is the list of all available commands.\n"
                "Use `r!help <command>` to see more details about a specific command."
            ),
            color=discord.Color.teal()
        )

        embed.add_field(
            name="Call Commands",
            value=(
                "`r!call` - Start or join a call with another channel.\n"
                "`r!hangup` - End the current call.\n"
                "`r!skip` - Skip to a new call.\n"
            ),
            inline=False
        )

        embed.add_field(
            name="Fun Commands",
            value=(
                "`r!topic [category]` - Get a random topic to talk about. Use `category` for specific topics (e.g., `r!topic funny`).\n"
                "`r!wouldyourather` - Get a random 'Would You Rather' question.\n"
                "`r!truthordare [choice]` - Play Truth or Dare! Choose `truth`, `dare`, or leave blank for random.\n"
            ),
            inline=False
        )

        embed.set_footer(
            text="Enjoy your conversations! Use r!help <command> to learn more about a specific command."
        )

        await ctx.send(embed=embed)
    else:
        # Detailed help for a specific command
        command = command.lower()
        embed = discord.Embed(color=discord.Color.blue())

        if command == "call":
            embed.title = "r!call"
            embed.description = (
                "Start or join a call with another channel. If no channel is available, "
                "your channel will be placed in a waiting queue."
            )
            embed.add_field(name="Usage", value="`r!call`", inline=False)

        elif command == "hangup":
            embed.title = "r!hangup"
            embed.description = (
                "End the current call and disconnect from the linked channel. "
                "Both channels will be notified of the disconnection."
            )
            embed.add_field(name="Usage", value="`r!hangup`", inline=False)

        elif command == "skip":
            embed.title = "r!skip"
            embed.description = (
                "Skip the current call and connect to the next available channel, "
                "or wait for a new connection."
            )
            embed.add_field(name="Usage", value="`r!skip`", inline=False)

        elif command == "topic":
            embed.title = "r!topic"
            embed.description = (
                "Get a random topic to talk about. Optionally, specify a category "
                "to narrow down the type of topics."
            )
            embed.add_field(name="Usage", value="`r!topic [category]`", inline=False)
            embed.add_field(
                name="Examples",
                value=(
                    "`r!topic` - Get a random topic from any category.\n"
                    "`r!topic funny` - Get a random funny topic."
                ),
                inline=False
            )

        elif command == "wouldyourather":
            embed.title = "r!wouldyourather"
            embed.description = (
                "Get a random 'Would You Rather' question to spark conversation."
            )
            embed.add_field(name="Usage", value="`r!wouldyourather`", inline=False)

        elif command == "truthordare" or command == "tod":
            embed.title = "r!truthordare"
            embed.description = (
                "Play Truth or Dare! Choose between 'truth' or 'dare' for a prompt, "
                "or leave it blank for a random choice."
            )
            embed.add_field(name="Usage", value="`r!truthordare [choice]`", inline=False)
            embed.add_field(
                name="Examples",
                value=(
                    "`r!truthordare` - Get a random truth or dare prompt.\n"
                    "`r!truthordare truth` - Get a truth prompt.\n"
                    "`r!truthordare dare` - Get a dare prompt."
                ),
                inline=False
            )

        else:
            embed.color = discord.Color.red()
            embed.title = "Command Not Found"
            embed.description = (
                f"The command `{command}` does not exist. Use `r!help` to see the list of all commands."
            )
            embed.set_author(
        name=bot.user.display_name,
        icon_url=bot.user.display_avatar.url
    )
        await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    """Relay messages between linked channels."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process commands first
    if message.content.startswith("r!"):
        await bot.process_commands(message)
        return  # Don't relay command messages

    # If the message is from a webhook, ignore it
    if message.webhook_id:
        return

    # Get the channel where the message was sent
    channel = message.channel

    # Relay messages to the linked channel if it exists
    if channel.id in active_channel_pairs:
        partner_channel_id, webhook = active_channel_pairs[channel.id]

        # Use webhook to impersonate the user in the linked channel
        partner_channel = bot.get_channel(partner_channel_id)

        # Check if the message is a reply
        if message.reference and message.reference.resolved:
            original_message = message.reference.resolved  # The original message being replied to
            embed = discord.Embed(
                description=original_message.content,
                color=discord.Color.blue(),
            )
            embed.set_author(
                name=original_message.author.display_name,
                icon_url=original_message.author.display_avatar.url,
            )

            # Send the embed first for the reply reference
            await webhook.send(content=message.content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
                               embed=embed)
        else:
            await webhook.send(
            content=message.content,
            username=message.author.display_name,
            avatar_url=message.author.display_avatar.url,
        )
# safe version
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env
token = os.getenv("BOT_TOKEN")

bot.run(token)