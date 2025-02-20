import os
import requests
from bs4 import BeautifulSoup
import json
import asyncio
import html
import re
from telegram import Bot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration Variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CROUS_SEARCH_URL = os.getenv("CROUS_URL")

# File to store previously seen listings
PREVIOUS_LISTINGS_FILE = "previous_listings.json"


def clean_text(text):
    """Fix encoding issues and strip whitespace."""
    if text:
        return html.unescape(text.strip())  # Decode HTML entities
    return "Unknown"


def escape_markdown(text):
    """Escape special characters for Telegram MarkdownV2"""
    escape_chars = r'_*\[\]()~`>#+-=|{}.!'
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)


async def load_previous_listings():
    """Load previously seen listings from a file."""
    try:
        with open(PREVIOUS_LISTINGS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


async def save_seen_listings(listings):
    """Save the new state of listings to a file."""
    with open(PREVIOUS_LISTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(listings, file, indent=4, ensure_ascii=False)


async def send_telegram_message(bot, message):
    """Send a message via Telegram bot."""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="MarkdownV2",
                               disable_web_page_preview=True)
        print("✅ Telegram message sent successfully.")
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")


async def scrape_crous_listings():
    """Scrape Crous Lyon website for new housing listings."""
    print("🔍 Checking for new Crous listings...")

    # Fetch the page
    try:
        response = requests.get(CROUS_SEARCH_URL, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding  # Ensure correct encoding
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching the website: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # Detect if no listings are found
    no_results = soup.find("h2", class_="SearchResults-desktop fr-h4 svelte-11sc5my")
    if no_results and "Aucun logement trouvé" in no_results.text:
        print("⚠️ No new listings available.")
        return

    # Find all listing elements
    listings = soup.select("ul.fr-grid-row.svelte-11sc5my > li.fr-col-12.fr-col-sm-6.fr-col-md-4.fr-col-lg-4")

    if not listings:
        print("⚠️ No listings were extracted from the page.")
        return

    # New state of listings
    new_state = []
    new_listings_detected = False

    for listing in listings:
        # Extract listing details safely
        title_tag = listing.find("h3", class_="fr-card__title")
        title = clean_text(title_tag.get_text()) if title_tag else "Unknown Title"

        link_tag = listing.find("a", href=True)
        link = f"https://trouverunlogement.lescrous.fr{link_tag['href']}" if link_tag else "No Link"

        location_tag = listing.find("p", class_="fr-card__desc")
        location = clean_text(location_tag.get_text()) if location_tag else "Unknown Location"

        price_tag = listing.find("p", class_="fr-badge")
        price = clean_text(price_tag.get_text()) if price_tag else "No Price Info"

        # Create a unique identifier for the listing
        listing_id = f"{title}-{link}"

        # Add to new state
        new_state.append({
            "id": listing_id,
            "title": title,
            "location": location,
            "price": price,
            "link": link
        })

    print(f"🔎 Extracted {len(new_state)} listings.")
    print(new_state)
    # Load previously saved listings
    previous_state = await load_previous_listings()

    # Compare new listings with previous ones
    for new_listing in new_state:
        if not any(prev["id"] == new_listing["id"] for prev in previous_state):
            new_listings_detected = True
            break  # Stop checking after the first new listing

    # If new listings exist, send a notification
    if new_listings_detected:
        message = f"📢 *New Crous Listings Found:* {len(new_state)} available\n\n"
        for listing in new_state:
            message += (
                f"🏡 *{escape_markdown(listing['title'])}*\n"
                f"📍 {escape_markdown(listing['location'])}\n"
                f"💰 {escape_markdown(listing['price'])}\n"
                f"🔗 [View Crous]({escape_markdown(listing['link'])})\n\n"
            )

        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await send_telegram_message(bot, message)
        print(f"✅ Sent update with {len(new_state)} listings.")
    else:
        print("🔄 No new listings detected. No message sent.")

    # Save the new state
    await save_seen_listings(new_state)


async def main():
    await scrape_crous_listings()


if __name__ == "__main__":
    asyncio.run(main())
