import os
import json
import random
import hashlib
import re
import asyncio
import base64
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HOMEWORK_CHANNEL_ID = os.getenv("HOMEWORK_CHANNEL_ID", "").strip()

if not TOKEN or not GUILD_ID:
    raise SystemExit("Add DISCORD_TOKEN and GUILD_ID to your .env file.")

try:
    GUILD = discord.Object(id=int(GUILD_ID))
    HOMEWORK_CHANNEL_ID = (
        int(HOMEWORK_CHANNEL_ID) if HOMEWORK_CHANNEL_ID else None
    )
except ValueError:
    raise SystemExit("GUILD_ID or HOMEWORK_CHANNEL_ID is not a valid number.")

DATA_FILE = Path(__file__).with_name("bot_data.json")
MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.8-27b"  # Groq vision-capable model for uploaded worksheet images

ai = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
data_lock = asyncio.Lock()


# ==================================================
# SCIENCE IMAGE LIBRARY
# ==================================================
# Wikimedia Commons image redirects.
# Discord may take a little time to display external images.
# If an image fails, the text commands still work.

IMAGES = {
    "astronomy": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Solar_sys8.jpg"
    ),
    "physics": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Ohms_law.svg"
    ),
    "electricity": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Ohms_law.svg"
    ),
    "chemistry": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Atom_diagram.svg"
    ),
    "biology": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Animal_cell_structure_en.svg"
    ),
    "maths": (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        "Coordinate_system_CA_0.svg"
    ),
}

def get_image(topic):
    """Return a relevant illustration URL when a topic is recognised."""
    topic = topic.lower()

    if any(word in topic for word in (
        "electric", "circuit", "current", "resistance",
        "voltage", "ohm", "magnet"
    )):
        return IMAGES["electricity"]

    if any(word in topic for word in (
        "planet", "space", "star", "galaxy", "moon",
        "universe", "astronomy", "black hole"
    )):
        return IMAGES["astronomy"]

    if any(word in topic for word in (
        "cell", "dna", "gene", "plant", "animal",
        "biology", "photosynthesis", "organism"
    )):
        return IMAGES["biology"]

    if any(word in topic for word in (
        "atom", "chemical", "element", "molecule",
        "bond", "reaction", "chemistry"
    )):
        return IMAGES["chemistry"]

    if any(word in topic for word in (
        "equation", "algebra", "parabola", "graph",
        "calculus", "geometry", "maths", "mathematics"
    )):
        return IMAGES["maths"]

    if any(word in topic for word in (
        "physics", "force", "motion", "energy",
        "gravity", "speed", "acceleration", "heat"
    )):
        return IMAGES["physics"]

    return None


def add_topic_image(embed, topic):
    """Attach a topic illustration if one is available."""
    image_url = get_image(topic)
    if image_url:
        embed.set_image(url=image_url)


# ==================================================
# BUILT-IN SCIENCE FACTS
# ==================================================

FACTS = [
    ("astronomy", "A day on Venus is longer than its year."),
    ("astronomy", "Sunlight takes about 8 minutes and 20 seconds to reach Earth."),
    ("astronomy", "Jupiter has the shortest day of the eight planets."),
    ("astronomy", "Saturn's average density is lower than that of water."),
    ("astronomy", "The Milky Way contains an enormous number of stars."),
    ("astronomy", "Neutron stars can contain more mass than the Sun in a city-sized volume."),
    ("astronomy", "The Moon is slowly moving away from Earth."),
    ("astronomy", "A black hole's event horizon marks the boundary beyond which light cannot escape."),
    ("astronomy", "The Sun contains most of the mass in our Solar System."),
    ("astronomy", "Mars has the largest volcano known in the Solar System: Olympus Mons."),
    ("astronomy", "Light from distant galaxies can take billions of years to reach us."),
    ("astronomy", "Astronauts aboard the International Space Station experience microgravity."),
    ("astronomy", "Uranus rotates on its side compared with most other planets."),
    ("astronomy", "Earth's magnetic field helps deflect many charged particles from space."),
    ("astronomy", "The observable universe is much larger than our Solar System."),

    ("physics", "Sound travels faster through water than through air."),
    ("physics", "Lightning can heat surrounding air to temperatures hotter than the Sun's surface."),
    ("physics", "The speed of light in a vacuum is exactly 299,792,458 metres per second."),
    ("physics", "The SI unit of electric current is the ampere."),
    ("physics", "A vacuum has no material medium through which sound can travel."),
    ("physics", "An object's momentum depends on its mass and velocity."),
    ("physics", "Energy can be transferred between objects and transformed between forms."),
    ("physics", "A prism separates white light into a spectrum of colours."),
    ("physics", "The acceleration due to gravity near Earth's surface is about 9.8 m/s²."),
    ("physics", "Electrical resistance is measured in ohms."),
    ("physics", "Absolute zero is 0 kelvin, or about −273.15 degrees Celsius."),
    ("physics", "In a series circuit, the current is the same through each component."),
    ("physics", "In a parallel circuit, each branch has the same voltage across it."),
    ("physics", "A magnet's field is strongest near its poles."),
    ("physics", "Infrared radiation is beyond the red end of the visible spectrum."),

    ("chemistry", "The chemical symbol for tungsten is W."),
    ("chemistry", "Water expands when it freezes under ordinary atmospheric conditions."),
    ("chemistry", "The periodic table is organised by atomic number."),
    ("chemistry", "A neutral atom has equal numbers of protons and electrons."),
    ("chemistry", "Isotopes of an element have the same number of protons but different numbers of neutrons."),
    ("chemistry", "The pH scale is commonly used to describe acidity and alkalinity."),
    ("chemistry", "A catalyst can increase reaction rate without being permanently consumed."),
    ("chemistry", "The chemical formula for ozone is O₃."),
    ("chemistry", "Diamond and graphite are different forms of carbon."),
    ("chemistry", "The noble gases occupy Group 18 of the periodic table."),
    ("chemistry", "The number of protons determines an element's identity."),
    ("chemistry", "Many chemical reactions involve energy being transferred to or from the surroundings."),
    ("chemistry", "One mole contains approximately 6.022 × 10²³ specified entities."),
    ("chemistry", "Rusting involves iron reacting with oxygen in the presence of water."),
    ("chemistry", "Pure water at 25°C has a pH close to 7."),

    ("biology", "Octopuses have three hearts."),
    ("biology", "Plants use light energy to power photosynthesis."),
    ("biology", "DNA stores biological instructions in its molecular sequence."),
    ("biology", "Mitochondria produce much of the ATP used by many eukaryotic cells."),
    ("biology", "Red blood cells transport much of the oxygen in human blood."),
    ("biology", "The human heart has four chambers."),
    ("biology", "Antibiotics target bacteria, not viruses."),
    ("biology", "Enzymes help reactions occur faster in living organisms."),
    ("biology", "Some fungi form extensive underground networks."),
    ("biology", "The human body contains trillions of microbial cells."),
    ("biology", "Chlorophyll absorbs light used in photosynthesis."),
    ("biology", "The immune system helps the body recognise and respond to pathogens."),
    ("biology", "A typical human body cell contains 46 chromosomes."),
    ("biology", "Pollination transfers pollen within the reproductive process of flowering plants."),
    ("biology", "Evolution describes changes in inherited characteristics of populations over generations."),

    ("earth science", "Antarctica is the driest continent by average precipitation."),
    ("earth science", "Earth's atmosphere is mostly nitrogen."),
    ("earth science", "Tectonic plates move slowly over geological time."),
    ("earth science", "Earthquakes can occur when stress is released along faults."),
    ("earth science", "Ocean tides are mainly caused by the Moon's and Sun's gravitational effects."),
    ("earth science", "The water cycle continually moves water through Earth's environment."),
    ("earth science", "Some rocks preserve evidence of ancient environments."),
    ("earth science", "Earth's inner core is solid despite its high temperature, largely due to immense pressure."),
    ("earth science", "Weather describes short-term atmospheric conditions; climate describes longer-term patterns."),
    ("earth science", "Coral reefs support many marine species."),

    ("maths", "The derivative of x² with respect to x is 2x."),
    ("maths", "Pi is irrational, meaning it cannot be expressed exactly as a ratio of two integers."),
    ("maths", "The sum of the interior angles of a triangle in Euclidean geometry is 180 degrees."),
    ("maths", "A prime number has exactly two positive divisors."),
    ("maths", "The Pythagorean theorem applies to right-angled triangles."),
    ("maths", "A logarithm tells you what exponent produces a given number."),
    ("maths", "The gradient of a straight line measures its change in y divided by its change in x."),
    ("maths", "The area of a circle is πr²."),
    ("maths", "The probability of an event lies between 0 and 1."),
    ("maths", "A quadratic function can have a parabolic graph."),
]


# ==================================================
# BUILT-IN QUIZZES
# ==================================================

QUIZZES = [
    ("chemistry", "What is the chemical symbol for gold?", "Au"),
    ("astronomy", "Which planet is known as the Red Planet?", "Mars"),
    ("physics", "What is the SI unit of force?", "Newton"),
    ("chemistry", "What is the centre of an atom called?", "The nucleus"),
    ("biology", "Which gas do plants absorb during photosynthesis?", "Carbon dioxide"),
    ("physics", "What is the approximate speed of light in a vacuum?", "3.0 × 10⁸ m/s"),
    ("biology", "Which organ pumps blood around the human body?", "The heart"),
    ("chemistry", "What is the chemical formula for water?", "H₂O"),
    ("astronomy", "Which planet is the largest in our Solar System?", "Jupiter"),
    ("physics", "What is the SI unit of electric current?", "Ampere"),
    ("biology", "How many chromosomes are in a typical human body cell?", "46"),
    ("physics", "What force attracts objects with mass toward one another?", "Gravity"),
    ("chemistry", "What is the pH of neutral pure water at 25°C?", "7"),
    ("biology", "Which organelle produces much of a cell's ATP?", "Mitochondrion"),
    ("astronomy", "What is the closest star to Earth?", "The Sun"),
    ("physics", "Which subatomic particle has a negative electric charge?", "Electron"),
    ("physics", "What is the SI unit of energy?", "Joule"),
    ("chemistry", "What is the process by which a liquid becomes a gas?", "Vaporisation"),
    ("earth science", "Which gas makes up most of Earth's atmosphere?", "Nitrogen"),
    ("astronomy", "What is the name of our galaxy?", "The Milky Way"),
    ("biology", "Which blood cells primarily transport oxygen?", "Red blood cells"),
    ("maths", "What is the derivative of x² with respect to x?", "2x"),
    ("maths", "What is pi to two decimal places?", "3.14"),
    ("chemistry", "Which type of bond involves sharing electron pairs?", "Covalent bond"),
    ("physics", "What is the SI unit of frequency?", "Hertz"),
    ("physics", "What is the equation connecting voltage, current and resistance?", "V = IR"),
    ("physics", "If voltage is 12 V and resistance is 4 Ω, what is the current?", "3 A"),
    ("physics", "What is the SI unit of power?", "Watt"),
    ("physics", "What type of lens converges parallel rays of light?", "A converging (convex) lens"),
    ("physics", "What is the SI unit of electric charge?", "Coulomb"),
    ("chemistry", "What is the atomic number of carbon?", "6"),
    ("chemistry", "What is the chemical symbol for sodium?", "Na"),
    ("chemistry", "What is the formula for carbon dioxide?", "CO₂"),
    ("chemistry", "What particles are found in an atom's nucleus?", "Protons and neutrons"),
    ("biology", "What molecule carries genetic information in most organisms?", "DNA"),
    ("biology", "What is the name of the process cells use to divide their nucleus for growth?", "Mitosis"),
    ("biology", "Which pigment absorbs light for photosynthesis?", "Chlorophyll"),
    ("biology", "What is the basic structural and functional unit of life?", "The cell"),
    ("astronomy", "Which planet is famous for its prominent ring system?", "Saturn"),
    ("astronomy", "What force keeps planets in orbit around the Sun?", "Gravity"),
    ("astronomy", "What is the name of Earth's natural satellite?", "The Moon"),
    ("earth science", "What is molten rock beneath Earth's surface called?", "Magma"),
    ("earth science", "What instrument records earthquake waves?", "Seismometer"),
    ("earth science", "What is the long-term average pattern of weather called?", "Climate"),
    ("maths", "What is the square root of 144?", "12"),
    ("maths", "What is the area of a rectangle 5 m long and 3 m wide?", "15 m²"),
    ("maths", "What is the gradient of y = 3x + 2?", "3"),
    ("maths", "What is the probability of rolling a 6 on a fair six-sided die?", "1/6"),
    ("maths", "Expand (x + 2)(x + 3).", "x² + 5x + 6"),
    ("maths", "Solve 4x + 7 = 31.", "x = 6"),
    ("maths", "What is the sum of the angles in a triangle?", "180 degrees"),
    ("chemistry", "What is the chemical symbol for iron?", "Fe"),
    ("chemistry", "What is the name of a substance that speeds up a reaction without being consumed overall?", "A catalyst"),
    ("physics", "What is the SI unit of resistance?", "Ohm"),
    ("physics", "Which law is expressed as F = ma?", "Newton's second law"),
    ("biology", "What is the main function of roots in most plants?", "Anchoring the plant and absorbing water and minerals"),
    ("biology", "Which organelle contains most of a eukaryotic cell's DNA?", "The nucleus"),
    ("astronomy", "What is the name of the star at the centre of our Solar System?", "The Sun"),
    ("earth science", "What is the breaking down of rocks at Earth's surface called?", "Weathering"),
]


# ==================================================
# PERSISTENT HISTORY
# ==================================================

def normalise(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fingerprint(text):
    return hashlib.sha256(
        normalise(text).encode("utf-8")
    ).hexdigest()


def load_state():
    if not DATA_FILE.exists():
        return {"seen_facts": [], "seen_quizzes": []}

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            saved = json.load(file)

        return {
            "seen_facts": saved.get("seen_facts", []),
            "seen_quizzes": saved.get("seen_quizzes", []),
        }
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(
            f"Cannot read {DATA_FILE.name}: {error}. "
            "Back up and repair this file before restarting."
        )


state = load_state()


def save_state():
    temporary = DATA_FILE.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)

    temporary.replace(DATA_FILE)


async def remember(kind, text):
    """Record a used fact or quiz without losing previous history."""
    key = f"seen_{kind}"
    digest = fingerprint(text)

    async with data_lock:
        if digest in state[key]:
            return False

        state[key].append(digest)
        save_state()
        return True


def is_seen(kind, text):
    return fingerprint(text) in state[f"seen_{kind}"]


# ==================================================
# GROQ AI
# ==================================================

async def ask_ai(system_prompt, user_prompt):
    if ai is None:
        raise RuntimeError(
            "GROQ_API_KEY is missing from .env. Add your API key to enable AI."
        )

    response = await ai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=850,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("The AI returned an empty response.")

    return content.strip()


async def generate_fact():
    for _ in range(5):
        raw = await ask_ai(
            "You create accurate science facts for students. "
            "Return ONLY JSON with fields topic and fact. "
            "Topic must be a short subject label. "
            "Fact must be 1-2 sentences. Do not invent scientific claims.",
            "Generate one interesting science fact that is different "
            "from common introductory textbook facts."
        )

        try:
            item = json.loads(raw)
            topic = item["topic"].strip()
            fact = item["fact"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            continue

        if fact and not is_seen("facts", fact):
            if await remember("facts", fact):
                return topic, fact

    raise RuntimeError("Could not create an unused fact. Try again shortly.")


async def generate_quiz(difficulty="medium"):
    level_descriptions = {
        "easy": "Year 10 foundations: direct recall and straightforward one-step applications.",
        "medium": "Year 10 challenge: connect ideas and use two-step reasoning, but do not rely on Year 11/12-only content.",
        "hard": "Year 12 / VCE level: senior-secondary depth, multi-step reasoning, precise terminology, and VCE-style applications where relevant.",
        "extra_hard": "Introductory university level: undergraduate concepts and deeper reasoning. Make the question self-contained and state necessary assumptions."
    }
    level = level_descriptions.get(difficulty, level_descriptions["medium"])
    for _ in range(5):
        raw = await ask_ai(
            "You create accurate science and maths quiz questions for students. "
            "Return ONLY JSON with string fields topic, question and answer. "
            "Questions must be unambiguous, have one clear answer, and match the requested academic level. "
            "Use correct units and independently verify any calculations.",
            f"Generate one original science or maths quiz question at this level: {difficulty}. "
            f"Level requirements: {level}. Avoid repeating questions already used."
        )

        try:
            item = json.loads(raw)
            topic = item["topic"].strip()
            question = item["question"].strip()
            answer = item["answer"].strip()
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            continue

        if question and answer and not is_seen("quizzes", question):
            if await remember("quizzes", question):
                return topic, question, answer

    raise RuntimeError("Could not create an unused quiz. Try again shortly.")


async def get_fact():
    available = [
        item for item in FACTS
        if not is_seen("facts", item[1])
    ]

    if available:
        topic, fact = random.choice(available)
        await remember("facts", fact)
        return topic, fact

    # Keep the existing history. Generate new content instead of resetting it.
    return await generate_fact()


async def get_quiz(difficulty="medium"):
    # Generate by the requested level so a Year 10 question is not accidentally
    # returned for a Year 12 or university-level request.
    return await generate_quiz(difficulty)


# ==================================================
# DISCORD BOT
# ==================================================

class StellarBot(commands.Bot):
    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)

        print(f"Synced {len(synced)} slash commands:")
        print([command.name for command in synced])


bot = StellarBot(
    command_prefix="!",
    intents=discord.Intents.default()
)


@bot.event
async def on_ready():
    print(f"Connected as {bot.user}")
    print("Stellar Bot is online!")


# ==================================================
# /HELLO
# ==================================================

@bot.tree.command(name="hello", description="Say hello to Stellar Bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hey {interaction.user.mention}! Welcome to Stellar Science Club!"
    )


# ==================================================
# /SCIENCE
# ==================================================

@bot.tree.command(name="science", description="Get a new science fact with an illustration")
async def science(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        topic, fact = await get_fact()

        embed = discord.Embed(
            title=f"🔬 Stellar Science Fact • {topic.title()}",
            description=fact,
            color=discord.Color.blurple()
        )
        add_topic_image(embed, topic + " " + fact)
        embed.set_footer(text="Stellar Science Club • Facts are checked by AI when generated")

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"/science error: {error}")
        await interaction.followup.send(
            "I couldn't get a new fact right now. Check the bot terminal and try again."
        )


# ==================================================
# /QUIZ
# ==================================================

@bot.tree.command(name="quiz", description="Get a science or maths quiz at your chosen level")
@app_commands.describe(difficulty="Choose the academic level")
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Easy • Year 10 foundations", value="easy"),
    app_commands.Choice(name="Medium • Year 10 challenge", value="medium"),
    app_commands.Choice(name="Hard • Year 12 / VCE", value="hard"),
    app_commands.Choice(name="Extra hard • University level", value="extra_hard"),
])
async def quiz(interaction: discord.Interaction, difficulty: app_commands.Choice[str]):
    await interaction.response.defer(thinking=True)

    try:
        topic, question, answer = await get_quiz(difficulty.value)

        embed = discord.Embed(
            title=f"Stellar Science Quiz • {difficulty.name}",
            description=f"**Topic:** {topic.title()}\\n\\n{question}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Answer", value=f"||{answer}||", inline=False)
        add_topic_image(embed, topic + " " + question)
        embed.set_footer(text="Try solving it before revealing the spoiler answer.")

        await interaction.followup.send(embed=embed)

    except Exception as error:
        print(f"/quiz error: {error}")
        await interaction.followup.send(
            "I couldn't create a quiz right now. Check the bot terminal and try again."
        )


# ==================================================
# /HOMEWORK — AI TUTOR
# ==================================================

@bot.tree.command(name="homework", description="Get step-by-step AI homework help from text or an uploaded image")
@app_commands.describe(
    subject="Subject, e.g. maths, physics, biology, chemistry or English",
    question="Type your question or say what you need help with",
    image="Optional photo/screenshot of the worksheet or question (PNG, JPG or WEBP)"
)
async def homework(
    interaction: discord.Interaction,
    subject: str,
    question: str,
    image: discord.Attachment | None = None
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        system_prompt = (
            "You are a patient, accurate school homework tutor. Answer the student's actual question, "
            "not a different question. Explain the method step by step, show equations and working "
            "where useful, define unfamiliar terms, and use age-appropriate language. For English, "
            "explain evidence and reasoning. If information is missing or an image is unclear, say so "
            "instead of guessing. Use Discord-compatible Markdown: **bold headings**, bullet lists and "
            "numbered steps. Do not use HTML or LaTeX delimiters; write equations as readable plain text. "
            "Help the student understand the method, not just copy an answer."
        )

        if image is not None:
            allowed_types = {"image/png", "image/jpeg", "image/webp"}
            if image.content_type not in allowed_types:
                await interaction.followup.send(
                    "Please upload a PNG, JPG/JPEG or WEBP image. If your file is a PDF, upload a screenshot of the relevant page.",
                    ephemeral=True
                )
                return
            if image.size > 8 * 1024 * 1024:
                await interaction.followup.send(
                    "That image is over 8 MB. Please resize or compress it and upload it again.",
                    ephemeral=True
                )
                return
            if ai is None:
                raise RuntimeError("GROQ_API_KEY is missing from .env.")

            image_bytes = await image.read()
            encoded_image = base64.b64encode(image_bytes).decode("ascii")
            mime_type = image.content_type or "image/jpeg"
            prompt_text = (
                f"Subject: {subject}\nStudent's question/instructions: {question}\n\n"
                "Read the attached worksheet/photo carefully. Use any visible question text, diagrams, "
                "labels and values to answer. If part of the image is unreadable, tell the student exactly "
                "what needs a clearer photo. Explain the solution step by step."
            )
            response = await ai.chat.completions.create(
                model=VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }}
                    ]}
                ],
                temperature=0.4,
                max_completion_tokens=1200,
            )
            answer_text = response.choices[0].message.content or "I couldn't read that image clearly. Please upload a sharper crop."
        else:
            answer_text = await ask_ai(system_prompt, f"Subject: {subject}\nStudent's question: {question}")

        answer_text = format_discord_markdown(answer_text) if "format_discord_markdown" in globals() else answer_text
        if len(answer_text) > 3900:
            answer_text = answer_text[:3880] + "\n\n…(answer shortened; ask a follow-up for the next part)"

        embed = discord.Embed(
            title=f"📚 Homework Help: {subject[:200]}",
            description=answer_text,
            color=discord.Color.green()
        )
        if image is not None:
            embed.set_image(url=image.url)
        else:
            add_topic_image(embed, subject + " " + question)
        embed.set_footer(text="AI-generated explanation • Check important answers with your teacher.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as error:
        print(f"/homework error: {error}")
        await interaction.followup.send(
            "I couldn't answer that right now. Check the Groq API key/model and terminal error, then try again.",
            ephemeral=True
        )


# ==================================================
# /ASK-COMMUNITY
# ==================================================

@bot.tree.command(
    name="ask-community",
    description="Post a homework question for community members to answer"
)
@app_commands.describe(
    subject="Subject of your question",
    question="Explain what you need help with"
)
async def ask_community(
    interaction: discord.Interaction,
    subject: str,
    question: str
):
    if not HOMEWORK_CHANNEL_ID:
        await interaction.response.send_message(
            "The homework channel isn't configured. Please tell a server administrator.",
            ephemeral=True
        )
        return

    channel = bot.get_channel(HOMEWORK_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(HOMEWORK_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            channel = None

    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "I couldn't find the configured homework channel. Ask an administrator "
            "to check HOMEWORK_CHANNEL_ID.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"📝 Community Homework Request: {subject[:200]}",
        description=question[:4000],
        color=discord.Color.orange()
    )
    embed.add_field(
        name="Asked by",
        value=interaction.user.mention,
        inline=False
    )
    add_topic_image(embed, subject + " " + question)
    embed.set_footer(text="Stellar Science Club • Help each other learn!")

    try:
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"Your question has been posted in {channel.mention}!",
            ephemeral=True
        )
    except discord.HTTPException as error:
        print(f"/ask-community error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "I couldn't post your question. Check the bot's permissions "
                "in the homework channel.",
                ephemeral=True
            )


# ==================================================
# /SERVER
# ==================================================

@bot.tree.command(name="server", description="Show server information")
async def server(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "Use this command inside a server.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=guild.name,
        description="Welcome to Stellar Science Club!",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="Members",
        value=str(guild.member_count or "Unknown")
    )
    embed.add_field(name="Server ID", value=str(guild.id))
    embed.set_footer(text="Stellar Science Club")

    await interaction.response.send_message(embed=embed)


# ==================================================
# /HELP
# ==================================================

@bot.tree.command(name="help", description="Show all Stellar Bot commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="✨ Stellar Bot Commands",
        description=(
            "`/hello` — say hello\n"
            "`/science` — get a science fact and relevant illustration\n"
            "`/quiz` — get a science or maths quiz question\n"
            "`/homework` — ask the AI tutor for step-by-step help\n"
            "`/ask-community` — post a question for members to answer\n"
            "`/flashcards` — revise with interactive flashcards\n"
            "`/challenge` and `/answer` — daily challenge and XP\n"
            "`/profile` — view XP and progress\n"
            "`/leaderboard` — see the top XP earners\n"
            "`/explain` — get an AI concept explanation\n"
            "`/studyplan` and `/myplan` — create or view a study plan\n"
            "`/formula` — look up a formula\n"
            "`/periodic-table` — look up an element\n"
            "`/convert` — convert common units\n"
            "`/define` — define a term\n"
            "`/hint` — get a hint without the full solution\n"
            "`/practice` — generate an interactive practice question\n"
            "`/flashcard-add` and `/myflashcards` — create and revise your own cards\n"
            "`/studylog` and `/progress` — track study time and progress\n"
            "`/server` — see server information\n"
            "`/help` — show this command list"
        ),
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed)



# ==================================================
# EXTRA FEATURES: FLASHCARDS, DAILY CHALLENGE, XP,
# AI EXPLAINER, STUDY PLANNER AND SCIENCE UTILITIES
# ==================================================

from datetime import datetime
from zoneinfo import ZoneInfo

FEATURES_FILE = Path(__file__).with_name("bot_features.json")
MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


def load_feature_data():
    """Load extra features separately, preserving the existing fact/quiz history."""
    if not FEATURES_FILE.exists():
        return {"users": {}, "challenge_attempts": {}, "study_plans": {}, "custom_flashcards": {}, "study_logs": {}, "practice_history": {}}
    try:
        with FEATURES_FILE.open("r", encoding="utf-8") as file:
            saved = json.load(file)
        saved.setdefault("users", {})
        saved.setdefault("challenge_attempts", {})
        saved.setdefault("study_plans", {})
        saved.setdefault("custom_flashcards", {})
        saved.setdefault("study_logs", {})
        saved.setdefault("practice_history", {})
        return saved
    except (OSError, json.JSONDecodeError) as error:
        # Don't silently overwrite a damaged save file.
        raise RuntimeError(
            f"Cannot read {FEATURES_FILE.name}: {error}. Back up and repair it first."
        ) from error


def save_feature_data(feature_data):
    temporary = FEATURES_FILE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(feature_data, file, indent=2, ensure_ascii=False)
    temporary.replace(FEATURES_FILE)


def get_feature_user(feature_data, user_id):
    key = str(user_id)
    if key not in feature_data["users"]:
        feature_data["users"][key] = {
            "xp": 0,
            "correct_answers": 0,
            "challenges_completed": 0
        }
    return feature_data["users"][key]


def today_key():
    return datetime.now(MELBOURNE_TZ).date().isoformat()


def format_discord_markdown(text):
    """Turn common LaTeX delimiters into readable Discord text."""
    text = text.strip()
    text = re.sub(r"\\\[([\s\S]*?)\\\]", r"```\n\1\n```", text)
    text = re.sub(r"\\\(([\s\S]*?)\\\)", r"`\1`", text)
    text = re.sub(r"\$\$([\s\S]*?)\$\$", r"```\n\1\n```", text)
    text = re.sub(r"\$([^$\n]+)\$", r"`\1`", text)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    return text.strip()


async def send_long_response(interaction, text, *, ephemeral=False):
    """Send an AI answer in Discord-safe chunks (under the 2000-character limit)."""
    text = format_discord_markdown(text)
    chunks = []
    while len(text) > 1850:
        split_at = text.rfind("\n", 0, 1850)
        if split_at < 500:
            split_at = 1850
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    if not chunks:
        chunks = ["I couldn't generate a response. Please try again."]
    for index, chunk in enumerate(chunks):
        if index == 0 and not interaction.response.is_done():
            await interaction.response.send_message(chunk, ephemeral=ephemeral)
        else:
            await interaction.followup.send(chunk, ephemeral=ephemeral)


# ------------------------------
# INTERACTIVE FLASHCARDS
# ------------------------------

FLASHCARDS = {
    "physics": [
        ("State Newton's second law.", "F = ma: net force equals mass multiplied by acceleration."),
        ("State Ohm's law.", "V = IR: voltage equals current multiplied by resistance."),
        ("What is kinetic energy?", "Energy of motion: Ek = ½mv²."),
        ("What is the SI unit of power?", "The watt (W), equal to one joule per second."),
        ("What is the approximate gravitational acceleration near Earth's surface?", "About 9.8 m/s²."),
        ("What is the SI unit of charge?", "The coulomb (C)."),
    ],
    "chemistry": [
        ("What is an isotope?", "Atoms of the same element with the same number of protons but different numbers of neutrons."),
        ("What is one mole?", "Approximately 6.022 × 10²³ specified entities."),
        ("What does atomic number tell you?", "The number of protons in an atom's nucleus."),
        ("What is a catalyst?", "A substance that increases reaction rate without being consumed overall."),
        ("What is the formula for ozone?", "O₃."),
        ("What type of bond involves shared electron pairs?", "A covalent bond."),
    ],
    "biology": [
        ("What is the role of mitochondria?", "They are a main site of aerobic respiration and ATP production in eukaryotic cells."),
        ("What is osmosis?", "Net movement of water across a selectively permeable membrane due to a water-potential difference."),
        ("What molecule carries genetic information in most organisms?", "DNA."),
        ("What is the main pigment used in photosynthesis?", "Chlorophyll."),
        ("What is the basic unit of life?", "The cell."),
        ("What do enzymes do?", "They catalyse biological reactions, increasing reaction rates."),
    ],
    "astronomy": [
        ("What is a light-year?", "The distance light travels in a vacuum in one year, about 9.46 trillion km."),
        ("What causes Earth's seasons?", "Earth's axial tilt as it orbits the Sun."),
        ("What is an exoplanet?", "A planet orbiting a star outside our Solar System."),
        ("What is the name of our galaxy?", "The Milky Way."),
        ("What is a nebula?", "A cloud of gas and dust in space."),
    ],
    "maths": [
        ("What is the derivative of x²?", "2x."),
        ("State the Pythagorean theorem.", "For a right triangle, a² + b² = c², where c is the hypotenuse."),
        ("What is the area of a circle?", "A = πr²."),
        ("What is the gradient between two points?", "m = (y₂ − y₁)/(x₂ − x₁)."),
        ("What is the quadratic formula?", "For ax² + bx + c = 0: x = (−b ± √(b² − 4ac))/(2a)."),
    ],
    "earth science": [
        ("What is molten rock below Earth's surface called?", "Magma."),
        ("What is the long-term pattern of weather called?", "Climate."),
        ("What is the breaking down of rocks at Earth's surface called?", "Weathering."),
        ("What instrument records earthquake waves?", "A seismometer."),
    ],
}


class FlashcardView(discord.ui.View):
    def __init__(self, cards, owner_id):
        super().__init__(timeout=180)
        self.cards = cards
        self.owner_id = owner_id
        self.index = 0
        self.revealed = False

    def make_embed(self):
        question, answer_text = self.cards[self.index]
        embed = discord.Embed(
            title=f"Flashcards • {self.index + 1}/{len(self.cards)}",
            description=f"**Question**\n{question}",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Answer",
            value=answer_text if self.revealed else "Press **Reveal answer** to check yourself.",
            inline=False
        )
        embed.set_footer(text="Stellar Science Club • Active recall")
        return embed

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "These flashcards belong to someone else. Start your own with `/flashcards`.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Reveal answer", style=discord.ButtonStyle.primary)
    async def reveal_button(self, interaction, button):
        self.revealed = True
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_button(self, interaction, button):
        self.index = (self.index + 1) % len(self.cards)
        self.revealed = False
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction, button):
        self.index = (self.index - 1) % len(self.cards)
        self.revealed = False
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


@bot.tree.command(name="flashcards", description="Revise using interactive flashcards")
@app_commands.choices(topic=[
    app_commands.Choice(name="Physics", value="physics"),
    app_commands.Choice(name="Chemistry", value="chemistry"),
    app_commands.Choice(name="Biology", value="biology"),
    app_commands.Choice(name="Astronomy", value="astronomy"),
    app_commands.Choice(name="Maths", value="maths"),
    app_commands.Choice(name="Earth science", value="earth science"),
])
async def flashcards(interaction: discord.Interaction, topic: app_commands.Choice[str]):
    cards = FLASHCARDS.get(topic.value, [])
    if not cards:
        await interaction.response.send_message("No flashcards found for that topic yet.", ephemeral=True)
        return
    view = FlashcardView(random.sample(cards, len(cards)), interaction.user.id)
    await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


# ------------------------------
# DAILY CHALLENGE + XP
# ------------------------------

DAILY_CHALLENGES = [
    {
        "question": "A 12 V battery is connected across a 4 Ω resistor. What current flows?",
        "options": ["2 A", "3 A", "4 A", "48 A"],
        "answer": 1,
        "explanation": "Using Ohm's law, I = V/R = 12/4 = 3 A."
    },
    {
        "question": "Which organelle is a main site of aerobic respiration in eukaryotic cells?",
        "options": ["Ribosome", "Mitochondrion", "Golgi apparatus", "Lysosome"],
        "answer": 1,
        "explanation": "Mitochondria are a main site of aerobic respiration and ATP production."
    },
    {
        "question": "What is the approximate speed of light in a vacuum?",
        "options": ["3 × 10⁶ m/s", "3 × 10⁸ m/s", "3 × 10¹⁰ m/s", "300 m/s"],
        "answer": 1,
        "explanation": "The speed of light in a vacuum is approximately 3.00 × 10⁸ m/s."
    },
    {
        "question": "At 25 °C, what is the pH of neutral pure water?",
        "options": ["0", "5", "7", "14"],
        "answer": 2,
        "explanation": "At 25 °C, neutral pure water has a pH close to 7."
    },
    {
        "question": "What is the derivative of x³?",
        "options": ["x²", "2x", "3x²", "3x"],
        "answer": 2,
        "explanation": "By the power rule, d(xⁿ)/dx = nxⁿ⁻¹, so d(x³)/dx = 3x²."
    },
    {
        "question": "Which gas makes up the largest proportion of Earth's atmosphere?",
        "options": ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"],
        "answer": 2,
        "explanation": "Nitrogen makes up about 78% of Earth's atmosphere."
    },
    {
        "question": "What is the chemical symbol for sodium?",
        "options": ["S", "So", "Na", "N"],
        "answer": 2,
        "explanation": "Sodium's chemical symbol is Na, from its Latin name natrium."
    },
]


def get_daily_challenge():
    # All servers/users see the same question on the same Melbourne date.
    date = today_key()
    index = int(hashlib.sha256(date.encode()).hexdigest(), 16) % len(DAILY_CHALLENGES)
    return DAILY_CHALLENGES[index]


@bot.tree.command(name="challenge", description="Show today's science challenge")
async def challenge(interaction: discord.Interaction):
    item = get_daily_challenge()
    options = "\n".join(f"**{chr(65 + i)}.** {value}" for i, value in enumerate(item["options"]))
    embed = discord.Embed(
        title=f"Daily Science Challenge • {today_key()}",
        description=f"{item['question']}\n\n{options}\n\nSubmit with `/answer`.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="One scored attempt per user per day • Melbourne time")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="answer", description="Submit your answer to today's challenge")
@app_commands.choices(choice=[
    app_commands.Choice(name="A", value="A"),
    app_commands.Choice(name="B", value="B"),
    app_commands.Choice(name="C", value="C"),
    app_commands.Choice(name="D", value="D"),
])
async def answer(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    date = today_key()
    item = get_daily_challenge()
    data = load_feature_data()
    user_key = str(interaction.user.id)
    attempt_key = f"{date}:{user_key}"

    if attempt_key in data["challenge_attempts"]:
        await interaction.response.send_message(
            "You've already submitted an answer for today's challenge. Try again tomorrow!",
            ephemeral=True
        )
        return

    selected = ord(choice.value) - ord("A")
    correct = selected == item["answer"]
    data["challenge_attempts"][attempt_key] = {
        "choice": choice.value,
        "correct": correct
    }
    user = get_feature_user(data, interaction.user.id)

    if correct:
        award_xp(user, 10)
        user["correct_answers"] = int(user.get("correct_answers", 0)) + 1
        user["challenges_completed"] = int(user.get("challenges_completed", 0)) + 1

    save_feature_data(data)
    result = "Correct! You earned **10 XP**. 🌟" if correct else "Not quite — no XP this time."
    await interaction.response.send_message(
        f"{result}\n\n**Correct answer:** {chr(65 + item['answer'])}. "
        f"{item['options'][item['answer']]}\n{item['explanation']}",
        ephemeral=True
    )


@bot.tree.command(name="profile", description="View your or another member's Stellar Bot XP")
@app_commands.describe(member="Optional server member to view")
async def profile(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    data = load_feature_data()
    user = get_feature_user(data, target.id)
    save_feature_data(data)
    embed = discord.Embed(title=f"{target.display_name}'s Stellar Profile", color=discord.Color.blurple())
    embed.add_field(name="XP", value=str(user.get("xp", 0)))
    embed.add_field(name="Correct challenges", value=str(user.get("challenges_completed", 0)))
    embed.add_field(name="Correct answers", value=str(user.get("correct_answers", 0)))
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="leaderboard", description="Show the top Stellar Bot XP earners")
async def leaderboard(interaction: discord.Interaction):
    data = load_feature_data()
    users = sorted(
        data["users"].items(),
        key=lambda entry: int(entry[1].get("xp", 0)),
        reverse=True
    )[:10]
    if not users:
        await interaction.response.send_message("No XP has been earned yet. Try `/challenge`!")
        return

    lines = []
    for rank, (user_id, stats) in enumerate(users, start=1):
        member = interaction.guild.get_member(int(user_id)) if interaction.guild else None
        name = member.display_name if member else f"User {user_id}"
        lines.append(f"**{rank}.** {name} — **{stats.get('xp', 0)} XP**")
    embed = discord.Embed(title="Stellar Bot Leaderboard", description="\n".join(lines), color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


# ------------------------------
# AI CONCEPT EXPLAINER
# ------------------------------

@bot.tree.command(name="explain", description="Get a clear AI explanation of a science or maths concept")
@app_commands.describe(topic="The concept you want explained")
async def explain(interaction: discord.Interaction, topic: str):
    await interaction.response.defer(thinking=True)
    try:
        response = await ask_ai(
            "You are a clear, accurate science and maths tutor for secondary-school students. "
            "Use Discord-compatible Markdown only: **bold headings**, bullets, and numbered steps. "
            "Do not use HTML or LaTeX delimiters. Write equations in readable plain text, e.g. V = IR. "
            "Explain the concept, give a worked example if suitable, list common mistakes, and finish "
            "with a one-sentence summary. Be honest about uncertainty.",
            f"Explain this concept: {topic}"
        )
        response = format_discord_markdown(response)
        embed = discord.Embed(
            title=f"Concept Explainer: {topic[:240]}",
            description=response[:4000],
            color=discord.Color.green()
        )
        add_topic_image(embed, topic)
        await interaction.followup.send(embed=embed)
    except Exception as error:
        print(f"/explain error: {error}")
        await interaction.followup.send("I couldn't explain that right now. Check the bot terminal and Groq configuration.")


# ------------------------------
# STUDY PLANNER
# ------------------------------

@bot.tree.command(name="studyplan", description="Create and save a personalised study plan")
@app_commands.describe(
    subject="Subject to study",
    topics="Topics to cover, separated by commas",
    deadline="Deadline, e.g. 2026-11-20",
    sessions_per_week="How many study sessions you can do each week"
)
@app_commands.choices(sessions_per_week=[
    app_commands.Choice(name="2 sessions", value=2),
    app_commands.Choice(name="3 sessions", value=3),
    app_commands.Choice(name="4 sessions", value=4),
    app_commands.Choice(name="5 sessions", value=5),
    app_commands.Choice(name="6 sessions", value=6),
    app_commands.Choice(name="7 sessions", value=7),
])
async def studyplan(
    interaction: discord.Interaction,
    subject: str,
    topics: str,
    deadline: str,
    sessions_per_week: app_commands.Choice[int]
):
    try:
        due = datetime.strptime(deadline, "%Y-%m-%d").date()
    except ValueError:
        await interaction.response.send_message("Use the deadline format `YYYY-MM-DD`, e.g. `2026-11-20`.", ephemeral=True)
        return

    today = datetime.now(MELBOURNE_TZ).date()
    if due < today:
        await interaction.response.send_message("That deadline is in the past. Please enter a future date.", ephemeral=True)
        return

    topic_list = [item.strip() for item in topics.split(",") if item.strip()]
    if not topic_list:
        await interaction.response.send_message("Add at least one topic, separated by commas.", ephemeral=True)
        return
    if len(topic_list) > 20:
        await interaction.response.send_message("Please keep each plan to 20 topics or fewer.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    days_left = max(1, (due - today).days)
    try:
        plan_text = await ask_ai(
            "You are a practical study coach for a secondary-school student. "
            "Create a realistic, balanced study schedule using short sessions, active recall, "
            "practice questions and review. Do not promise grades. Use Discord-compatible Markdown "
            "and plain-text equations; no HTML or LaTeX. Keep the plan concise and actionable.",
            f"Subject: {subject}\nTopics: {', '.join(topic_list)}\n"
            f"Days until deadline: {days_left}\nSessions per week: {sessions_per_week.value}\n"
            "Make a week-by-week plan and include a final review session."
        )
    except Exception as error:
        print(f"/studyplan AI error: {error}")
        plan_text = (
            f"**Suggested plan for {subject}**\n"
            + "\n".join(f"- Session {i + 1}: study {topic}; finish with 5 practice questions."
                        for i, topic in enumerate(topic_list))
            + "\n- Final session: mixed practice and review of mistakes."
        )

    data = load_feature_data()
    data["study_plans"][str(interaction.user.id)] = {
        "subject": subject,
        "topics": topic_list,
        "deadline": deadline,
        "sessions_per_week": sessions_per_week.value,
        "plan": plan_text,
        "updated": today_key()
    }
    save_feature_data(data)
    await send_long_response(interaction, f"**Saved study plan • {subject} • Deadline: {deadline}**\n\n{plan_text}", ephemeral=True)


@bot.tree.command(name="myplan", description="View your saved study plan")
async def myplan(interaction: discord.Interaction):
    data = load_feature_data()
    saved = data["study_plans"].get(str(interaction.user.id))
    if not saved:
        await interaction.response.send_message("You don't have a saved plan yet. Use `/studyplan` to make one.", ephemeral=True)
        return
    message = (
        f"**{saved['subject']}** • Deadline: {saved['deadline']}\n"
        f"**Topics:** {', '.join(saved['topics'])}\n"
        f"**Sessions per week:** {saved['sessions_per_week']}\n\n"
        f"{saved['plan']}"
    )
    await send_long_response(interaction, message, ephemeral=True)


# ------------------------------
# SCIENCE UTILITIES
# ------------------------------

FORMULAS = {
    "ohms law": ("V = IR", "V = voltage (V), I = current (A), R = resistance (Ω)."),
    "speed": ("v = d/t", "v = speed (m/s), d = distance (m), t = time (s)."),
    "acceleration": ("a = (v - u)/t", "a = acceleration (m/s²), u = initial velocity, v = final velocity, t = time."),
    "newtons second law": ("F = ma", "F = net force (N), m = mass (kg), a = acceleration (m/s²)."),
    "weight": ("W = mg", "W = weight (N), m = mass (kg), g = gravitational field strength (N/kg)."),
    "kinetic energy": ("Ek = ½mv²", "Ek = kinetic energy (J), m = mass (kg), v = speed (m/s)."),
    "gravitational potential energy": ("Eg = mgh", "Eg = gravitational potential energy (J), m = mass (kg), g = gravitational field strength, h = height (m)."),
    "power": ("P = E/t", "P = power (W), E = energy transferred (J), t = time (s)."),
    "density": ("ρ = m/V", "ρ = density (kg/m³), m = mass (kg), V = volume (m³)."),
    "momentum": ("p = mv", "p = momentum (kg·m/s), m = mass (kg), v = velocity (m/s)."),
    "wave speed": ("v = fλ", "v = wave speed (m/s), f = frequency (Hz), λ = wavelength (m)."),
    "circle area": ("A = πr²", "A = area, r = radius."),
    "circumference": ("C = 2πr", "C = circumference, r = radius."),
    "quadratic formula": ("x = (-b ± √(b² - 4ac))/(2a)", "For ax² + bx + c = 0, where a ≠ 0."),
    "moles": ("n = m/M", "n = amount (mol), m = mass (g), M = molar mass (g/mol)."),
    "concentration": ("c = n/V", "c = concentration (mol/L if V is in L), n = amount (mol), V = volume (L)."),
    "photosynthesis": ("6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂", "Simplified overall equation for photosynthesis."),
}


@bot.tree.command(name="formula", description="Look up a common science or maths formula")
@app_commands.describe(topic="For example: ohms law, speed, moles, kinetic energy")
async def formula(interaction: discord.Interaction, topic: str):
    key = normalise(topic)
    match = next((value for name, value in FORMULAS.items() if normalise(name) == key), None)
    if not match:
        choices = ", ".join(FORMULAS.keys())
        await interaction.response.send_message(
            f"I don't have that formula saved yet. Try one of: {choices}",
            ephemeral=True
        )
        return
    equation, definitions = match
    embed = discord.Embed(title=f"Formula: {topic}", description=f"**{equation}**\n\n{definitions}", color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)


ELEMENTS = {
    "h": ("Hydrogen", 1, "Non-metal"), "he": ("Helium", 2, "Noble gas"),
    "li": ("Lithium", 3, "Alkali metal"), "be": ("Beryllium", 4, "Alkaline earth metal"),
    "b": ("Boron", 5, "Metalloid"), "c": ("Carbon", 6, "Non-metal"),
    "n": ("Nitrogen", 7, "Non-metal"), "o": ("Oxygen", 8, "Non-metal"),
    "f": ("Fluorine", 9, "Halogen"), "ne": ("Neon", 10, "Noble gas"),
    "na": ("Sodium", 11, "Alkali metal"), "mg": ("Magnesium", 12, "Alkaline earth metal"),
    "al": ("Aluminium", 13, "Post-transition metal"), "si": ("Silicon", 14, "Metalloid"),
    "p": ("Phosphorus", 15, "Non-metal"), "s": ("Sulfur", 16, "Non-metal"),
    "cl": ("Chlorine", 17, "Halogen"), "ar": ("Argon", 18, "Noble gas"),
    "k": ("Potassium", 19, "Alkali metal"), "ca": ("Calcium", 20, "Alkaline earth metal"),
    "fe": ("Iron", 26, "Transition metal"), "ni": ("Nickel", 28, "Transition metal"),
    "cu": ("Copper", 29, "Transition metal"), "zn": ("Zinc", 30, "Transition metal"),
    "br": ("Bromine", 35, "Halogen"), "ag": ("Silver", 47, "Transition metal"),
    "sn": ("Tin", 50, "Post-transition metal"), "i": ("Iodine", 53, "Halogen"),
    "xe": ("Xenon", 54, "Noble gas"), "au": ("Gold", 79, "Transition metal"),
    "hg": ("Mercury", 80, "Transition metal"), "pb": ("Lead", 82, "Post-transition metal"),
    "u": ("Uranium", 92, "Actinide"),
}
ALL_ELEMENT_ROWS = """H:Hydrogen;He:Helium;Li:Lithium;Be:Beryllium;B:Boron;C:Carbon;N:Nitrogen;O:Oxygen;F:Fluorine;Ne:Neon;Na:Sodium;Mg:Magnesium;Al:Aluminium;Si:Silicon;P:Phosphorus;S:Sulfur;Cl:Chlorine;Ar:Argon;K:Potassium;Ca:Calcium;Sc:Scandium;Ti:Titanium;V:Vanadium;Cr:Chromium;Mn:Manganese;Fe:Iron;Co:Cobalt;Ni:Nickel;Cu:Copper;Zn:Zinc;Ga:Gallium;Ge:Germanium;As:Arsenic;Se:Selenium;Br:Bromine;Kr:Krypton;Rb:Rubidium;Sr:Strontium;Y:Yttrium;Zr:Zirconium;Nb:Niobium;Mo:Molybdenum;Tc:Technetium;Ru:Ruthenium;Rh:Rhodium;Pd:Palladium;Ag:Silver;Cd:Cadmium;In:Indium;Sn:Tin;Sb:Antimony;Te:Tellurium;I:Iodine;Xe:Xenon;Cs:Caesium;Ba:Barium;La:Lanthanum;Ce:Cerium;Pr:Praseodymium;Nd:Neodymium;Pm:Promethium;Sm:Samarium;Eu:Europium;Gd:Gadolinium;Tb:Terbium;Dy:Dysprosium;Ho:Holmium;Er:Erbium;Tm:Thulium;Yb:Ytterbium;Lu:Lutetium;Hf:Hafnium;Ta:Tantalum;W:Tungsten;Re:Rhenium;Os:Osmium;Ir:Iridium;Pt:Platinum;Au:Gold;Hg:Mercury;Tl:Thallium;Pb:Lead;Bi:Bismuth;Po:Polonium;At:Astatine;Rn:Radon;Fr:Francium;Ra:Radium;Ac:Actinium;Th:Thorium;Pa:Protactinium;U:Uranium;Np:Neptunium;Pu:Plutonium;Am:Americium;Cm:Curium;Bk:Berkelium;Cf:Californium;Es:Einsteinium;Fm:Fermium;Md:Mendelevium;No:Nobelium;Lr:Lawrencium;Rf:Rutherfordium;Db:Dubnium;Sg:Seaborgium;Bh:Bohrium;Hs:Hassium;Mt:Meitnerium;Ds:Darmstadtium;Rg:Roentgenium;Cn:Copernicium;Nh:Nihonium;Fl:Flerovium;Mc:Moscovium;Lv:Livermorium;Ts:Tennessine;Og:Oganesson""".split(";")
for atomic_number, row in enumerate(ALL_ELEMENT_ROWS, start=1):
    symbol, name = row.split(":", 1)
    if symbol.lower() not in ELEMENTS:
        ELEMENTS[symbol.lower()] = (name, atomic_number, "Element")

ELEMENT_NAMES = {normalise(v[0]): (k, v) for k, v in ELEMENTS.items()}


@bot.tree.command(name="periodic-table", description="Look up common periodic table elements")
@app_commands.describe(element="Element name or symbol, e.g. carbon or Fe")
async def periodic_table(interaction: discord.Interaction, element: str):
    key = element.strip().lower()
    record = ELEMENTS.get(key) or (ELEMENT_NAMES.get(normalise(element)) or (None, None))[1]
    if not record:
        await interaction.response.send_message(
            "I couldn't find that element. Enter its full name or official chemical symbol, e.g. carbon or Fe.",
            ephemeral=True
        )
        return
    name, atomic_number, category = record
    symbol = next((sym for sym, val in ELEMENTS.items() if val == record), key.title())
    embed = discord.Embed(title=f"{name} ({symbol.title()})", color=discord.Color.green())
    embed.add_field(name="Atomic number", value=str(atomic_number))
    embed.add_field(name="Category", value=category)
    await interaction.response.send_message(embed=embed)


UNIT_TABLE = {
    "m": ("length", 1.0), "km": ("length", 1000.0), "cm": ("length", 0.01), "mm": ("length", 0.001),
    "g": ("mass", 1.0), "kg": ("mass", 1000.0), "mg": ("mass", 0.001),
    "s": ("time", 1.0), "sec": ("time", 1.0), "min": ("time", 60.0), "h": ("time", 3600.0),
    "ml": ("volume", 0.001), "l": ("volume", 1.0),
    "j": ("energy", 1.0), "kj": ("energy", 1000.0),
    "w": ("power", 1.0), "kw": ("power", 1000.0),
    "pa": ("pressure", 1.0), "kpa": ("pressure", 1000.0),
    "m/s": ("speed", 1.0), "km/h": ("speed", 1 / 3.6),
}


@bot.tree.command(name="convert", description="Convert common science units")
@app_commands.describe(value="Number to convert", from_unit="Starting unit", to_unit="Target unit")
async def convert(interaction: discord.Interaction, value: float, from_unit: str, to_unit: str):
    source = from_unit.strip().lower()
    target = to_unit.strip().lower()
    if not (value == value and abs(value) != float("inf")):
        await interaction.response.send_message("Please enter a finite number.", ephemeral=True)
        return

    if source in {"c", "°c", "celsius"} and target in {"k", "kelvin"}:
        result = value + 273.15
    elif source in {"k", "kelvin"} and target in {"c", "°c", "celsius"}:
        result = value - 273.15
    elif source in {"c", "°c", "celsius"} and target in {"f", "°f", "fahrenheit"}:
        result = value * 9 / 5 + 32
    elif source in {"f", "°f", "fahrenheit"} and target in {"c", "°c", "celsius"}:
        result = (value - 32) * 5 / 9
    elif source in UNIT_TABLE and target in UNIT_TABLE:
        source_type, source_factor = UNIT_TABLE[source]
        target_type, target_factor = UNIT_TABLE[target]
        if source_type != target_type:
            await interaction.response.send_message("Those units measure different quantities.", ephemeral=True)
            return
        result = value * source_factor / target_factor
    else:
        await interaction.response.send_message(
            "Unsupported units. Supported: m, km, cm, mm, g, kg, mg, s, min, h, mL, L, J, kJ, W, kW, Pa, kPa, m/s, km/h, °C, K and °F.",
            ephemeral=True
        )
        return
    await interaction.response.send_message(f"**{value:g} {from_unit} = {result:.6g} {to_unit}**")


@bot.tree.command(name="define", description="Get a student-friendly definition of a term")
@app_commands.describe(term="The science, maths or study term to define")
async def define(interaction: discord.Interaction, term: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await ask_ai(
            "Define terms for a secondary-school student. Give a concise definition, "
            "one simple example, and distinguish similar terms if needed. Use Discord-compatible "
            "Markdown only. Do not use HTML or LaTeX.",
            f"Define this term: {term}"
        )
        await send_long_response(interaction, f"**{term}**\n{result}")
    except Exception as error:
        print(f"/define error: {error}")
        await interaction.followup.send("I couldn't define that term right now. Check the Groq setup.")


# ------------------------------
# NEW FEATURE 1: HINT WITHOUT FULL SOLUTION
# ------------------------------

@bot.tree.command(name="hint", description="Get a useful hint without revealing the full solution")
@app_commands.describe(subject="Subject", question="The problem you are stuck on")
async def hint(interaction: discord.Interaction, subject: str, question: str):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        result = await ask_ai(
            "You are a supportive school tutor. Give ONE useful hint only, not the final answer and not a full worked solution. "
            "Point the student toward the relevant concept or first step. Use Discord Markdown and readable plain-text equations.",
            f"Subject: {subject}\nProblem: {question}"
        )
        await send_long_response(interaction, f"**A hint for {subject}**\n{result}", ephemeral=True)
    except Exception as error:
        print(f"/hint error: {error}")
        await interaction.followup.send("I couldn't generate a hint right now. Check the terminal and Groq configuration.", ephemeral=True)


# ------------------------------
# NEW FEATURE 2: INTERACTIVE PRACTICE QUIZ
# ------------------------------

DIFFICULTY_LEVELS = {
    "easy": "Year 10 level: foundational knowledge, direct applications, and one-step calculations.",
    "medium": "Year 10 level: more challenging Year 10 questions, requiring connected ideas or two-step reasoning. Do not use Year 11/12-only content.",
    "hard": "Year 12 level: senior-secondary depth, multi-step reasoning, precise terminology, and VCE-style applications where relevant.",
    "extra_hard": "University introductory level: undergraduate concepts and reasoning. State any advanced assumptions or definitions needed in the question so it remains self-contained."
}


class PracticeView(discord.ui.View):
    def __init__(self, owner_id: int, question: str, options: list[str],
                 answer_index: int, explanation: str, difficulty: str, topic: str):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.question = question
        self.options = options
        self.answer_index = answer_index
        self.explanation = explanation
        self.difficulty = difficulty
        self.topic = topic
        self.revealed = False

    def make_embed(self):
        body = "\\n".join(
            f"**{chr(65 + i)}.** {option}"
            for i, option in enumerate(self.options)
        )
        embed = discord.Embed(
            title=f"Practice Quiz • {self.difficulty.replace('_', ' ').title()}",
            description=f"**Topic:** {self.topic}\n\n{self.question}\n\n{body}",
            color=discord.Color.blurple()
        )
        if self.revealed:
            embed.add_field(
                name="Answer and explanation",
                value=(
                    f"**{chr(65 + self.answer_index)}. {self.options[self.answer_index]}**\n"
                    f"{self.explanation}"
                )[:1024],
                inline=False
            )
            embed.set_footer(text="Run /practice to try another question.")
        else:
            embed.add_field(
                name="Ready to check?",
                value="Try solving it first, then press **Show answer**.",
                inline=False
            )
            embed.set_footer(text="Only the person who started this quiz can use its buttons.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This practice quiz belongs to someone else. Run `/practice` to start your own.",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Show answer", style=discord.ButtonStyle.primary)
    async def show_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Acknowledge the button interaction first, then edit the original message.
        # This avoids the interaction failing silently if Discord is slow to respond.
        if self.revealed:
            await interaction.response.send_message(
                "The answer is already shown above.", ephemeral=True
            )
            return

        self.revealed = True
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.response.defer()
        if interaction.message:
            await interaction.message.edit(embed=self.make_embed(), view=self)


@bot.tree.command(name="practice", description="Generate a multiple-choice quiz at your chosen level")
@app_commands.describe(
    topic="Topic to practise, e.g. electricity, genetics, or calculus",
    difficulty="Choose the academic level"
)
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Easy • Year 10 foundations", value="easy"),
    app_commands.Choice(name="Medium • Year 10 challenge", value="medium"),
    app_commands.Choice(name="Hard • Year 12 / VCE", value="hard"),
    app_commands.Choice(name="Extra hard • University level", value="extra_hard"),
])
async def practice(
    interaction: discord.Interaction,
    topic: str,
    difficulty: app_commands.Choice[str]
):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        level_description = DIFFICULTY_LEVELS[difficulty.value]
        system_prompt = (
            "You are an accurate science and mathematics assessment writer. "
            "Generate exactly one clear multiple-choice question and return ONLY valid JSON "
            "with keys: question (string), options (array of exactly four short strings), "
            "answer_index (integer 0-3), explanation (string). Exactly one option must be correct. "
            "The question must genuinely match the requested academic level and topic. "
            "Use correct units and notation; independently verify any calculations and answer index. "
            "Avoid trick questions, ambiguous wording, and implausible distractors. "
            "Do not include markdown fences or extra text."
        )
        user_prompt = (
            f"Topic: {topic}\n"
            f"Selected difficulty: {difficulty.value}\n"
            f"Academic level requirements: {level_description}\n"
            "Make a fresh, self-contained question. For Year 12, use senior-secondary depth; "
            "for university level, test an introductory undergraduate concept and include all "
            "necessary assumptions in the question."
        )
        raw = await ask_ai(system_prompt, user_prompt)
        raw = re.sub(r"^```(?:json)?\\s*|\\s*```$", "", raw.strip(), flags=re.I)
        item = json.loads(raw)
        options = item["options"]
        answer_index = int(item["answer_index"])

        if (
            not isinstance(item.get("question"), str)
            or len(options) != 4
            or answer_index not in range(4)
            or not all(isinstance(option, str) and option.strip() for option in options)
            or not isinstance(item.get("explanation"), str)
        ):
            raise ValueError("AI returned invalid question data")

        view = PracticeView(
            interaction.user.id,
            item["question"].strip(),
            [option.strip() for option in options],
            answer_index,
            item["explanation"].strip(),
            difficulty.value,
            topic.strip()
        )
        await interaction.followup.send(
            embed=view.make_embed(),
            view=view,
            ephemeral=True
        )
    except Exception as error:
        print(f"/practice error: {error}")
        await interaction.followup.send(
            "I couldn't generate a practice question. Try again or choose another topic. "
            "Check the bot terminal for the exact error.",
            ephemeral=True
        )


# ------------------------------
# NEW FEATURE 3: USER-CREATED FLASHCARDS
# ------------------------------

@bot.tree.command(name="flashcard-add", description="Save a flashcard to your personal deck")
@app_commands.describe(question="Front of the card", answer="Back of the card", topic="Optional topic label")
async def flashcard_add(interaction: discord.Interaction, question: str, answer: str, topic: str = "general"):
    if len(question) > 500 or len(answer) > 1000:
        await interaction.response.send_message("Keep the question under 500 characters and the answer under 1000 characters.", ephemeral=True)
        return
    data = load_feature_data()
    key = str(interaction.user.id)
    deck = data["custom_flashcards"].setdefault(key, [])
    if len(deck) >= 100:
        await interaction.response.send_message("Your personal deck has reached 100 cards. Remove some before adding more.", ephemeral=True)
        return
    deck.append({"question": question, "answer": answer, "topic": topic[:80]})
    save_feature_data(data)
    await interaction.response.send_message(f"Saved! Your personal deck now has **{len(deck)} cards**. Use `/myflashcards` to revise.", ephemeral=True)


@bot.tree.command(name="myflashcards", description="Revise your personal saved flashcards")
async def myflashcards(interaction: discord.Interaction):
    data = load_feature_data()
    deck = data["custom_flashcards"].get(str(interaction.user.id), [])
    if not deck:
        await interaction.response.send_message("Your personal deck is empty. Add a card with `/flashcard-add`.", ephemeral=True)
        return
    cards = [(card["question"], card["answer"]) for card in deck]
    view = FlashcardView(random.sample(cards, len(cards)), interaction.user.id)
    await interaction.response.send_message(embed=view.make_embed(), view=view, ephemeral=True)


# ------------------------------
# NEW FEATURE 4: STUDY SESSION LOG
# ------------------------------

@bot.tree.command(name="studylog", description="Log a study session to your personal progress")
@app_commands.describe(subject="What you studied", minutes="Minutes spent studying", notes="Optional short note about what you covered")
async def studylog(interaction: discord.Interaction, subject: str, minutes: app_commands.Range[int, 1, 600], notes: str = ""):
    data = load_feature_data()
    key = str(interaction.user.id)
    sessions = data["study_logs"].setdefault(key, [])
    sessions.append({"date": today_key(), "subject": subject[:100], "minutes": int(minutes), "notes": notes[:300]})
    # Keep the latest 500 records per user so the file stays manageable.
    if len(sessions) > 500:
        del sessions[:-500]
    save_feature_data(data)
    await interaction.response.send_message(f"Logged **{minutes} minutes** of {subject}. Use `/progress` to see your totals.", ephemeral=True)


# ------------------------------
# NEW FEATURE 5: STUDY PROGRESS DASHBOARD
# ------------------------------

@bot.tree.command(name="progress", description="View your study time and learning progress")
async def progress(interaction: discord.Interaction):
    data = load_feature_data()
    key = str(interaction.user.id)
    sessions = data["study_logs"].get(key, [])
    total_minutes = sum(int(item.get("minutes", 0)) for item in sessions)
    today = today_key()
    today_minutes = sum(int(item.get("minutes", 0)) for item in sessions if item.get("date") == today)
    by_subject = {}
    for item in sessions:
        subject = item.get("subject", "Other")
        by_subject[subject] = by_subject.get(subject, 0) + int(item.get("minutes", 0))
    top_subjects = sorted(by_subject.items(), key=lambda item: item[1], reverse=True)[:5]
    subject_text = "\n".join(f"• **{name}:** {minutes} min" for name, minutes in top_subjects) or "No sessions logged yet."
    user = get_feature_user(data, interaction.user.id)
    embed = discord.Embed(title=f"{interaction.user.display_name}'s Study Progress", color=discord.Color.green())
    embed.add_field(name="Total study time", value=f"{total_minutes // 60} h {total_minutes % 60} min", inline=True)
    embed.add_field(name="Today", value=f"{today_minutes} min", inline=True)
    embed.add_field(name="XP", value=str(user.get("xp", 0)), inline=True)
    embed.add_field(name="Sessions logged", value=str(len(sessions)), inline=True)
    embed.add_field(name="Time by subject", value=subject_text[:1024], inline=False)
    embed.set_footer(text="Use /studylog after a session to keep your progress updated.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================================================
# END OF EXTRA FEATURES
# ==================================================


# ==================================================
# START BOT
# ==================================================

bot.run(TOKEN)