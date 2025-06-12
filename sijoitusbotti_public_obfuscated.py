import logging

logging.basicConfig(
    filename="app.log",  # Lokitiedoston nimi
    level=logging.DEBUG,  # Logitaso (DEBUG tallentaa kaikki merkittävät tapahtumat)
    format="%(asctime)s - %(levelname)s - %(message)s"  # Lokin muoto
)

import sys
import signal
import time
import yfinance as yf
import schedule
from telegram import Bot
from random import uniform
import asyncio
import json
from subprocess import Popen, PIPE
import requests
import os
import getpass
from datetime import datetime
import pandas as pd
import datetime
import aiohttp
import re
import pyfiglet
from statistics import median
import math

running_task = None  # Pitää kirjaa suoritettavasta analyysitehtävästä
start_time = 0     # Tallentaa suorituksen aloitusajan

def display_banner():
    banner = pyfiglet.figlet_format("SIJOITUSBOTTI", font="slant")  # Voit kokeilla myös muita fontteja
    print(banner)

TELEGRAM_TOKEN = None
TELEGRAM_CHAT_ID = None

CREDENTIALS_LOADED = False
bot = None
NEWS_API_KEY = None

ETF_DB = "etf_data.db"

OWNED_STOCKS_FILE = "owned_stocks.txt"
OWNED_ETFS_FILE = "owned_etfs.txt"
STOCK_TICKERS_FILE = "tickers.txt"
ETF_TICKERS_FILE = "etf_tickers.txt"
FAILED_ASSETS_FILE = "failed_assets.json"
REMOVED_ASSETS_FILE = "removed_assets.txt"

NEWSAPI_URL = "https://newsapi.org/v2/everything"
STOCK_NEWS_SOURCES = [
    "bloomberg", "cnbc", "marketwatch", "yahoo finance", "reuters",  
    "wall street journal", "financial times", "forbes", "business insider", "seeking alpha",
    "investopedia", "motley fool", "barron's", "zacks investment research",
    "arvopaperi", "kauppalehti", "taloussanomat", "inderes", "salkunrakentaja"
]
ETF_NEWS_SOURCES = [
    "bloomberg", "cnbc", "marketwatch", "yahoo finance", "reuters", 
    "wall street journal", "financial times", "forbes", "business insider", "seeking alpha",
    "morningstar", "etf.com", "etf trends", "investopedia", "etf daily news"
]
CRITICAL_KEYWORDS_STOCKS = [
    "bankruptcy", "ceo resigns", "criminal charges", "collapse", "sec investigation",
    "fraud", "lawsuit", "scandal", "corruption", "insolvency", "mass layoffs"
]
CRITICAL_KEYWORDS_ETF = [
    "fund closure", "liquidation", "delisting", "high redemption", "outflows surge",
    "market crash", "bear market", "structural issues", "fund mismanagement",
    "fund shutdown", "abnormal tracking error", "index removal", "severe underperformance"
]
NEGATIVE_KEYWORDS_STOCKS = [
    "missed expectations", "plunges", "drops", "warning", "profit warning",
    "losses", "shutdown", "sell-off", "stock downgrade", "bad earnings report",
    "supply chain issues", "debt crisis", "recession risk", "high volatility"
]
NEGATIVE_KEYWORDS_ETF = [
    "high volatility", "sector downturn", "outflows increase", "investor withdrawals",
    "performance lagging", "market headwinds", "fund redemption issues", "economic slowdown",
    "rebalancing risks", "passive fund risk", "ETF fee hike", "issuer downgrade", "low liquidity",
    "ETF tracking error", "rising management costs"
]

NEWS_API_CALLS_LIMIT = 50  # **Maksimi 50 hakua 12h sisällä**
OWNED_STOCKS_CALLS_LIMIT = 10  # **Omistetuille osakkeille 10 hakua per 12h**
OWNED_ETFS_CALLS_LIMIT = 10  # **Omistetuille ETF:lle 10 hakua per 12h**
GENERAL_STOCKS_CALLS_LIMIT = 15  # **Yleisille osakehauille 15 hakua per 12h**
GENERAL_ETFS_CALLS_LIMIT = 15  # **Yleisille ETF-hauille 15 hakua per 12h**
TOTAL_API_LIMIT = 50  # **Kokonaisuudessaan 50 hakua per 12h**

LAST_NEWS_FETCH_FILE = "last_news_fetch.json"
NEWS_API_USAGE_FILE = "news_api_usage.json"
FETCHED_ASSETS_FILE = "fetched_assets.json"

def load_assets_from_file(filename):
    """Lataa tiedoston rivit listaksi."""
    try:
        with open(filename, "r") as f:
            return set(line.strip().upper() for line in f)
    except FileNotFoundError:
        return set()

def save_assets_to_file(filename, assets):
    """Tallentaa listan tiedostoon."""
    with open(filename, "w") as f:
        for asset in sorted(assets):
            f.write(f"{asset}\n")

def list_owned_assets(owned_stocks, owned_etfs):
    """Tulostaa käyttäjälle listan omistetuista osakkeista ja ETF:istä."""
    print("\n📜 **Omistetut osakkeet:**")
    if owned_stocks:
        print(", ".join(sorted(owned_stocks)))
    else:
        print("🔹 Ei omistettuja osakkeita.")

    print("\n📜 **Omistetut ETF:t:**")
    if owned_etfs:
        print(", ".join(sorted(owned_etfs)))
    else:
        print("🔹 Ei omistettuja ETF:iä.")

async def get_user_input(owned_stocks, owned_etfs, valid_stocks, valid_etfs):
    """
    Odottaa käyttäjän syötteen ja lisää tai poistaa osakkeen/ETF:n omistettujen listalta.
    Tallentaa tiedostoon jokaisen muutoksen jälkeen, mutta vain jos muutos tapahtui.
    """
    try:
        while True:
            list_owned_assets(owned_stocks, owned_etfs)
            asset = await asyncio.to_thread(input, "\n➕ Lisää osake tai ETF (poista -tunnus, tyhjä jatkaa): ")
            asset = asset.strip().upper()

            if asset == "":
                print("\n✅ Omistuslista päivitetty. Jatketaan ohjelman suorittamista...")
                break

            change_made = False  # ✅ Muutoksen seuranta

            if asset.startswith("-"):
                asset_to_remove = asset[1:]
                if asset_to_remove in owned_stocks:
                    owned_stocks.remove(asset_to_remove)
                    remove_owned_asset_from_db(asset_to_remove, "stock")  # Poistetaan myös tietokannasta
                    print(f"❌ Osake {asset_to_remove} poistettu.")
                    change_made = True
                elif asset_to_remove in owned_etfs:
                    owned_etfs.remove(asset_to_remove)
                    remove_owned_asset_from_db(asset_to_remove, "etf")  # Poistetaan myös tietokannasta
                    print(f"❌ ETF {asset_to_remove} poistettu.")
                    change_made = True
                else:
                    print(f"⚠️ {asset_to_remove} ei löytynyt listalta.")
            else:
                if asset in valid_stocks:
                    if asset not in owned_stocks:
                        owned_stocks.append(asset)
                        print(f"✅ Osake {asset} lisätty.")
                        change_made = True
                    else:
                        print(f"⚠️ Osake {asset} on jo listalla.")
                elif asset in valid_etfs:
                    if asset not in owned_etfs:
                        owned_etfs.append(asset)
                        print(f"✅ ETF {asset} lisätty.")
                        change_made = True
                    else:
                        print(f"⚠️ ETF {asset} on jo listalla.")
                else:
                    print(f"❌ {asset}: Tunnusta ei löytynyt `tickers.txt` tai `etf_tickers.txt` -tiedostoista.")

            if change_made:  # ✅ Tallennetaan vain jos muutos tapahtui
                save_assets_to_file(OWNED_STOCKS_FILE, owned_stocks)
                save_assets_to_file(OWNED_ETFS_FILE, owned_etfs)
                print("📌 Muutokset tallennettu.")

    except asyncio.TimeoutError:
        print("\n🕒 Aikaraja ylittyi, jatketaan ilman syötettä.")

OWNED_ASSETS_DB = "owned_assets.db"  # Tietokanta omistetuille osakkeille ja ETF:ille

async def prompt_for_owned_assets(is_first_run=True):
    """
    Kysyy käyttäjältä omistukset ohjelman käynnistyessä ja tallentaa ne tietokantaan.
    """
    owned_stocks = load_owned_assets_from_db("stock")  # Lataa omistetut osakkeet
    owned_etfs = load_owned_assets_from_db("etf")  # Lataa omistetut ETF:t

    valid_stocks = load_assets_from_file(STOCK_TICKERS_FILE)
    valid_etfs = load_assets_from_file(ETF_TICKERS_FILE)

    if is_first_run:
        print("💡 Lisää tai poista omistamiasi osakkeita ja ETF:iä. Anna osakkeen/ETF:n tunnus ja paina Enter.")
        print("   Poista kirjoittamalla -tunnus (esim. -AAPL). Lopeta jättämällä syöte tyhjäksi.")

        try:
            await asyncio.wait_for(get_user_input(owned_stocks, owned_etfs, valid_stocks, valid_etfs), timeout=120.0)
        except asyncio.TimeoutError:
            print("\n🕒 Aikaraja ylittyi, jatketaan ilman syötettä.")

        update_owned_assets_in_db(owned_stocks, "stock")
        update_owned_assets_in_db(owned_etfs, "etf")

    return owned_stocks, owned_etfs

def load_owned_assets_from_db(asset_type):
    """
    Lataa tietokannasta omistetut osakkeet tai ETF:t.
    """
    conn = sqlite3.connect(OWNED_ASSETS_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT ticker FROM owned_assets WHERE type = ?", (asset_type,))
    assets = [row[0] for row in cursor.fetchall()]

    conn.close()
    return assets

def update_owned_assets_in_db(assets, asset_type):
    """
    Lisää tai päivittää omistetut osakkeet tai ETF:t tietokantaan ja hakee viimeisimmän hinnan SQLite:stä.
    Päivittää hinnan vain, jos se on muuttunut.
    """
    conn = sqlite3.connect(OWNED_ASSETS_DB)
    cursor = conn.cursor()

    for ticker in assets:
        latest_price = fetch_latest_price(ticker, asset_type)
        purchase_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if latest_price is None:
            print(f"⚠️ Ei voitu hakea hintaa tietokannasta osakkeelle {ticker}, jätetään lisäämättä.")
            continue

        cursor.execute("SELECT purchase_price, latest_price FROM owned_assets WHERE ticker = ?", (ticker,))
        existing_record = cursor.fetchone()

        if existing_record:
            old_latest_price = existing_record[1]  # Nykyinen latest_price tietokannassa
            
            if old_latest_price == latest_price:
                print(f"⏳ {ticker}: Hinta ({latest_price}) ei ole muuttunut, ei päivitetä.")
                continue  # Ei tehdä turhaa päivitystä

            cursor.execute("""
                UPDATE owned_assets 
                SET latest_price = ?, last_update = ? 
                WHERE ticker = ?
            """, (latest_price, purchase_date, ticker))
            print(f"🔄 Päivitettiin {ticker}: uusi hinta {latest_price} (vanha {old_latest_price})")

        else:
            cursor.execute("""
                INSERT INTO owned_assets (ticker, type, purchase_price, purchase_date, latest_price, last_update)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticker, asset_type, latest_price, purchase_date, latest_price, purchase_date))
            print(f"✅ {ticker} lisätty tietokantaan ostohintaan {latest_price}")

    conn.commit()
    conn.close()

def fetch_latest_price(ticker, asset_type):
    """
    Hakee osakkeen tai ETF:n viimeisimmän hinnan SQLite-tietokannasta.
    """
    if asset_type == "stock":
        db_file = DB_FILE  # stocks.db
        table = "x1"  # Oikea taulu osakkeille
        date_column = "datetime"  # Osakkeilla päivämääräsarake on "datetime"
    elif asset_type == "etf":
        db_file = ETF_DB  # etf_data.db
        table = "etf_prices"  # Oikea taulu ETF:ille
        date_column = "date"  # ETF:illä päivämääräsarake on "date"
    else:
        print(f"⚠️ Tuntematon asset_type {asset_type} tickerille {ticker}")
        return None

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT close_price FROM {table} 
            WHERE ticker = ? 
            ORDER BY {date_column} DESC 
            LIMIT 1
        """, (ticker,))
        
        result = cursor.fetchone()
        conn.close()

        if result:
            return round(result[0], 2)
        else:
            print(f"⚠️ Ei löydetty hintaa tietokannasta {db_file} tickerille {ticker}.")
            return None

    except sqlite3.Error as e:
        print(f"⚠️ Virhe SQLite-haussa tickerille {ticker}: {e}")
        return None

def remove_owned_asset_from_db(ticker, asset_type):
    """Poistaa osakkeen/ETF:n tietokannasta."""
    conn = sqlite3.connect(OWNED_ASSETS_DB)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM owned_assets WHERE ticker = ? AND type = ?", (ticker, asset_type))
    conn.commit()  # Muista varmistaa, että commit on suoritettu, jotta muutos tallentuu tietokantaan
    conn.close()
    print(f"✅ {ticker} poistettu tietokannasta.")


    except Exception as e:
        print(f"❌ {e}")
        print("Salasana syötetty virheellisesti. Ohjelman suoritus loppuu.")
        exit(1)  # Lopetetaan ohjelman suoritus


async def load_credentials():
    global CREDENTIALS_LOADED, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, bot, NEWS_API_KEY
    
    if not CREDENTIALS_LOADED:

        lines = decrypted_data.strip().split('\n')
        
        if len(lines) < 3:
            raise ValueError("Tiedostossa on puutteelliset tiedot.")
        
        for line in lines:
            key, value = [part.strip() for part in line.strip().split('=')]  # Poistetaan välilyönnit

            if key == "TELEGRAM_TOKEN":
                TELEGRAM_TOKEN = value.strip('"')  # Poistetaan mahdolliset ympäröivät lainausmerkit
            elif key == "TELEGRAM_CHAT_ID":
                TELEGRAM_CHAT_ID = int(value.strip())  # Muutetaan luku kokonaisluvuksi
            elif key == "NEWS_API_KEY":
                NEWS_API_KEY = value.strip('"')  # Poistetaan mahdolliset ympäröivät lainausmerkit

        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not NEWS_API_KEY:
            print("❌ Virheelliset tunnukset, varmista että kaikki tiedot ovat oikein.")
            exit(1)

        bot = Bot(token=TELEGRAM_TOKEN)  # Luo Bot-olio vain, jos kaikki tiedot on ladattu oikein
        CREDENTIALS_LOADED = True
        print("✅ Token, Chat ID ja NewsAPI-avain ladattu onnistuneesti!")

def load_assets_from_file(filename):
    """Lataa osakkeet tekstitiedostosta ja palauttaa listan."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            assets = [line.strip() for line in f.readlines() if line.strip()]  # Poistetaan tyhjät rivit
        return assets
    except Exception as e:
        print(f"⚠️ ERROR: Ei voitu ladata osakkeita tiedostosta {filename}: {e}")
        return []

def load_company_dict(filename):
    """Lataa nimet JSON-tiedostosta ja palauttaa sanakirjan."""
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

ASSETS = load_assets_from_file("tickers.txt")
ETF_TICKERS = load_assets_from_file("etf_tickers.txt")

COMPANY_NAME_DICT = load_company_dict("company_name_dict.json")
ETF_NAME_DICT = load_company_dict("etf_name_dict.json")

MAX_CONCURRENT_REQUESTS = 5 

def log_removed_asset(asset, reason):
    with open(REMOVED_ASSETS_FILE, "a") as file:
        file.write(f"{asset}: {reason}\n")

import sqlite3

DB_FILE = "stocks.db"

def load_historical_data(ticker):
    """Lataa osakkeen historialliset tiedot SQLite-tietokannasta."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT datetime, open_price, high_price, low_price, close_price, 
               adjusted_close, volume, dividends, stock_splits
        FROM x1
        WHERE ticker = ?
        ORDER BY datetime ASC
    ''', (ticker,))
    
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "Datetime": row[0],
            "Open": row[1],
            "High": row[2],
            "Low": row[3],
            "Close": row[4],
            "Adjusted Close": row[5],
            "Volume": row[6],
            "Dividends": row[7],
            "Stock Splits": row[8],
        }
        for row in rows
    ]

def save_historical_data_new(asset, new_data):
    """Tallentaa osaketiedot SQLite-tietokantaan vain, jos ne eivät jo ole siellä."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    datetime_value = new_data.get("Datetime")
    if isinstance(datetime_value, pd.Timestamp):
        datetime_value = datetime_value.isoformat()  # Muunnetaan str-muotoon

    cursor.execute('''
        SELECT 1 FROM x1 WHERE ticker = ? AND datetime = ?
    ''', (asset, datetime_value))

    if cursor.fetchone():
        conn.close()
        return  # Poistutaan funktiosta ilman lisäystä

    cursor.execute('''
        INSERT INTO x1 (ticker, datetime, open_price, high_price, low_price, close_price, 
                               adjusted_close, volume, dividends, stock_splits)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        asset,
        datetime_value,
        new_data.get("Open"),
        new_data.get("High"),
        new_data.get("Low"),
        new_data.get("Close"),
        new_data.get("Adjusted Close"),
        new_data.get("Volume"),
        new_data.get("Dividends"),
        new_data.get("Stock Splits")
    ))

    conn.commit()
    conn.close()


def load_historical_etf_data(ticker):
    """Lataa ETF:n historialliset tiedot SQLite-tietokannasta."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT date, open_price, high_price, low_price, close_price, volume, dividends, stock_splits, capital_gains
        FROM etf_prices
        WHERE ticker = ?
        ORDER BY date ASC
    ''', (ticker,))
    
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "Date": row[0],
            "Open": row[1],
            "High": row[2],
            "Low": row[3],
            "Close": row[4],
            "Volume": row[5],
            "Dividends": row[6],
            "Stock Splits": row[7],
            "Capital Gains": row[8],
        }
        for row in rows
    ]

def save_historical_etf_data(ticker, new_data):
    """Tallentaa ETF-tiedot SQLite-tietokantaan vain, jos ne eivät jo ole siellä."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    date_value = new_data.get("Date")

    cursor.execute('''
        SELECT 1 FROM etf_prices WHERE ticker = ? AND date = ?
    ''', (ticker, date_value))

    if cursor.fetchone():
        conn.close()
        return  # Poistutaan funktiosta ilman lisäystä

    cursor.execute('''
        INSERT INTO etf_prices (ticker, date, open_price, high_price, low_price, close_price, volume, dividends, stock_splits, capital_gains)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        ticker,
        date_value,
        new_data.get("Open"),
        new_data.get("High"),
        new_data.get("Low"),
        new_data.get("Close"),
        new_data.get("Volume"),
        new_data.get("Dividends", 0.0),
        new_data.get("Stock Splits", 0.0),
        new_data.get("Capital Gains", 0.0)
    ))

    conn.commit()
    conn.close()


def load_json(filename):
    try:
        with open(filename, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    """Tallentaa JSON-tiedoston ja muuntaa Timestamp-objektit merkkijonoiksi."""
    def convert(obj):
        if isinstance(obj, pd.Timestamp):  # Tarkistetaan, onko objekti Timestamp
            return obj.isoformat()  # Muunnetaan ISO 8601 -merkkijonoksi
        raise TypeError(f"Type {type(obj)} is not serializable")

    with open(filename, "w") as file:
        json.dump(data, file, indent=4, default=convert)  # Käytetään custom-muunnosta

def compare_with_previous_data(asset, new_data):
    try:

        if isinstance(new_data, pd.DataFrame):
            new_data = new_data.iloc[-1].to_dict()  # Ota viimeinen rivi ja muuta se sanakirjaksi
        elif isinstance(new_data, list) and len(new_data) > 0 and isinstance(new_data[0], dict):
            new_data = new_data[-1]  # Otetaan listan viimeinen alkio

        
        if not isinstance(new_data, dict):
            print(f"❌ ERROR: {asset} - new_data EI OLE dict, vaan {type(new_data)}!")
            return False, False, False
        
        if isinstance(new_data, list):
            print(f"❌ ERROR: new_data on lista, mutta sen pitäisi olla sanakirja! Sisältö: {new_data}")

        current_price = float(new_data["Close"]) if "Close" in new_data else None
        if current_price is None:
            print(f"⚠️ DEBUG: Ei saatu sulkemishintaa osakkeelle {asset}, kokeillaan avaimia: {list(new_data.keys())}")
            return False, False, False

        print(f"{asset} nykyinen hinta: {current_price}")

        historical_prices = find_closing_prices(asset)
        if not historical_prices:
            print(f"⚠️ DEBUG: Ei historiallista dataa osakkeelle {asset}.")
            return False, False, False

        try:
            last_close_price = float(historical_prices[-1])
        except (IndexError, ValueError):
            print(f"⚠️ DEBUG: Virhe historiatiedoissa osakkeelle {asset}, ei voitu hakea viimeistä sulkemishintaa.")
            return False, False, False

        price_dropped = current_price < last_close_price

        below_average = False
        if len(historical_prices) >= 10:
            moving_average_10d = sum(historical_prices[-10:]) / 10
            below_average = current_price < 0.9 * moving_average_10d

        below_5d_avg = False
        if len(historical_prices) >= 5:
            moving_average_5d = sum(historical_prices[-5:]) / 5
            below_5d_avg = current_price < moving_average_5d

        return price_dropped, below_average, below_5d_avg

    except Exception as e:
        print(f"⚠️ DEBUG: Virhe compare_with_previous_data:ssa osakkeelle {asset}: {e}")
        return False, False, False

logger = logging.getLogger()
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("news_api_usage.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)

def load_last_news_fetch():
    print("DEBUG: Ladataan last_news_fetch.json")
    if os.path.exists(LAST_NEWS_FETCH_FILE):
        with open(LAST_NEWS_FETCH_FILE, "r") as file:
            data = json.load(file)
            print(f"DEBUG: Tiedoston sisältö: {data}")  # 🟢 Debug
            return data
    return {}

def save_last_news_fetch(last_fetch_times):
    print(f"DEBUG: Tallennetaan last_news_fetch.json: {last_fetch_times}")  # 🟢 Debug
    with open(LAST_NEWS_FETCH_FILE, "w") as file:
        json.dump(last_fetch_times, file)

    print(f"✅ DEBUG: Tallennettu last_news_fetch.json: {last_fetch_times}")

def load_news_api_usage():
    """Lataa uutis-API:n käyttötilastot ja varmistaa, että kaikki avaimet ovat olemassa."""
    usage_data = load_json(NEWS_API_USAGE_FILE) or {}

    default_values = {
        "calls_today": 0,
        "owned_stocks_calls_today": 0,
        "owned_etfs_calls_today": 0,
        "general_stocks_calls_today": 0,
        "general_etfs_calls_today": 0,
        "last_reset_time": datetime.datetime.now().isoformat() if "last_reset_time" not in usage_data else usage_data["last_reset_time"]
    }

    missing_keys = [key for key in default_values if key not in usage_data]

    if missing_keys:
        for key in missing_keys:
            usage_data[key] = default_values[key]
            print(f"🔍 DEBUG: Lisätään puuttuva kenttä `{key}` tiedostoon `news_api_usage.json`.")

        save_news_api_usage(usage_data)  # ✅ Tallennetaan korjattu versio

    return usage_data

def save_news_api_usage(data):
    """
    Tallentaa uutis-API:n käyttötilastot tiedostoon.
    Tarkistaa, että kaikki tarvittavat kentät ovat mukana ennen tallennusta.
    """
    required_keys = {
        "calls_today", "owned_stocks_calls_today", "owned_etfs_calls_today",
        "general_stocks_calls_today", "general_etfs_calls_today", "last_reset_time"
    }

    missing_keys = required_keys - data.keys()
    if missing_keys:
        print(f"⚠️ ERROR: Puuttuvia avaimia `news_api_usage.json` tiedostossa: {missing_keys}")
        return  # ⚠️ Ei tallenneta puutteellista dataa

    save_json(NEWS_API_USAGE_FILE, data)
    print(f"✅ DEBUG: `news_api_usage.json` päivitetty onnistuneesti.")

def update_news_api_usage(call_type):
    """
    Päivittää API-kutsujen laskurin 12h välein. 
    - "owned_stock": Omistetuille osakkeille
    - "owned_etf": Omistetuille ETF:lle
    - "general_stock": Yleinen osakehaku
    - "general_etf": Yleinen ETF-haku
    """
    usage_data = load_news_api_usage()
    now = datetime.datetime.now()

    last_reset_time_str = usage_data.get("last_reset_time", "")
    last_reset_time = datetime.datetime.fromisoformat(last_reset_time_str) if last_reset_time_str else now - datetime.timedelta(hours=13)

    if (now - last_reset_time).total_seconds() > 12 * 3600:
        usage_data = {
            "calls_today": 0,
            "owned_stocks_calls_today": 0,
            "owned_etfs_calls_today": 0,
            "general_stocks_calls_today": 0,
            "general_etfs_calls_today": 0,
            "last_reset_time": now.isoformat()
        }
        print(f"🔄 DEBUG: API-kutsujen laskurit nollattu! (Viimeisin nollaus: {last_reset_time})")

    limits = {
        "owned_stock": OWNED_STOCKS_CALLS_LIMIT,
        "owned_etf": OWNED_ETFS_CALLS_LIMIT,
        "general_stock": GENERAL_STOCKS_CALLS_LIMIT,
        "general_etf": GENERAL_ETFS_CALLS_LIMIT,
    }

    call_key = f"{call_type}s_calls_today" if "stock" in call_type else f"{call_type}_calls_today"
    if usage_data[call_key] >= limits[call_type]:
        print(f"⚠️ {call_type} hakuraja ({limits[call_type]}) saavutettu! Ei lisätä uutta hakua.")
        return False

    usage_data["calls_today"] += 1
    usage_data[call_key] += 1
    print(f"✅ Päivitetty {call_type} hakulaskuri: {usage_data[call_key]}/{limits[call_type]} (12h raja)")

    save_news_api_usage(usage_data)
    return True

def can_fetch_news(asset, asset_type, fetched_assets, owned_assets):
    """
    Varmistaa, voidaanko uutisia hakea tälle osakkeelle tai ETF:lle tänään.
    
    - `asset_type`: joko "stock" tai "etf"
    - `owned_assets`: lista käyttäjän omistamista osakkeista tai ETF:stä
    """
    today = datetime.date.today().isoformat()
    last_fetch_date = fetched_assets.get(asset, "")

    call_type = f"general_{asset_type}" if asset not in owned_assets else f"owned_{asset_type}"

    if last_fetch_date != today and update_news_api_usage(call_type):
        fetched_assets[asset] = today
        save_json(FETCHED_ASSETS_FILE, fetched_assets)
        return True

    return False

def is_valid_asset(asset, filename):
    """Tarkistaa, löytyykö asset annetusta tiedostosta."""
    if not os.path.exists(filename):
        print(f"⚠️ Virhe: Tiedostoa {filename} ei löydy.")
        return False

    with open(filename, "r") as file:
        valid_assets = {line.strip().upper() for line in file.readlines()}

    return asset.upper() in valid_assets

def get_asset_type(asset):
    """Tarkistaa, onko asset ETF vai osake `tickers.txt` ja `etf_tickers.txt` perusteella."""
    if is_valid_asset(asset, "etf_tickers.txt"):
        return "etf"
    elif is_valid_asset(asset, "tickers.txt"):
        return "stock"
    return None  # Jos tunnusta ei löydy mistään

def fetch_stock_news(asset, owned_stocks):
    """
    Hakee uutiset **vain osakkeille** ja suodattaa ne hyväksytyistä lähteistä.
    """
    if asset not in owned_stocks:
        print(f"⚠️ {asset}: Ei löydy omistetuista osakkeista, ohitetaan uutishaku.")
        return [], [], []

    print(f"🔍 DEBUG: Aloitetaan osakeuutishaku kohteelle {asset}")

    fetched_assets = load_json(LAST_NEWS_FETCH_FILE)

    if not can_fetch_news(asset, "stock", fetched_assets, owned_stocks):
        print(f"⚠️ {asset}: Uutishaku EI SALLITTU tarkistuksen perusteella.")
        return [], [], []

    usage_data = load_news_api_usage()
    total_calls_today = usage_data["calls_today"]
    owned_stocks_calls_today = usage_data["owned_stocks_calls_today"]

    remaining_calls = TOTAL_API_LIMIT - total_calls_today
    remaining_owned_stocks_calls = OWNED_STOCKS_CALLS_LIMIT - owned_stocks_calls_today

    if total_calls_today >= NEWS_API_CALLS_LIMIT:
        print(f"⚠️ {asset}: Päivittäinen uutishakujen raja ({NEWS_API_CALLS_LIMIT}) saavutettu, ei haeta.")
        return [], [], []

    if owned_stocks_calls_today >= OWNED_STOCKS_CALLS_LIMIT:
        print(f"🔍 {asset}: Omistettujen osakkeiden limiitti täynnä! Ei haeta uutisia.")
        return [], [], []

    print(f"🔍 {asset}: Haetaan uutisia... (Jäljellä olevat kutsut: {remaining_calls}, Omistetuille: {remaining_owned_stocks_calls})")

    fetched_assets[asset] = datetime.date.today().isoformat()
    save_json(LAST_NEWS_FETCH_FILE, fetched_assets)

    company_names = load_json("company_name_dict.json")
    company_name = company_names.get(asset, asset)

    if not isinstance(company_name, str):
        print(f"⚠️ ERROR: `company_name` EI ole merkkijono kohteelle {asset}: {type(company_name)} - {company_name}")
        company_name = asset

    print(f"🔍 Haetaan uutisia kohteelle: {company_name}")

    search_terms = f"{asset} OR \"{company_name}\""
    params = {
        "q": search_terms,
        "apiKey": NEWS_API_KEY,
        "language": "en,fi",
        "sortBy": "publishedAt",
        "pageSize": 10
    }

    time.sleep(2)  # ✅ Estetään liian nopeat pyynnöt
    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=10)

        if response.status_code == 429:
            print(f"⚠️ DEBUG: Liian monta pyyntöä NewsAPI:lle, odotetaan ja yritetään uudelleen.")
            time.sleep(60)
            response = requests.get(NEWSAPI_URL, params=params, timeout=10)

        if response.status_code != 200:
            logging.error(f"❌ ERROR: Virhe uutishakuun kohteelle {asset}: {response.status_code} - {response.text}")
            return [], [], []

        try:
            news_data = response.json()
        except ValueError:
            logging.error(f"❌ ERROR: NewsAPI palautti virheellisen JSON-datan kohteelle {asset}.")
            return [], [], []

        articles = news_data.get("articles", [])
        if not isinstance(articles, list):
            print(f"⚠️ ERROR: `articles` ei ole lista, vaan {type(articles)} - {articles}")
            return [], [], []

        filtered_news = []
        for article in articles:
            if not isinstance(article, dict):
                continue

            title = article.get("title", "")
            description = article.get("description", "")
            source = article.get("source", {}).get("name", "Tuntematon lähde")

            if not title:
                print(f"⚠️ DEBUG: Uutisartikkelilta puuttuu otsikko: {article}")
                continue

            if not description:
                print(f"⚠️ DEBUG: Uutisartikkelilta puuttuu kuvaus: {article}")
                continue

            title = title.lower()
            description = description.lower()

            if not isinstance(source, str):
                source = "Tuntematon lähde"

            source = source.lower()

            if source not in STOCK_NEWS_SOURCES:
                print(f"⚠️ DEBUG: Ohitetaan uutinen {title} ({source}) - Ei hyväksytyllä lähdelistalla")
                continue

            if asset.lower() not in title and asset.lower() not in description and company_name.lower() not in title and company_name.lower() not in description:
                print(f"⚠️ DEBUG: Ohitetaan uutinen - Ei mainintaa: {title}")
                save_rejected_news(article)  # 🔴 Tallennetaan hylätty uutinen
                continue

            filtered_news.append({
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "source": source,
            })

        negative_news, critical_news = analyze_news_sentiment(filtered_news)

        print(f"✅ DEBUG: Haettu {len(filtered_news)} uutista kohteelle {asset}.")
        return filtered_news, negative_news, critical_news

    except requests.exceptions.RequestException as e:
        logging.error(f"⚠️ ERROR: HTTP-virhe kohteelle {asset}: {e}")

    return [], [], []

def analyze_news_sentiment(news_articles):
    """Analysoi uutisten sentimentin ja palauttaa kriittiset ja negatiiviset uutiset erikseen."""
    critical_news = []
    negative_news = []

    if not isinstance(news_articles, list):
        print(f"⚠️ ERROR: Uutislista ei ole lista: {type(news_articles)} - {news_articles}")
        return [], []  

    for article in news_articles:
        if not isinstance(article, dict):
            print(f"⚠️ ERROR: Uutisartikkeli ei ole dict: {type(article)} - {article}")
            continue

        title = article.get("title", "").lower()
        description = article.get("description", "").lower()

        source = article.get("source", {})

        if isinstance(source, dict):
            source_name = source.get("name", "Tuntematon lähde")
        elif isinstance(source, str):  # Jos lähde on vahingossa jo merkkijono
            source_name = source
        else:
            print(f"⚠️ ERROR: `source` tuntematon tietotyyppi: {type(source)} - {source}")
            source_name = "Tuntematon lähde"

        source_name = source_name.lower() if isinstance(source_name, str) else "tuntematon lähde"

        if any(word in title or word in description for word in CRITICAL_KEYWORDS_STOCKS):
            critical_news.append(f"{title} ({source_name})")  

        elif any(word in title or word in description for word in NEGATIVE_KEYWORDS_STOCKS):
            negative_news.append(f"{title} ({source_name})")  

    return negative_news, critical_news

REJECTED_NEWS_FILE = "rejected_news.json"

def load_rejected_news():
    """Lataa hylätyt uutiset tiedostosta."""
    if os.path.exists(REJECTED_NEWS_FILE):
        with open(REJECTED_NEWS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def save_rejected_news(news_article):
    """Tallentaa hylätyn uutisen rejected_news.json -tiedostoon."""
    rejected_news = load_rejected_news()

    source = news_article.get("source", "Tuntematon lähde")
    title = news_article.get("title", "Ei otsikkoa")
    description = news_article.get("description", "Ei kuvausta")
    url = news_article.get("url", "Ei URL:ia")

    rejected_news_entry = {
        "source": source,
        "title": title,
        "description": description,
        "url": url
    }

    if source not in rejected_news:
        rejected_news[source] = []

    rejected_news[source].append(rejected_news_entry)

    with open(REJECTED_NEWS_FILE, "w", encoding="utf-8") as file:
        json.dump(rejected_news, file, indent=4, ensure_ascii=False)

    print(f"⚠️ DEBUG: Hylätty uutinen tallennettu {source}: {title}")


def load_etf_name_dict():
    """Lataa ETF-nimet JSON-tiedostosta."""
    with open("etf_name_dict.json", "r") as f:
        return json.load(f)

def fetch_etf_news(ticker, owned_etfs):
    """
    Hakee uutiset **ETF:lle** ja suodattaa ne hyväksytyistä lähteistä.
    
    - **Omistetut ETF:t haetaan `owned_etfs`**
    - **Mahdollistaa kattavamman analyysin ETF-uutisista**
    - **Suodattaa vain hyväksytyistä lähteistä tulevat uutiset**
    """
    if ticker not in owned_etfs:
        print(f"⚠️ {ticker}: Ei löydy omistetuista ETF:istä, ohitetaan uutishaku.")
        return [], [], []

    print(f"🔍 Aloitetaan ETF-uutishaku kohteelle {ticker}")

    fetched_etfs = load_json(LAST_NEWS_FETCH_FILE)

    if not can_fetch_news(ticker, "etf", fetched_etfs, owned_etfs):
        print(f"⚠️ {ticker}: Uutishaku EI SALLITTU tarkistuksen perusteella.")
        return [], [], []

    if not update_news_api_usage("owned_etf"):
        print(f"⚠️ {ticker}: Omistettujen ETF:ien hakuraja saavutettu! Ei tehdä uutta hakua.")
        return [], [], []
    
    print(f"✅ {ticker}: Uutishaku sallittu, jatketaan hakua...")

    usage_data = load_news_api_usage()
    total_calls_today = usage_data.get("calls_today", 0)
    owned_etfs_calls_today = usage_data.get("owned_etfs_calls_today", 0)
    today = datetime.date.today().isoformat()

    remaining_calls = TOTAL_API_LIMIT - total_calls_today
    remaining_owned_etfs_calls = OWNED_ETFS_CALLS_LIMIT - owned_etfs_calls_today

    if total_calls_today >= NEWS_API_CALLS_LIMIT:
        print(f"⚠️ {ticker}: Päivittäinen uutishakujen raja ({NEWS_API_CALLS_LIMIT}) saavutettu, ei haeta.")
        return [], [], []

    if owned_etfs_calls_today >= OWNED_ETFS_CALLS_LIMIT:
        print(f"🔍 {ticker}: Omistettujen ETF:ien limiitti täynnä! Ei haeta uutisia.")
        return [], [], []

    print(f"🔍 {ticker}: Haetaan uutisia... (Jäljellä olevat kutsut: {remaining_calls}, Omistetuille: {remaining_owned_etfs_calls})")

    fetched_etfs[ticker] = today
    save_json(LAST_NEWS_FETCH_FILE, fetched_etfs)

    etf_name_dict = load_etf_name_dict()
    etf_name = etf_name_dict.get(ticker, ticker)  # Käytetään täyttä nimeä, jos saatavilla

    search_terms = f"\"{etf_name}\" OR {ticker}"
    params = {
        "q": search_terms,
        "apiKey": NEWS_API_KEY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 10
    }

    time.sleep(2)  # ✅ Estetään liian nopeat pyynnöt
    try:
        response = requests.get(NEWSAPI_URL, params=params, timeout=10)

        if response.status_code == 429:
            print(f"⚠️ DEBUG: Liian monta pyyntöä NewsAPI:lle, odotetaan ja yritetään uudelleen.")
            time.sleep(60)
            response = requests.get(NEWSAPI_URL, params=params, timeout=10)

        if response.status_code != 200:
            logging.error(f"❌ ERROR: Virhe uutishakuun kohteelle {ticker}: {response.status_code} - {response.text}")
            return [], [], []

        try:
            news_data = response.json()
        except ValueError:
            logging.error(f"❌ ERROR: NewsAPI palautti virheellisen JSON-datan kohteelle {ticker}.")
            return [], [], []

        articles = news_data.get("articles", [])
        if not isinstance(articles, list):
            print(f"⚠️ ERROR: `articles` ei ole lista, vaan {type(articles)} - {articles}")
            return [], [], []

        filtered_news = []
        for article in articles:
            if not isinstance(article, dict):
                continue

            title = article.get("title", "")
            description = article.get("description", "")
            source = article.get("source", {}).get("name", "Tuntematon lähde")

            if not title:
                print(f"⚠️ DEBUG: Uutisartikkelilta puuttuu otsikko: {article}")
                continue

            if not description:
                print(f"⚠️ DEBUG: Uutisartikkelilta puuttuu kuvaus: {article}")
                continue

            title = title.lower()
            description = description.lower()

            if not isinstance(source, str):
                source = "Tuntematon lähde"

            source = source.lower()

            if source not in ETF_NEWS_SOURCES:
                print(f"⚠️ Ohitetaan uutinen {title} ({source}) - Ei hyväksytyllä lähdelistalla")
                continue

            if ticker.lower() not in title and ticker.lower() not in description and etf_name.lower() not in title and etf_name.lower() not in description:
                print(f"⚠️ Ohitetaan uutinen - Ei mainintaa: {title}")
                save_rejected_news(article)  # 🔴 Tallennetaan hylätty uutinen
                continue

            filtered_news.append({
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "url": article.get("url", ""),
                "source": source,
            })

        negative_news, critical_news = analyze_etf_news_sentiment(filtered_news)

        print(f"✅ Haettu {len(filtered_news)} uutista ETF:lle {ticker}.")
        return filtered_news, negative_news, critical_news

    except requests.exceptions.RequestException as e:
        logging.error(f"⚠️ ERROR: HTTP-virhe kohteelle {ticker}: {e}")

    return [], [], []


def analyze_etf_news_sentiment(news_articles):
    """Analysoi ETF-uutisten sentimentin ja palauttaa kriittiset ja negatiiviset uutiset erikseen."""
    critical_news = []
    negative_news = []

    if not isinstance(news_articles, list):
        print(f"⚠️ ERROR: ETF-uutislista ei ole lista: {type(news_articles)} - {news_articles}")
        return [], []  

    for article in news_articles:
        if not isinstance(article, dict):
            print(f"⚠️ ERROR: ETF-uutisartikkeli ei ole dict: {type(article)} - {article}")
            continue

        title = article.get("title", "").lower()
        description = article.get("description", "").lower()

        source = article.get("source", {})

        if isinstance(source, dict):
            source_name = source.get("name", "Tuntematon lähde")
        elif isinstance(source, str):  
            source_name = source  
        else:
            print(f"⚠️ ERROR: `source` tuntematon tietotyyppi: {type(source)} - {source}")
            source_name = "Tuntematon lähde"

        source_name = source_name.lower() if isinstance(source_name, str) else "tuntematon lähde"

        if any(word in title or word in description for word in CRITICAL_KEYWORDS_ETF):
            critical_news.append(f"{title} ({source_name})")  

        elif any(word in title or word in description for word in NEGATIVE_KEYWORDS_ETF):
            negative_news.append(f"{title} ({source_name})")  

    return negative_news, critical_news

SECTOR_CACHE_FILE = "sector_cache.json"

def load_sector_cache():
    """🔍 Lataa sektoritiedot sektor_cache.json-tiedostosta."""
    if os.path.exists(SECTOR_CACHE_FILE):
        with open(SECTOR_CACHE_FILE, "r") as file:
            return json.load(file)
    return {}

def save_sector_cache():
    """🔹 Tallentaa sektoritiedot sektor_cache.json-tiedostoon."""
    with open(SECTOR_CACHE_FILE, "w") as file:
        json.dump(sector_cache, file)

sector_cache = load_sector_cache()  # 🔹 Alustetaan välimuisti

def get_all_sectors(assets):
    """🔍 Hakee sektoritiedot kaikille osakkeille ja tallentaa ne välimuistiin."""
    print(f"📊 Haetaan sektoritiedot kaikille {len(assets)} osakkeille.")

    stocks = {asset: yf.Ticker(asset) for asset in assets}

    for asset, stock in stocks.items():
        try:
            if asset in sector_cache:
                continue  # 🔹 Käytetään välimuistia, jos tieto löytyy
            
            if isinstance(stock.info, list):
                print(f"❌ ERROR: stock.info on lista osakkeelle {asset}, mutta pitäisi olla sanakirja! Sisältö: {stock.info}")
                continue  # Hypätään tämän osakkeen yli virheen välttämiseksi

            sector = stock.info.get("sector", "Tuntematon")
            sector_cache[asset] = sector  # 🔹 Tallennetaan välimuistiin
            time.sleep(0.3)  # 🔄 Pienempi viive
        except Exception as e:
            print(f"⚠️ Virhe sektoritietojen haussa osakkeelle {asset}: {e}")

    save_sector_cache()  # 🔹 Tallennetaan sektorit välimuistiin

def get_sector(asset):
    """🔍 Palauttaa osakkeen sektorin välimuistista (JSON)."""
    
    sector = sector_cache.get(asset, "Tuntematon")  # Haetaan sektori välimuistista

    
    if isinstance(sector, list):
        print(f"❌ ERROR: Sektoritieto {sector} osakkeelle {asset} on lista, mutta pitäisi olla merkkijono!")
        return "Tuntematon"

    return sector

sector_pe_cache = {}
sector_pb_cache = {}

def get_sector_averages(sector):
    """🔎 Laskee annetun sektorin keskimääräisen PE- ja PB-luvun ja tallentaa ne välimuistiin."""
    
    if not isinstance(sector, str) or not sector:
        print(f"❌ ERROR: get_sector_averages() sai virheellisen sektorin: {sector} (tyyppi: {type(sector)})")
        return None, None

    if sector in sector_pe_cache and sector in sector_pb_cache:
        print(f"⚡ Sektorin {sector} keskiarvot löytyivät välimuistista.")
        return sector_pe_cache[sector], sector_pb_cache[sector]

    pe_values = []
    pb_values = []

    sector_assets = [asset for asset, sec in sector_cache.items() if sec == sector]

    if not sector_assets:
        print(f"⚠️ Ei osakkeita sektorille {sector}, ei voida laskea keskiarvoja.")
        return None, None

    print(f"📊 Sektori {sector} sisältää {len(sector_assets)} osaketta.")

    stocks = {asset: yf.Ticker(asset) for asset in sector_assets}

    for i, (asset, stock) in enumerate(stocks.items()):
        try:
            stock_info = stock.info  # 🔥 Haetaan kerralla

            a1 = stock_info.get("trailingPE")
            if isinstance(a1, (int, float)) and 0 < a1 < 100:
                pe_values.append(a1)
            
            a2 = stock_info.get("priceToBook")
            if isinstance(a2, (int, float)) and 0 < a2 < 50:
                pb_values.append(a2)

            if len(sector_assets) > 20 and i % 10 == 0:
                print(f"⏳ Asetetaan viive, jotta Yahoo Finance ei rajoita pyyntöjä...")
                time.sleep(0.5)  # Pieni tauko 10 osakkeen välein

        except Exception as e:
            print(f"⚠️ Virhe sektoritietojen hakemisessa osakkeelle {asset}: {e}")

    sector_avg_pe = (
        sum(pe_values) / len(pe_values) if len(pe_values) >= 5 else median(pe_values) if pe_values else None
    )
    sector_avg_pb = (
        sum(pb_values) / len(pb_values) if len(pb_values) >= 5 else median(pb_values) if pb_values else None
    )

    print(f"📊 Sektori {sector} - PE-keskiarvo: {sector_avg_pe}, PB-keskiarvo: {sector_avg_pb}")

    sector_pe_cache[sector] = sector_avg_pe
    sector_pb_cache[sector] = sector_avg_pb

    return sector_avg_pe, sector_avg_pb

sema = asyncio.Semaphore(5)  # Sallitaan enintään 5 samanaikaista pyyntöä

async def fetch_all_stocks():
    """Hakee kaikkien osakkeiden tiedot asynkronisesti ja palauttaa ne sanakirjana."""
    all_assets = set(ASSETS)
    results = {}
    failed_assets = load_json(FAILED_ASSETS_FILE)

    async def limited_stock_fetch(asset):
        async with sema:
            return await get_data_block_async(asset)

    tasks = {
        asset: asyncio.wait_for(limited_stock_fetch(asset), timeout=60)
        for asset in all_assets
    }

    for asset, task in tasks.items():
        try:
            asset, data = await task

            if isinstance(data, list):
                print(f"❌ ERROR: {asset} palautti listan, mutta odotettiin sanakirjaa! Sisältö: {data}")
                continue

            if data:
                results[asset] = data
                if asset in failed_assets:
                    print(f"ℹ️ DEBUG: {asset} palautettu aktiiviseksi.")
                    failed_assets.pop(asset)  # Poistetaan aiemmat virheet
            else:
                failed_assets[asset] = failed_assets.get(asset, 0) + 1
                print(f"⚠️ {asset} ei palauttanut dataa. Yritys {failed_assets[asset]}/3.")

        except asyncio.TimeoutError:
            failed_assets[asset] = failed_assets.get(asset, 0) + 1
            print(f"⏳ TIMEOUT: {asset} - Osakkeen haku kesti liian kauan! Yritys {failed_assets[asset]}/3.")

        if failed_assets.get(asset, 0) >= 3:
            print(f"🚨 VAROITUS: {asset} epäonnistui 3 kertaa peräkkäin, mutta EI poisteta seurannasta.")

    save_json(FAILED_ASSETS_FILE, failed_assets)
    return results

async def get_data_block_async(asset, is_etf=False, retries=3):
    """Hakee osakkeen tai ETF:n tiedot asynkronisesti Yahoo Financesta aiohttp:n avulla."""
    async with sema:
        for attempt in range(retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    start_time = time.time()
                    hist = await asyncio.wait_for(
                        asyncio.to_thread(yf.Ticker(asset).history, period="7d", interval="1h"),
                        timeout=35
                    )
                    elapsed_time = time.time() - start_time
                    print(f"✅ {asset}: Haku valmis ({elapsed_time:.2f} s)")

                    if hist.empty:
                        print(f"⚠️ {asset}: Ei saatavilla olevaa dataa.")
                        return asset, None  

                    asset_data = hist.reset_index().to_dict('records')
                    if isinstance(asset_data, list) and asset_data:
                        asset_data = asset_data[-1]  

                    if not isinstance(asset_data, dict):
                        print(f"❌ ERROR: {asset} palautti listan, mutta odotettiin sanakirjaa! Sisältö: {asset_data}")
                        return asset, None  

                    asset_data["ticker"] = asset  

                    return asset, asset_data

            except asyncio.TimeoutError:
                elapsed_time = time.time() - start_time
                print(f"⏳ TIMEOUT: {asset} - Yahoo Finance ei vastannut ajoissa! Yritys {attempt + 1}/{retries} (Aikaa kului: {elapsed_time:.2f} s)")
                if attempt == retries - 1:
                    return asset, None  

            except asyncio.CancelledError:
                print(f"🛑 {asset}: Haku peruutettu.")
                return asset, None  

            except Exception as e:
                print(f"⚠️ Virhe osakkeen {asset} haussa: {e}")
                return asset, None

            await asyncio.sleep(min(10, 2 * (attempt + 1)))  # 🔄 Kasvava viive, max 10s

async def get_data_block():
    """Hakee osaketiedot asynkronisesti ja käsittelee virhetilanteet."""
    data = {}
    error_messages = []  # 🔹 Lisätty takaisin virheilmoitusten keräämistä varten
    failed_assets = load_json(FAILED_ASSETS_FILE)
    removed_assets = load_json(REMOVED_ASSETS_FILE)

    print("🔎 Aloitetaan markkinadatan haku...")
    start_time = time.time()

    if not isinstance(removed_assets, list):
        print("⚠️ DEBUG: REMOVED_ASSETS_FILE sisälsi virheellistä dataa, alustetaan tyhjäksi listaksi.")
        removed_assets = []

    new_data = await fetch_all_stocks()  

    elapsed_time = time.time() - start_time
    print(f"✅ DEBUG: Markkinadatan haku valmis. Kesto: {elapsed_time:.2f} sekuntia.\n")

    for asset, hist in new_data.items():
        retry_count = failed_assets.get(asset, 0)

        if isinstance(hist, list) and hist and not isinstance(hist[0], dict):
            error_message = f"❌ ERROR: {asset} palautti listan, mutta odotettiin sanakirjaa! Sisältö: {hist}"
            print(error_message)
            error_messages.append(error_message)  # 🔹 Lisätään virheilmoitus listaan
            continue  

        if not hist:
            error_message = f"⚠️ DEBUG: {asset}: Ei saatavilla olevaa dataa."
            print(error_message)
            error_messages.append(error_message)  # 🔹 Lisätään virheilmoitus listaan
            failed_assets[asset] = retry_count + 1
            if failed_assets[asset] >= 3:
                removal_message = f"❌ DEBUG: {asset} poistetaan seurannasta (3 epäonnistunutta hakua)."
                print(removal_message)
                error_messages.append(removal_message)
                removed_assets.append(asset)
                failed_assets.pop(asset, None)
        else:
            if asset in failed_assets:
                print(f"ℹ️ DEBUG: {asset} palautettu aktiiviseksi.")
                failed_assets.pop(asset)
            data[asset] = hist

    save_json(FAILED_ASSETS_FILE, failed_assets)
    save_json(REMOVED_ASSETS_FILE, removed_assets)

    return data, error_messages  # 🔹 Palautetaan virheilmoitukset

FAILED_ETF_FILE = "failed_etf_queries.json"
DELISTED_ETF_FILE = "delisted_etfs.txt"

def track_failed_etf_queries(ticker, success=False):
    """Seuraa epäonnistuneita ETF-hakuja ja poistaa ne listalta, jos haku onnistuu."""
    
    today = datetime.date.today().isoformat()
    
    if os.path.exists(FAILED_ETF_FILE):
        with open(FAILED_ETF_FILE, "r") as f:
            try:
                failed_etfs = json.load(f)
            except json.JSONDecodeError:
                failed_etfs = {}
    else:
        failed_etfs = {}

    if success:
        if ticker in failed_etfs:
            print(f"✅ ETF {ticker} löytyi uudelleen – poistetaan epäonnistuneiden listalta.")
            del failed_etfs[ticker]
            with open(FAILED_ETF_FILE, "w") as f:
                json.dump(failed_etfs, f, indent=4)
        return  # Ei tehdä mitään muuta, koska ETF löytyi

    if ticker in failed_etfs:
        failed_etfs[ticker]["failures"] += 1
        failed_etfs[ticker]["last_failed"] = today
    else:
        failed_etfs[ticker] = {"failures": 1, "first_failed": today, "last_failed": today}

    first_failed_date = datetime.date.fromisoformat(failed_etfs[ticker]["first_failed"])
    days_since_first_fail = (datetime.date.today() - first_failed_date).days

    if days_since_first_fail >= 7:
        with open(DELISTED_ETF_FILE, "a") as f:
            f.write(ticker + "\n")

        del failed_etfs[ticker]

        message = f"🚨 ETF {ticker} haku epäonnistunut viikon ajan. Poistettu haettavista."
        asyncio.create_task(send_telegram_message(message))  # Käynnistetään async-tehtävä

    with open(FAILED_ETF_FILE, "w") as f:
        json.dump(failed_etfs, f, indent=4)

sema = asyncio.Semaphore(5)  # 🔹 Rajoitetaan samanaikaisia hakuja (max 5 kerrallaan)

async def fetch_etf_data_async(ticker, retries=3):
    """Hakee yksittäisen ETF:n tiedot asynkronisesti ja yrittää useita kertoja, jos epäonnistuu."""
    async with sema:
        for attempt in range(retries):
            try:
                timeout = aiohttp.ClientTimeout(total=30)  # 🔥 30s aikakatkaisu
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    stock = yf.Ticker(ticker)
                    hist = await asyncio.to_thread(stock.history, period="5d", interval="1d")

                    if hist.empty:
                        print(f"⚠️ {ticker}: Ei saatavilla olevaa dataa (yritys {attempt + 1}/{retries})")
                        await asyncio.sleep(2 * (attempt + 1))  # 🔄 Kasvava viive uusintayritysten välillä
                        continue

                    track_failed_etf_queries(ticker, success=True)

                    data = hist.reset_index()
                    data["Date"] = data["Date"].astype(str)

                    latest_data = data.iloc[-1].to_dict()
                    return {
                        "ticker": ticker,
                        "Date": latest_data["Date"],
                        "Open": latest_data["Open"],
                        "High": latest_data["High"],
                        "Low": latest_data["Low"],
                        "Close": latest_data["Close"],
                        "Volume": latest_data["Volume"],
                        "Dividends": latest_data.get("Dividends", 0.0),
                        "Stock Splits": latest_data.get("Stock Splits", 0.0),
                        "Capital Gains": latest_data.get("Capital Gains", 0.0)
                    }

            except asyncio.TimeoutError:
                print(f"⏳ TIMEOUT: {ticker} - Yahoo Finance ei vastannut ajoissa! Yritys {attempt + 1}/{retries}")
                await asyncio.sleep(2 * (attempt + 1))  # 🔄 Kasvava viive uusintayritysten välillä

            except Exception as e:
                print(f"⚠️ ERROR: {ticker} - Virhe haussa: {e}")
                await asyncio.sleep(2 * (attempt + 1))  # 🔄 Kasvava viive uusintayritysten välillä

        print(f"❌ ERROR: {ticker} - Ei onnistunut {retries} yrityksen jälkeen.")
        track_failed_etf_queries(ticker)  # 🔴 Merkitään epäonnistuneeksi
        return None

async def fetch_latest_etf_data():
    """Hakee uusimmat ETF-tiedot asynkronisesti ja tallentaa ne."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    etf_tickers = load_assets_from_file("etf_tickers.txt")
    fetched_data = {}
    error_messages = []

    delisted_etfs = set()
    if os.path.exists(DELISTED_ETF_FILE):
        with open(DELISTED_ETF_FILE, "r") as f:
            delisted_etfs = {line.strip() for line in f.readlines()}

    valid_tickers = [ticker for ticker in etf_tickers if ticker not in delisted_etfs]

    print(f"🔎 DEBUG: Haetaan tiedot {len(valid_tickers)} ETF:lle...")

    tasks = {
        ticker: asyncio.wait_for(fetch_etf_data_async(ticker), timeout=60)
        for ticker in valid_tickers
    }

    for ticker, task in tasks.items():
        print(f"🔍 Haetaan ETF: {ticker}")
        try:
            result = await task
            if result:
                fetched_data[ticker] = result

                cursor.execute('''
                    INSERT OR IGNORE INTO etf_prices 
                    (ticker, date, open_price, high_price, low_price, close_price, volume, dividends, stock_splits, capital_gains)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result["ticker"], result["Date"], result["Open"], result["High"], result["Low"],
                    result["Close"], result["Volume"], result["Dividends"], result["Stock Splits"], result["Capital Gains"]
                ))
            else:
                error_messages.append(f"⚠️ {ticker}: Haku epäonnistui.")
        except asyncio.TimeoutError:
            print(f"⏳ TIMEOUT: {ticker} - koko haulle asetettu 60s aikakatkaisu ylittyi.")
            error_messages.append(f"⏳ {ticker}: Aikakatkaisu.")
        except Exception as e:
            print(f"⚠️ ERROR: {ticker} - Virhe haussa: {e}")
            error_messages.append(f"⚠️ {ticker}: {e}")

    conn.commit()
    conn.close()

    print(f"✅ Uusimmat ETF-tiedot haettu ja tallennettu ({len(fetched_data)} onnistunutta hakua).")
    return fetched_data, error_messages

def compare_etf_with_previous_data(ticker):
    """Vertailee ETF:n nykyisiä arvoja edellisiin merkintöihin ja analysoi trendiä."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date, close_price FROM etf_prices 
        WHERE ticker = ? ORDER BY date DESC LIMIT 10
    ''', (ticker,))
    
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        print(f"⚠️ {ticker}: Ei tarpeeksi historiallista dataa vertailuun.")
        return None, None, None

    latest_price = rows[0][1]
    previous_price = rows[1][1]

    price_dropped = latest_price < previous_price
    below_5d_avg = latest_price < sum(row[1] for row in rows[:5]) / 5
    below_10d_avg = latest_price < sum(row[1] for row in rows[:10]) / 10

    return price_dropped, below_5d_avg, below_10d_avg

def get_moving_average_etf(ticker, period=200):
    """Laskee ETF:n liukuvan keskiarvon SQLiten tiedoista. Täydentää Yahoo Financesta tarvittaessa."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM etf_prices
        WHERE ticker = ? ORDER BY date DESC LIMIT ?
    ''', (ticker, period))
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]

    if len(close_prices) < period:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{period + 20}d")  # Haetaan hieman enemmän dataa
        close_prices = hist["Close"].tolist()

    if len(close_prices) < period:
        print(f"❌ ERROR: {ticker} - Ei tarpeeksi dataa {period} päivän keskiarvon laskentaan.")
        return None

    moving_avg = sum(close_prices[:period]) / period  # Lasketaan keskiarvo
    print(f"📊 {ticker} - {period} päivän liukuva keskiarvo: {moving_avg:.2f}")

    return moving_avg

def get_macd_etf(ticker):
    """Laskee ETF:n MACD-indikaattorin, signaalilinjan ja histogrammin käyttäen SQLite-tietoja."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM etf_prices
        WHERE ticker = ? ORDER BY date DESC LIMIT 26
    ''', (ticker,))
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]

    if len(close_prices) < 26:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")  # Haetaan tarpeeksi dataa MACD-laskentaan
        close_prices = hist["Close"].tolist()

    if len(close_prices) < 26:
        print(f"❌ ERROR: {ticker} - Ei tarpeeksi dataa MACD-laskentaan.")
        return None, None, None

    df = pd.DataFrame({'Close': close_prices[::-1]})  # Käännetään oikeaan järjestykseen
    df["EMA12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["Histogram"] = df["MACD"] - df["Signal"]

    print(f"📊 {ticker} - MACD: {df['MACD'].iloc[-1]:.4f}, Signaalilinja: {df['Signal'].iloc[-1]:.4f}, Histogrammi: {df['Histogram'].iloc[-1]:.4f}")

    return df["MACD"].iloc[-1], df["Signal"].iloc[-1], df["Histogram"].iloc[-1]

def get_rsi_etf(ticker, period=14):
    """Laskee ETF:n RSI:n käyttäen SQLite-tietokannan tietoja."""
    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM etf_prices
        WHERE ticker = ? ORDER BY date DESC LIMIT ?
    ''', (ticker, period + 1))  # Haetaan yksi ylimääräinen päivä delta-laskentaa varten
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]

    if len(close_prices) < period:
        print(f"❗ {ticker} - Ei tarpeeksi dataa RSI-laskentaan ({len(close_prices)} datapistettä).")
        return None  # Ei tarpeeksi dataa laskentaan

    df = pd.DataFrame({'Close': close_prices[::-1]})  # Käännetään vanhimmasta uusimpaan
    df["delta"] = df["Close"].diff()

    df["gain"] = df["delta"].apply(lambda x: x if x > 0 else 0)
    df["loss"] = df["delta"].apply(lambda x: -x if x < 0 else 0)

    avg_gain = df["gain"].rolling(window=period, min_periods=1).mean()
    avg_loss = df["loss"].rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    print(f"✅ {ticker} - RSI laskettu: {df['RSI'].iloc[-1]:.2f}")

    return round(df["RSI"].iloc[-1], 2)

def get_rsi(asset, period=14):
    """Laskee RSI:n käyttäen SQLite-tietokannan tietoja."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM x1
        WHERE ticker = ? ORDER BY datetime DESC LIMIT ?
    ''', (asset, period + 1))  # Haetaan yksi ylimääräinen päivä delta-laskentaa varten
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]
    
    if len(close_prices) < period:
        return None  # Ei tarpeeksi dataa laskentaan

    df = pd.DataFrame({'Close': close_prices[::-1]})  # Käännetään vanhimmasta uusimpaan
    df["delta"] = df["Close"].diff()

    df["gain"] = df["delta"].apply(lambda x: x if x > 0 else 0)
    df["loss"] = df["delta"].apply(lambda x: -x if x < 0 else 0)

    avg_gain = df["gain"].rolling(window=period, min_periods=1).mean()
    avg_loss = df["loss"].rolling(window=period, min_periods=1).mean()

    rs = avg_gain / avg_loss
    df["RSI"] = 100 - (100 / (1 + rs))

    print(f"✅ {asset} - RSI laskettu: {df['RSI'].iloc[-1]:.2f}")

    return round(df["RSI"].iloc[-1], 2)

def get_macd(asset):
    """Laskee MACD-indikaattorin, signaalilinjan ja histogrammin käyttäen SQLite-tietoja."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM x1
        WHERE ticker = ? ORDER BY datetime DESC LIMIT 26
    ''', (asset,))
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]

    if len(close_prices) < 26:
        stock = yf.Ticker(asset)
        hist = stock.history(period="60d")  # Haetaan tarpeeksi dataa MACD-laskentaan
        close_prices = hist["Close"].tolist()

    if len(close_prices) < 26:
        print(f"❌ ERROR: {asset} - Ei tarpeeksi dataa MACD-laskentaan.")
        return None, None, None

    df = pd.DataFrame({'Close': close_prices[::-1]})  # Käännetään oikeaan järjestykseen
    df["EMA12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA26"] = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = df["EMA12"] - df["EMA26"]
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["Histogram"] = df["MACD"] - df["Signal"]

    print(f"📊 {asset} - MACD: {df['MACD'].iloc[-1]:.4f}, Signaalilinja: {df['Signal'].iloc[-1]:.4f}, Histogrammi: {df['Histogram'].iloc[-1]:.4f}")

    return df["MACD"].iloc[-1], df["Signal"].iloc[-1], df["Histogram"].iloc[-1]

def get_moving_average(asset, period=200):
    """Laskee osakkeen liukuvan keskiarvon SQLiten tiedoista. Täydentää Yahoo Financesta tarvittaessa."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM x1
        WHERE ticker = ? ORDER BY datetime DESC LIMIT ?
    ''', (asset, period))
    rows = cursor.fetchall()
    conn.close()

    close_prices = [row[0] for row in rows]

    if len(close_prices) < period:
        stock = yf.Ticker(asset)
        hist = stock.history(period=f"{period + 20}d")  # Haetaan vähän ylimääräistä
        close_prices = hist["Close"].tolist()

    if len(close_prices) < period:
        print(f"❌ ERROR: {asset} - Ei tarpeeksi dataa {period} päivän keskiarvon laskentaan.")
        return None

    moving_avg = sum(close_prices[:period]) / period  # Lasketaan keskiarvo
    print(f"📊 {asset} - {period} päivän liukuva keskiarvo: {moving_avg:.2f}")

    return moving_avg

def get_fundamentals(ticker):
    """Hakee osakkeen keskeiset fundamenttiarvot Yahoo Financesta turvallisesti."""
    try:
        if not isinstance(ticker, str):
            print(f"⚠️ ERROR: get_fundamentals() sai väärän datatyypin ({type(ticker)}) ticker: {ticker}")
            return None, None, None, None

        stock = yf.Ticker(ticker)
        info = stock.info  

        if not isinstance(info, dict):
            print(f"⚠️ ERROR: stock.info ei ole dict, vaan {type(info)} - {info}")
            return None, None, None, None

        if not info:
            print(f"⚠️ WARNING: stock.info palautti tyhjän dictin osakkeelle {ticker}")
            return None, None, None, None

        a1 = info.get("trailingPE")
        a2 = info.get("priceToBook")
        earnings_growth = info.get("earningsGrowth")
        debt_to_equity = info.get("debtToEquity")

        if not isinstance(a1, (int, float)) or a1 <= 0 or a1 > 100:
            a1 = None  

        if not isinstance(a2, (int, float)) or a2 <= 0 or a2 > 50:
            a2 = None  

        if not isinstance(earnings_growth, (int, float)):
            earnings_growth = None  

        if not isinstance(debt_to_equity, (int, float)) or debt_to_equity < 0:
            debt_to_equity = 50  


        return a1, a2, earnings_growth, debt_to_equity

    except Exception as e:
        print(f"⚠️ ERROR: Virhe fundamenttiarvojen haussa osakkeelle {ticker}: {e}")
        return None, None, None, None

def generate_etf_buy_decision(ticker, etf_data, historical_prices):
    """Analysoi ETF:n ostomahdollisuudet pisteytysjärjestelmällä."""
    print(f"🔵🔍 Aloitetaan ETF-ostosuositusanalyysi {ticker}")

    conn = sqlite3.connect(ETF_DB)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price, volume FROM etf_prices
        WHERE ticker = ? ORDER BY date DESC LIMIT 1
    ''', (ticker,))
    result = cursor.fetchone()
    
    if result:
        current_price, today_volume = result
        print(f"✅ Haettu SQLitestä ETF:lle {ticker} - Hinta: {current_price}, Volyymi: {today_volume}")
    else:
        print(f"⚠️ DEBUG: Ei löydetty tietoja ETF:lle {ticker} SQLitestä.")
        conn.close()
        return ticker, None, 0  
    
    cursor.execute('''
        SELECT AVG(volume) FROM etf_prices
        WHERE ticker = ? AND date >= date('now', '-30 days')
    ''', (ticker,))
    avg_volume_30d = cursor.fetchone()[0] or 0  

    conn.close()

    try:
        price_dropped, below_10d_avg, below_5d_avg = compare_etf_with_previous_data(ticker)
    except Exception as e:
        print(f"⚠️ DEBUG: Virhe compare_etf_with_previous_data:ssa ETF:lle {ticker}: {e}")
        price_dropped, below_10d_avg, below_5d_avg = False, False, False  # **Oletusarvot**

    rsi = get_rsi_etf(ticker)
    if rsi is None:
        print(f"❗ {ticker} - RSI on None, asetetaan arvoon 50.")
        rsi = 50

    macd, signal_line, histogram = get_macd_etf(ticker)
    if macd is None or signal_line is None or histogram is None:
        print(f"❗ {ticker} - MACD-arvoja ei voitu laskea, asetetaan neutraalit arvot.")
        macd, signal_line, histogram = 0, 0, 0  

    sma_50 = get_moving_average_etf(ticker, period=50)
    sma_200 = get_moving_average_etf(ticker, period=200)

    if sma_50 is None:
        print(f"❗ {ticker} - SMA-50 ei saatavilla, käytetään viimeisintä päätöskurssia ({current_price:.2f}).")
        sma_50 = current_price  

    if sma_200 is None:
        print(f"❗ {ticker} - SMA-200 ei saatavilla, käytetään viimeisintä päätöskurssia ({current_price:.2f}).")
        sma_200 = current_price  

    score = 0
    decisions = []

    if rsi < 20:
        score += 5  # Pidetään korkea arvo, koska RSI < 20 on vahva signaali
        decisions.append(f"🔥 RSI on erittäin alhainen ({rsi:.2f}) - mahdollinen vahva ostosignaali.")
    elif rsi < 25:
        score += 4
        decisions.append(f"🔥 RSI on erittäin matala ({rsi:.2f}) - ETF voi olla aliarvostettu.")
    elif rsi < 30:
        score += 3
        decisions.append(f"🔥 RSI on matala ({rsi:.2f}) - mahdollinen ostopaikka.")
    elif rsi < 40:
        score += 2
        decisions.append(f"🔥 RSI on hieman matala ({rsi:.2f}) - ETF voi olla edullinen.")
    elif rsi > 70:
        score -= 5
        decisions.append(f"⚠️ RSI on korkea ({rsi:.2f}) - ETF voi olla yliostettu.")

    if histogram > 0.5:
        score += 5  # Lasketaan max pistearvo yhdellä
        decisions.append("🚀🚀 MACD-histogrammi kasvaa merkittävästi – erittäin vahva nousutrendi.")
    elif histogram > 0:
        score += 3
        decisions.append("🚀 MACD-histogrammi on positiivinen – nousutrendi ennusteessa.")
    elif histogram < -0.5:
        score -= 5
        decisions.append("⚠️ MACD-histogrammi laskee jyrkästi - mahdollinen laskutrendi.")

    if current_price > sma_200:
        score += 4  # Pidetään korkea, mutta ei +5
        decisions.append(f"📈 ETF:n hinta on yli SMA-200 ({current_price:.2f} > {sma_200:.2f}) - vahva nousutrendi.")
    elif current_price < sma_200:
        score -= 5
        decisions.append(f"⚠️ ETF:n hinta on alle SMA-200 ({current_price:.2f} < {sma_200:.2f}) - laskutrendi mahdollinen.")

    if current_price > sma_50:
        score += 2  # Alennetaan yhdellä
        decisions.append(f"📈 ETF:n hinta on yli SMA-50 ({current_price:.2f} > {sma_50:.2f}) - lyhyen aikavälin nousutrendi.")
    elif current_price < sma_50:
        score -= 3
        decisions.append(f"⚠️ ETF:n hinta on alle SMA-50 ({current_price:.2f} < {sma_50:.2f}) - lyhyen aikavälin laskutrendi.")

    if sma_50 > sma_200:
        score += 4  # Alennetaan yhdellä
        decisions.append(f"📈 Kultainen risti havaittu: SMA-50 ({sma_50:.2f}) yli SMA-200 ({sma_200:.2f}).")
    elif sma_50 < sma_200:
        score -= 4
        decisions.append(f"⚠️ Kuoleman risti havaittu: SMA-50 ({sma_50:.2f}) alle SMA-200 ({sma_200:.2f}).")

    if price_dropped:
        score += 2
        decisions.append("📉 ETF:n hinta on laskenut edellisestä päivästä.")
    if below_5d_avg:
        score += 3
        decisions.append("📊 ETF:n hinta on alle 5 päivän keskiarvon – mahdollinen ostotilaisuus.")
    if below_10d_avg:
        score += 5
        decisions.append("📊 ETF:n hinta on alle 10 päivän keskiarvon – vahva ostosignaali.")

    if avg_volume_30d and today_volume < avg_volume_30d * 0.2:
        print(f"⚠️ {ticker}: Volyymi ({today_volume}) on merkittävästi matalampi kuin 30p keskiarvo ({avg_volume_30d}) – vähennetään 3 pistettä.")
        score -= 3  

    print(f"✅ {ticker}: Lopullinen pistemäärä {score}")

    if score >= 22:  # Uusi kompromissitaso
        decisions.append(f"🌟 Vahva ostosuositus: {score} pistettä!")
    elif score >= 20:  # Pidetään kohtalaisen korkeana
        decisions.append(f"⭐ ETF voi olla hyvä ostokohde ({score} pistettä).")
    else:
        print(f"🟡 {ticker}: Ostosuosituksia ei löytynyt.")
        return ticker, None, score  # 🔹 Varmistetaan, että palautetaan selkeä arvo

    return ticker, decisions if decisions else None, score

def generate_etf_sell_decision(ticker, historical_prices, owned_etfs):
    """Analysoi ETF:n myyntimahdollisuudet pisteytysjärjestelmällä."""
    print(f"\n🔴🔍 Aloitetaan ETF-myyntianalyysi {ticker}")

    if ticker not in load_assets_from_file(OWNED_ETFS_FILE):
        print(f"⚠️ {ticker}: Ei omistettujen ETF:ien listalla, ei analysoida myyntiä.")
        return ticker, None, 0  

    if not historical_prices:
        print(f"⚠️ {ticker}: Ei saatavilla olevaa historiadataa.")
        return ticker, None, 0  

    conn_etf = sqlite3.connect(ETF_DB)
    cursor_etf = conn_etf.cursor()

    cursor_etf.execute('''
        SELECT close_price FROM etf_prices
        WHERE ticker = ? ORDER BY date DESC LIMIT 1
    ''', (ticker,))
    result = cursor_etf.fetchone()
    
    if result:
        current_price = result[0]
        print(f"✅ Haettu SQLitestä ETF:lle {ticker} - Hinta: {current_price}")
    else:
        print(f"⚠️ DEBUG: Ei löydetty päätöskurssia ETF:lle {ticker} SQLitestä.")
        conn_etf.close()
        return ticker, None, 0  

    conn_etf.close()  # ✅ Suljetaan yhteys ETF_DB:hen

    conn_assets = sqlite3.connect("owned_assets.db")
    cursor_assets = conn_assets.cursor()

    cursor_assets.execute('''
        SELECT purchase_price FROM owned_assets
        WHERE ticker = ? LIMIT 1
    ''', (ticker,))
    purchase_result = cursor_assets.fetchone()

    if purchase_result:
        purchase_price = purchase_result[0]
        print(f"✅ Haettu ostohinta ETF:lle {ticker} - Ostohinta: {purchase_price}")
        profit_percentage = ((current_price - purchase_price) / purchase_price) * 100
    else:
        print(f"⚠️ Ei löytynyt ostohintaa ETF:lle {ticker}.")
        profit_percentage = None    

    conn_assets.close()  # ✅ Suljetaan yhteys owned_assets.db:hen

    try:
        rsi = get_rsi_etf(ticker)
        if rsi is None:
            print(f"❗ {ticker} - RSI on None, asetetaan arvoon 50.")
            rsi = 50

        macd, signal_line, histogram = get_macd_etf(ticker)
        if macd is None or signal_line is None or histogram is None:
            print(f"❗ {ticker} - MACD-arvoja ei voitu laskea, asetetaan neutraalit arvot.")
            macd, signal_line, histogram = 0, 0, 0  

        sma_50 = get_moving_average_etf(ticker, period=50)
        sma_200 = get_moving_average_etf(ticker, period=200)

        if sma_50 is None or sma_200 is None:
            print(f"❗ {ticker} - SMA-arvoja ei saatavilla, ohitetaan niiden käyttö analyysissä.")
            sma_50, sma_200 = None, None

        print(f"📊 {ticker} - RSI: {rsi}, MACD: {macd}, Signaalilinja: {signal_line}, Histogrammi: {histogram}")
        print(f"📊 {ticker} - 50 päivän liukuva keskiarvo: {sma_50}, 200 päivän liukuva keskiarvo: {sma_200}")

    except Exception as e:
        print(f"⚠️ DEBUG: Virhe teknisten indikaattoreiden haussa ETF:lle {ticker}: {e}")
        return ticker, None, 0  

    try:
        price_dropped, below_5d_avg, below_10d_avg = compare_etf_with_previous_data(ticker)
    except Exception as e:
        print(f"⚠️ DEBUG: Virhe compare_etf_with_previous_data:ssa ETF:lle {ticker}: {e}")
        return ticker, None, 0  

    negative_news = []
    critical_news = []

    if ticker in owned_etfs:  # ✅ Tarkistetaan vain omistetut ETF:t
        news_articles, negative_news, critical_news = fetch_etf_news(ticker, owned_etfs)

        if not isinstance(news_articles, list):
            print(f"⚠️ ERROR: Uutislista ei ole lista: {type(news_articles)} - {news_articles}")
            news_articles = []

        if news_articles:
            analyzed_negative_news, analyzed_critical_news = analyze_etf_news_sentiment(news_articles)
            
            if isinstance(analyzed_negative_news, list) and isinstance(analyzed_critical_news, list):
                negative_news.extend(analyzed_negative_news)
                critical_news.extend(analyzed_critical_news)
            else:
                print(f"⚠️ ERROR: Uutisanalyysi palautti odottamattoman tyypin ETF:lle {ticker}: "
                    f"{type(analyzed_negative_news)}, {type(analyzed_critical_news)}")

    score = 0
    decisions = []

    if profit_percentage is not None:
        if profit_percentage > 25:
            if rsi > 70 or macd < signal_line:  # Varmistetaan, että myös RSI/MACD tukevat myyntiä
                score += 10
                decisions.append(f"💰💰💰 ETF:n tuotto on {profit_percentage:.2f} % - erittäin hyvä myyntipaikka.")
        elif profit_percentage > 20:  
            score += 5
            decisions.append(f"💰 ETF:n tuotto on {profit_percentage:.2f} % - hyvä myyntipaikka.")
        elif profit_percentage > 15:  
            score += 3
            decisions.append(f"📈 ETF on noussut {profit_percentage:.2f} % - mahdollinen myyntimahdollisuus.")
        elif profit_percentage < -10:  
            score += 5
            decisions.append(f"⚠️ ETF on laskenut {profit_percentage:.2f} % - harkitse tappioiden minimoimista.")

        elif profit_percentage > 10 and current_price < purchase_price * 1.10:
            score += 7
            decisions.append(f"⚠️ ETF oli noussut yli 20 %, mutta on nyt pudonnut takaisin +10 % tasolle – kannattaa harkita myyntiä.")

    if rsi > 80:
        score += 5
        decisions.append(f"🚨 RSI on erittäin korkea ({rsi:.2f}) – ETF saattaa olla yliostettu.")
    elif rsi > 70:
        score += 3
        decisions.append(f"📊 RSI on korkea ({rsi:.2f}) – mahdollinen myyntisignaali.")

    if macd < signal_line:
        score += 4
        decisions.append("⚠️ MACD on alle signaalilinjan – laskutrendi vahvistuu.")
    if histogram < -0.5:
        score += 5
        decisions.append("⚠️ MACD-histogrammi laskee jyrkästi - mahdollinen laskutrendi.")

    if current_price < sma_50:
        score += 3
        decisions.append("📉 ETF:n hinta on alle 50 päivän keskiarvon – mahdollinen lyhyen aikavälin laskutrendi.")
    if current_price < sma_200:
        score += 5
        decisions.append("⚠️ ETF:n hinta on alle 200 päivän keskiarvon – mahdollinen pitkäaikainen laskutrendi.")

    if sma_50 is not None and sma_200 is not None:
        if sma_50 < sma_200:
            score += 5
            decisions.append(f"⚠️ Kuoleman risti havaittu: SMA-50 ({sma_50:.2f}) alle SMA-200 ({sma_200:.2f}).")
        elif sma_50 > sma_200:
            score -= 5
            decisions.append(f"📈 Kultainen risti havaittu: SMA-50 ({sma_50:.2f}) yli SMA-200 ({sma_200:.2f}).")

    if current_price < historical_prices[-1]["Close"] * 0.95:
        score += 4
        decisions.append("📉 ETF:n hinta on laskenut yli 5 % yhden päivän aikana.")

    if current_price < historical_prices[-1]["Close"] * 0.90:
        score += 7
        decisions.append("🚨 Kriittinen hinnanlasku – ETF:n arvo on pudonnut yli 10 %.")

    if negative_news:
        score += 4
        decisions.append(f"⚠️ Negatiivisia uutisia löydetty ({', '.join(negative_news)}) – harkitse myyntiä.")

    if critical_news:
        score += 8
        decisions.append(f"🆘 Kriittinen uutinen löydetty ({', '.join(critical_news)})! Välitön myyntisuositus!")

    if negative_news and current_price < historical_prices[-1]["Close"] * 0.98:
        score += 2
        decisions.append(f"📉 Hinnanlasku negatiivisten uutisten jälkeen - vahvistaa myyntisuositusta!")

    if critical_news and current_price < historical_prices[-1]["Close"] * 0.95:
        score += 4
        decisions.append(f"🚨 Kriittinen uutinen + hinnanlasku -> myynti erittäin suositeltavaa!")

    print(f"✅ {ticker}: Myyntipistemäärä {score}")

    if score >= 18:
        decisions.append(f"🌟 Vahva myyntisuositus: {score} pistettä!")
        return ticker, decisions, score
    elif score >= 10:
        decisions.append(f"⭐ ETF voi olla hyvä myyntikohde ({score} pistettä).")
        return ticker, decisions, score
    else:
        return ticker, None, score

def generate_buy_decision(asset, new_data, historical_prices):
    """Analysoi osakkeen ostomahdollisuudet pisteytysjärjestelmällä, suosien pitkän aikavälin sijoituksia."""

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price, volume FROM x1
        WHERE ticker = ? ORDER BY datetime DESC LIMIT 1
    ''', (asset,))
    result = cursor.fetchone()
    
    if result:
        current_price, today_volume = result
    else:
        print(f"⚠️ DEBUG: Ei löydetty tietoja osakkeelle {asset} SQLitestä.")
        conn.close()
        return asset, None, 0  

    cursor.execute('''
        SELECT AVG(volume) FROM x1
        WHERE ticker = ? AND datetime >= date('now', '-30 days')
    ''', (asset,))
    avg_volume_30d = cursor.fetchone()[0] or 0  

    conn.close()

    try:
        moving_avg_50 = get_moving_average(asset, period=50)  
        moving_avg_200 = get_moving_average(asset, period=200)  
        rsi = get_rsi(asset)  
        macd, signal_line, histogram = get_macd(asset)  

        print(f"📊 {asset} - RSI: {rsi}, MACD: {macd}, Signaalilinja: {signal_line}, Histogrammi: {histogram}")
        print(f"📊 {asset} - 50 päivän liukuva keskiarvo: {moving_avg_50}, 200 päivän liukuva keskiarvo: {moving_avg_200}")

    except Exception as e:
        print(f"⚠️ DEBUG: Virhe teknisten indikaattoreiden haussa osakkeelle {asset}: {e}")
        return asset, None, 0  

    try:
        if not isinstance(asset, str):
            print(f"⚠️ ERROR: `asset` EI OLE merkkijono ennen fundamenttien hakua! Se on tyyppiä {type(asset)}")
            return asset, None, 0
            
        a1, a2, earnings_growth, debt_to_equity = get_fundamentals(asset)
        
        try:
            sector = get_sector(asset)
            print(f"✅ {asset} kuuluu sektoriin: {sector}")
        except Exception as e:
            print(f"⚠️ DEBUG: Virhe sektorin haussa osakkeelle {asset}: {e}")
            sector = "TUNTEMATON"

        sector_avg_pe, sector_avg_pb = get_sector_averages(sector)

        if not isinstance(sector_avg_pe, (int, float)) or sector_avg_pe <= 0:
            sector_avg_pe = 15  

        if not isinstance(sector_avg_pb, (int, float)) or sector_avg_pb <= 0:
            sector_avg_pb = 2  

        print(f"📊 {asset} - 30p volyymi-KA: {avg_volume_30d}, Sektori: {sector}, PE-keskiarvo: {sector_avg_pe}, PB-keskiarvo: {sector_avg_pb}")

    except Exception as e:
        asset_str = asset if 'asset' in locals() else 'TUNTEMATON'
        print(f"⚠️ DEBUG: Virhe MYYNTIANALYYSISSÄ fundamenttitietojen haussa osakkeelle {asset_str}: {e}")

    try:
        price_dropped, below_10d_avg, below_5d_avg = compare_with_previous_data(asset, new_data)
    except Exception as e:
        print(f"⚠️ DEBUG: Virhe compare_with_previous_data:ssa osakkeelle {asset}: {e}")
        return asset, None, 0  

    volume_penalty = 0  # Alustetaan volyymipisteiden vaikutus

    if avg_volume_30d is not None:
        if today_volume == 0:
            print(f"⚠️ {asset}: Volyymitieto näyttää 0 – tarkista osakkeen kaupankäynti ennen ostopäätöstä.")
        elif today_volume < avg_volume_30d * 0.2:
            print(f"⚠️ {asset}: Volyymi ({today_volume}) on merkittävästi matalampi kuin 30p keskiarvo ({avg_volume_30d}) – vähennetään 2 pistettä.")
            volume_penalty = -2  # 🔥 Vähennetään pisteitä huonosta volyymistä

    score = 0
    decisions = []

    if price_dropped:
        score += 1
        decisions.append("📉 Osakkeen hinta on laskenut viimeisimmästä sulkemishinnasta.")
    if below_5d_avg:
        score += 1
        decisions.append("📉 Osakkeen hinta on alle 5 päivän liukuvan keskiarvon – mahdollinen ostotilaisuus.")
    if below_10d_avg:
        score += 2
        decisions.append("📉 Osakkeen hinta on alle 10 päivän liukuvan keskiarvon – vahva ostosignaali.")

    if rsi is not None:
        if rsi < 40:
            score += 2
            decisions.append(f"🔥 RSI alhainen ({rsi:.2f}) - osake voi olla aliarvostettu.")
        if rsi < 30:
            score += 3
            decisions.append(f"🔥 RSI erittäin alhainen ({rsi:.2f}) - mahdollinen erittäin vahva ostosignaali.")

    if histogram > 0:
        score += 2
        decisions.append("🚀 MACD-histogrammi on positiivinen – nousutrendi ennusteessa.")
    if histogram > 0.5:
        score += 3
        decisions.append("🚀🚀 MACD-histogrammi kasvaa merkittävästi – erittäin vahva nousutrendi.")

    if moving_avg_50 and current_price < moving_avg_50:
        score += 2
        decisions.append(f"📊 Osakkeen hinta on alle 50 päivän liukuvan keskiarvon ({moving_avg_50:.2f}).")

    if moving_avg_200 and current_price < moving_avg_200:
        score += 3
        decisions.append(f"📊 Osakkeen hinta on alle 200 päivän liukuvan keskiarvon ({moving_avg_200:.2f}) - pitkän aikavälin ostosignaali.")
    
    score += volume_penalty  

    print(f"✅ {asset}: Pistemäärä {score}")

    if score >= 18:
        decisions.append(f"🌟 Vahva ostosuositus: {score} pistettä!")
        return asset, decisions, score
    elif score >= 15:
        decisions.append(f"⭐ Pisteet: {score}, osake voi olla hyvä ostokohde.")
        return asset, decisions, score
    else:
        return asset, None, score  # ✅ Varmistaa oikean palautusrakenteen

def generate_sell_decision(asset, historical_prices, owned_assets):
    """Analysoi osakkeen myyntimahdollisuudet, huomioiden hinnanmuutokset, volyymin, uutiset ja tekniset indikaattorit."""
    print(f"\n🔴🔍 DEBUG: Aloitetaan myyntianalyysi osakkeelle {asset}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price, volume FROM x1
        WHERE ticker = ? ORDER BY datetime DESC LIMIT 1
    ''', (asset,))
    result = cursor.fetchone()
    
    if result:
        current_price, today_volume = result
    else:
        print(f"⚠️ DEBUG: Ei löydetty tietoja osakkeelle {asset} SQLitestä.")
        conn.close()
        return asset, None, 0  

    cursor.execute('''
        SELECT AVG(volume) FROM x1
        WHERE ticker = ? AND datetime >= date('now', '-30 days')
    ''', (asset,))
    avg_volume_30d = cursor.fetchone()[0] or 0  

    conn.close()  # ✅ Suljetaan yhteys DB_FILE:een, koska sitä ei enää tarvita tässä funktiossa

    conn_assets = sqlite3.connect("owned_assets.db")
    cursor_assets = conn_assets.cursor()

    cursor_assets.execute('''
        SELECT purchase_price FROM owned_assets
        WHERE ticker = ? LIMIT 1
    ''', (asset,))
    purchase_result = cursor_assets.fetchone()

    if purchase_result:
        purchase_price = purchase_result[0]
        print(f"✅ Haettu ostohinta osakkeelle {asset} - Ostohinta: {purchase_price}")
        profit_percentage = ((current_price - purchase_price) / purchase_price) * 100
    else:
        print(f"⚠️ Ei löytynyt ostohintaa osakkeelle {asset}.")
        profit_percentage = None       

    conn_assets.close()  # ✅ Suljetaan yhteys owned_assets.db:hen


    if isinstance(historical_prices, float):
        historical_prices = [historical_prices]  # Muutetaan yksittäinen arvo listaksi
    elif not isinstance(historical_prices, list):
        print(f"⚠️ ERROR: {asset} - historical_prices EI OLE LISTA! Se on {type(historical_prices)}")
        return asset, None, 0  

    if historical_prices and isinstance(historical_prices, list):
        last_close_price = historical_prices[-1]  # Oletetaan, että lista sisältää suoraan päätöskursseja
        print(f"✅ {asset} - Viimeisin sulkemishinta historiallisista tiedoista: {last_close_price}")
    else:
        print(f"⚠️ DEBUG: Ei saatavilla aiempia sulkemishintoja osakkeelle {asset}, ohitetaan analyysi.")
        return asset, None, 0  

    try:
        rsi = get_rsi(asset)  
        macd, signal_line, histogram = get_macd(asset)  
        moving_avg_50 = get_moving_average(asset, period=50)  
        moving_avg_200 = get_moving_average(asset, period=200)  

        print(f"📊 {asset} - RSI: {rsi}, MACD: {macd}, Signaalilinja: {signal_line}, Histogrammi: {histogram}")
        print(f"📊 {asset} - 50 päivän liukuva keskiarvo: {moving_avg_50}, 200 päivän liukuva keskiarvo: {moving_avg_200}")

    except Exception as e:
        print(f"⚠️ DEBUG: Virhe indikaattoreiden haussa osakkeelle {asset}: {e}")
        return asset, None, 0  

    negative_news = []
    critical_news = []

    if asset in owned_assets:  # ✅ Tarkistetaan vain osakkeet, ei ETF:t
        news_articles, negative_news, critical_news = fetch_stock_news(asset, owned_assets)

        if not isinstance(news_articles, list):
            print(f"⚠️ ERROR: Uutislista ei ole lista: {type(news_articles)} - {news_articles}")
            news_articles = []

        if news_articles:
            analyzed_negative_news, analyzed_critical_news = analyze_news_sentiment(news_articles)
            
            if isinstance(analyzed_negative_news, list) and isinstance(analyzed_critical_news, list):
                negative_news.extend(analyzed_negative_news)
                critical_news.extend(analyzed_critical_news)
            else:
                print(f"⚠️ ERROR: Uutisanalyysi palautti odottamattoman tyypin: "
                    f"{type(analyzed_negative_news)}, {type(analyzed_critical_news)}")

    score = 0
    decisions = []

    if profit_percentage is not None:
        if profit_percentage > 25:
            if rsi > 70 or macd < signal_line:
                score += 10
                decisions.append(f"💰💰💰 Osakkeen tuotto on {profit_percentage:.2f} % - erittäin hyvä myyntipaikka.")
        elif profit_percentage > 20:  
            score += 5
            decisions.append(f"💰 Osakkeen tuotto on {profit_percentage:.2f} % - hyvä myyntipaikka.")
        elif profit_percentage > 15:  
            score += 3
            decisions.append(f"📈 Osake on noussut {profit_percentage:.2f} % - mahdollinen myyntimahdollisuus.")
        elif profit_percentage < -10:  
            score += 5
            decisions.append(f"⚠️ Osake on laskenut {profit_percentage:.2f} % - harkitse tappioiden minimoimista.")

        elif profit_percentage > 10 and current_price < purchase_price * 1.10:
            score += 7
            decisions.append(f"⚠️ Osake oli noussut yli 20 %, mutta on nyt pudonnut takaisin +10 % tasolle – kannattaa harkita myyntiä.")

    if current_price < last_close_price * 0.97:
        score += 3
        decisions.append(f"🚨 Hinnanlasku {current_price:.2f} (-{(1 - current_price / last_close_price) * 100:.2f}%) - myyntisuositus!")

    if current_price < last_close_price * 0.95:
        score += 5
        decisions.append(f"⚠️ Kriittinen hinnanlasku {current_price:.2f} (-{(1 - current_price / last_close_price) * 100:.2f}%) viimeisen tunnin aikana - vahva myyntisuositus!")

    if current_price < last_close_price * 0.90:
        score += 8
        decisions.append(f"🆘 Romahdus! Hinnanlasku {current_price:.2f} (-{(1 - current_price / last_close_price) * 100:.2f}%) päivän aikana - myynti heti!")

    if avg_volume_30d and today_volume > avg_volume_30d * 3 and current_price < last_close_price:
        score += 2
        decisions.append(f"⚠️ Korkea myyntipaine: Volyymi {today_volume}, yli 3x keskiarvon ({avg_volume_30d}) ja hinta laskee.")

    if moving_avg_50 and moving_avg_200 and moving_avg_50 < moving_avg_200:
        score += 7
        decisions.append(f"⚠️ Kuoleman risti havaittu: 50 päivän liukuva keskiarvo ({moving_avg_50:.2f}) alittaa 200 päivän keskiarvon ({moving_avg_200:.2f}).")

    if critical_news:
        score += 10
        decisions.append(f"🆘 Kriittinen uutinen löydetty ({', '.join(critical_news)})! Välitön myyntisuositus!")

    if negative_news:
        score += 5
        decisions.append(f"⚠️ Negatiivisia uutisia löydetty ({', '.join(negative_news)}) – harkitse myyntiä.")

    if negative_news and current_price < last_close_price * 0.98:
        score += 3
        decisions.append(f"📉 Hinnanlasku negatiivisten uutisten jälkeen - vahvistaa myyntisuositusta!")

    if critical_news and current_price < last_close_price * 0.95:
        score += 5
        decisions.append(f"🚨 Kriittinen uutinen + hinnanlasku -> myynti erittäin suositeltavaa!")

    if histogram < 0:
        score += 2
        decisions.append("📉 MACD-histogrammi negatiivinen – laskutrendi vahvistuu.")
    if histogram < -0.5:
        score += 3
        decisions.append("📉📉 MACD-histogrammi laskee merkittävästi – erittäin vahva laskutrendi.")

    if current_price > last_close_price * 1.03 and macd < signal_line and rsi < 50:
        score += 3
        decisions.append(f"⚠️ Kuolleen kissan pomppu havaittu – varo mahdollista uutta laskua!")

    print(f"✅ {asset}: Myyntipistemäärä {score}")

    if score >= 15:
        decisions.append(f"🌟 Vahva myyntisuositus: {score} pistettä!")
        return asset, decisions, score
    elif score >= 10:
        decisions.append(f"⭐ Pisteet: {score} pistettä – osake voi olla hyvä myyntikohde.")
        return asset, decisions, score
    else:
        print(f"⚠️ DEBUG: {asset}: Myyntisuosituksia ei löytynyt.")
        return asset, None, score  

def generate_decision_message(asset, buy_decisions, sell_decisions, news_risk_message):
    message = ""

    if news_risk_message:
        message += f"⚠️ **Uutisriski**: {news_risk_message}\n"

    if buy_decisions:
        print(f"🔵 {asset} ostosuositukset löytyi: {buy_decisions}")  # Debug-viesti
        message += "\n".join([f"{rec}" for rec in buy_decisions]) + "\n"

    if sell_decisions:
        print(f"🔵 {asset} myyntisuositukset löytyi: {sell_decisions}")  # Debug-viesti
        message += "\n".join([f"{rec}" for rec in sell_decisions]) + "\n"

    if not message.strip():
        print(f"{asset} ei ole suosituksia, ei lähetetä viestiä")  # Debug-viesti
        return None

    return f"**{asset}**\n{message}"

def find_closing_prices(asset):
    """Hakee osakkeen historialliset sulkemishinnat SQLite-tietokannasta ja palauttaa listan pelkkiä numeroita."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT close_price FROM x1
        WHERE ticker = ?
        ORDER BY datetime ASC
    ''', (asset,))

    rows = cursor.fetchall()
    conn.close()

    return [row[0] for row in rows if isinstance(row[0], (int, float))]

async def send_telegram_message(message):
    """
    Lähettää viestin Telegramiin vain, jos viesti ei ole tyhjä.
    """
    if not message.strip():  # Tarkistetaan, että viesti ei ole tyhjä
        print("Ei suosituksia tai viesti tyhjä, ei lähetetä viestiä.")
        return  # Ei lähetetä tyhjää viestiä

    max_message_length = 4096  # Telegramin raja viestin pituudelle
    retries = 3  # Määrä, kuinka monta kertaa yritetään uudelleen
    timeout = 10  # Aikakatkaisu 10 sekuntia

    for attempt in range(retries):
        try:
            if len(message) > max_message_length:
                for i in range(0, len(message), max_message_length):
                    chunk = message[i:i + max_message_length]
                    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk)  # Lisää await
            else:
                await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)  # Lisää await

            break  # Viesti lähetettiin onnistuneesti, ei tarvitse yrittää uudelleen
        except Exception as e:
            print(f"Virhe viestin lähettämisessä: {e}. Yritetään uudelleen...")
            logging.error(f"Virhe viestin lähettämisessä: {e}")  # Kirjataan virhe lokiin
            await asyncio.sleep(2)  # Odotetaan ennen seuraavaa yritystä

def extract_score(decisions):
    """Hakee pisteet suositustekstistä ja palauttaa korkeimman arvon."""
    score_pattern = re.compile(r"(\d+) pistettä")
    scores = [int(match.group(1)) for rec in decisions for match in score_pattern.finditer(rec)]
    return max(scores, default=0)

async def main():
    """Pääohjelma, joka hakee osaketiedot ja analysoi ne."""
    await load_credentials()
    display_banner()
    
    owned_etfs = set(load_assets_from_file(OWNED_ETFS_FILE))  # Muunnetaan listasta setiksi
    print("Omistetut ETF:t ohjelman muistissa:", owned_etfs)

    with open(OWNED_ETFS_FILE, "r") as f:
        actual_owned_etfs = {line.strip() for line in f}
    print("Tiedostosta ladatut ETF:t:", actual_owned_etfs)

    extra_etfs = owned_etfs - actual_owned_etfs
    if extra_etfs:
        print("⚠️ Nämä ETF:t löytyvät ohjelman muistista, mutta eivät owned_etfs.txt:stä:", extra_etfs)
    else:
        print("✅ Kaikki omistetut ETF:t vastaavat tiedostossa olevia.")


    owned_stocks, owned_etfs = await prompt_for_owned_assets()
    
    new_etf_data, etf_error_messages = await fetch_latest_etf_data()
    if etf_error_messages:
        for msg in etf_error_messages:
            if "ERROR" in msg or "KRIITTINEN" in msg:  # Lähetetään vain kriittiset virheet
                await send_telegram_message(msg)
            
    if not new_etf_data:
        print("⚠️ Ei uusia ETF-tietoja saatavilla.")
 
    try:
        with open("sent_etf_decisions.json", "r") as f:
            sent_etf_decisions = json.load(f)

        if not isinstance(sent_etf_decisions, dict):
            print(f"❌ ERROR: `sent_etf_decisions` on väärää tyyppiä: {type(sent_etf_decisions)}. Alustetaan uudelleen.")
            sent_etf_decisions = {}

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ WARNING: Ei voitu ladata `sent_etf_decisions.json` ({e}). Alustetaan tyhjäksi.")
        sent_etf_decisions = {}

    today = datetime.date.today().isoformat()

    if sent_etf_decisions.get("last_update") != today:
        print("🔄 Päivitetään ETF-suositusten tallennus - nollataan pisteet vuorokauden vaihtuessa.")
        sent_etf_decisions = {"last_update": today}

    for etf, etf_data in new_etf_data.items():
        if not etf_data:
            continue

        print(f"🔍 Analysoidaan ETF: {etf}")

        historical_prices = load_historical_etf_data(etf)
        result = generate_etf_buy_decision(etf, etf_data, historical_prices)

        if result is None or not isinstance(result, (list, tuple)) or len(result) != 3:
            print(f"❌ ERROR: `generate_etf_buy_decision()` palautti virheellisen arvon {result} ETF:lle {etf}")
            continue

        etf, buy_decisions, buy_score = result
        buy_score = buy_score or 0  

        if etf in sent_etf_decisions and not isinstance(sent_etf_decisions[etf], dict):
            print(f"❌ ERROR: `sent_etf_decisions[{etf}] EI OLE DICT, VAAN {type(sent_etf_decisions[etf])}!")
            print(f"🔍 DEBUG: Arvo: {sent_etf_decisions[etf]}")
            continue  

        if buy_decisions:
            print(f"✅ {etf}: Ostosuositukset löytyivät! Pisteet: {buy_score}")

            last_buy_score = sent_etf_decisions.get(etf, {}).get("buy_score", 0)
            last_sent_date = sent_etf_decisions.get(etf, {}).get("date", None)

            if buy_score > last_buy_score or last_sent_date != today:
                message = generate_decision_message(etf, buy_decisions, None, None)
                await send_telegram_message(message)

                sent_etf_decisions.setdefault(etf, {})["buy_score"] = buy_score
                sent_etf_decisions.setdefault(etf, {})["date"] = today  
                with open("sent_etf_decisions.json", "w") as f:
                    json.dump(sent_etf_decisions, f)
            else:
                print(f"{etf}: Ostosuosituksen pisteet eivät nousseet. Ei lähetetä viestiä uudelleen.")
        else:
            print(f"{etf}: Pisteet eivät riitä ostosuositukseen.\n")

        print(f"🔵 Ostosuositusanalyysi valmis ETF:lle {etf}\n")

        save_historical_etf_data(etf, etf_data)

    print("\n🔍 Analysoidaan ETF-myyntisuosituksia...")

    for etf in owned_etfs:  # ✅ Käytetään omistettuja ETF:iä myyntianalyysissä
        historical_prices = load_historical_etf_data(etf)  # Ladataan aiemmat hintatiedot
        result = generate_etf_sell_decision(etf, historical_prices, owned_etfs)

        if result is None or not isinstance(result, (list, tuple)) or len(result) != 3:
            print(f"❌ ERROR: `generate_etf_sell_decision()` palautti virheellisen arvon {result} ETF:lle {etf}")
            continue

        etf, sell_decisions, sell_score = result
        sell_score = sell_score or 0  

        if sell_decisions:
            last_sell_info = sent_etf_decisions.get(etf, {}).get("sell_info", {"score": 0, "date": None})
            last_sell_score = last_sell_info.get("score", 0)
            last_sent_date = last_sell_info.get("date", None)

            if sell_score > last_sell_score or last_sent_date != today:
                message = generate_decision_message(etf, None, sell_decisions, None)
                await send_telegram_message(message)

                sent_etf_decisions.setdefault(etf, {})["sell_info"] = {"score": sell_score, "date": today}
                with open("sent_etf_decisions.json", "w") as f:
                    json.dump(sent_etf_decisions, f)

            else:
                print(f"{etf}: Myyntisuosituksen pisteet eivät nousseet ja viesti on jo lähetetty tänään, ei lähetetä uutta viestiä.")
        else:
            print(f"{etf}: Ei riittäviä pisteitä myyntisuositukseen.")

        print(f"\n🔴 Myyntisuositusanalyysi valmis ETF:lle {etf}\n")
        await asyncio.sleep(5)  

    print("\n\n✅✅✅ ETF-analyysi valmis. ✅✅✅\n\n")

    new_data, error_messages = await get_data_block()

    if error_messages:
        for msg in error_messages:
            await send_telegram_message(msg)

    try:
        with open("sent_decisions.json", "r") as f:
            sent_decisions = json.load(f)

        if not isinstance(sent_decisions, dict):
            print(f"❌ ERROR: `sent_decisions` on väärää tyyppiä: {type(sent_decisions)}. Alustetaan uudelleen.")
            sent_decisions = {}

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ WARNING: Ei voitu ladata `sent_decisions.json` ({e}). Alustetaan tyhjäksi.")
        sent_decisions = {}

    today = datetime.date.today().isoformat()

    if sent_decisions.get("last_update") != today:
        print("🔄 Päivitetään suositusten tallennus - nollataan pisteet vuorokauden vaihtuessa.")
        sent_decisions = {"last_update": today}

    for asset, data in new_data.items():
        if not data:
            continue

        print(f"🔍 Analysoidaan osake: {asset}")

        historical_prices = find_closing_prices(asset)
        result = generate_buy_decision(asset, data, historical_prices)

        if result is None or not isinstance(result, (list, tuple)) or len(result) != 3:
            print(f"❌ ERROR: `generate_buy_decision()` palautti virheellisen arvon {result} osakkeelle {asset}")
            continue

        asset, buy_decisions, buy_score = result
        buy_score = buy_score or 0  

        if asset in sent_decisions and not isinstance(sent_decisions[asset], dict):
            print(f"❌ ERROR: `sent_decisions[{asset}] EI OLE DICT, VAAN {type(sent_decisions[asset])}!")
            print(f"🔍 DEBUG: Arvo: {sent_decisions[asset]}")
            continue 

        if buy_decisions:
            print(f"✅ {asset}: Ostosuositukset löytyivät! Pisteet: {buy_score}")

            last_buy_score = sent_decisions.get(asset, {}).get("buy_score", 0)
            last_sent_date = sent_decisions.get(asset, {}).get("date", None)

            if buy_score > last_buy_score or last_sent_date != today:
                message = generate_decision_message(asset, buy_decisions, None, None)
                await send_telegram_message(message)

                sent_decisions.setdefault(asset, {})["buy_score"] = buy_score
                sent_decisions.setdefault(asset, {})["date"] = today  
                with open("sent_decisions.json", "w") as f:
                    json.dump(sent_decisions, f)
            else:
                print(f"{asset}: Ostosuosituksen pisteet eivät nousseet. Ei lähetetä viestiä uudelleen.")
        else:
            print(f"{asset}: Pisteet eivät riitä ostosuositukseen.\n")

        print(f"🔵 Ostosuositusanalyysi valmis osakkeelle {asset}\n")

        save_historical_data_new(asset, data)

        if asset in owned_stocks:
            historical_prices = find_closing_prices(asset)

            if not historical_prices:
                print(f"⚠️ {asset}: Ei historiadataa saatavilla, ohitetaan myyntianalyysi.")
                continue

            result = generate_sell_decision(asset, historical_prices, owned_stocks)

            if result is None or not isinstance(result, (list, tuple)) or len(result) != 3:
                print(f"❌ ERROR: `generate_sell_decision()` palautti odottamattoman arvon {result} osakkeelle {asset}")
                continue  

            asset, sell_decisions, sell_score = result
            sell_score = sell_score or 0  

            if sell_decisions:
                last_sell_info = sent_decisions.get(asset, {}).get("sell_info", {"score": 0, "date": None})
                last_sell_score = last_sell_info.get("score", 0)
                last_sent_date = last_sell_info.get("date", None)

                if sell_score > last_sell_score or last_sent_date != today:
                    message = generate_decision_message(asset, None, sell_decisions, None)
                    await send_telegram_message(message)

                    sent_decisions.setdefault(asset, {})["sell_info"] = {"score": sell_score, "date": today}
                    with open("sent_decisions.json", "w") as f:
                        json.dump(sent_decisions, f)

                else:
                    print(f"{asset}: Myyntisuosituksen pisteet eivät nousseet ja viesti on jo lähetetty tänään, ei lähetetä uutta viestiä.")
            else:
                print(f"{asset}: Ei riittäviä pisteitä myyntisuositukseen.")

            print(f"\n🔴 Myyntisuositusanalyysi valmis osakkeelle {asset}\n")
            await asyncio.sleep(5)  
    print("✅✅✅ Analyysi valmis. ✅✅✅")

run_count = 0  # Lasketaan ajokertoja

async def run_scheduled_task():
    """Toistaa analyysin aina sen päätyttyä ja odottaa 30 minuuttia ennen seuraavaa suoritusta."""
    global start_time, running_task, run_count
    while True:
        try:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🚀 Ohjelma käynnistyy: {now}")
            start_time = time.time()
            running_task = asyncio.create_task(main())  # Luo tehtävän
            await running_task  # Odotetaan tehtävän valmistumista
            duration = time.time() - start_time
            minutes = duration // 60
            seconds = duration % 60
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            run_count += 1  # Kasvata ajokertojen laskuria

            print(f"✅ Suoritus päättyi: {end_time}")
            print(f"🔁 Tämä oli ajokerta numero {run_count}.")
            print(f"⏳ Edellinen ajo kesti {duration:.2f} sekuntia, eli {int(minutes)} minuuttia {seconds:.0f} sekuntia.")

        except asyncio.CancelledError:
            print("Tehtävä keskeytettiin.")
            break
        except Exception as e:
            print(f"❌ ERROR: Virhe ohjelman suorituksessa: {e}")
        print("⏳ Odotetaan 30 minuuttia ennen seuraavaa suoritusta...")
        await asyncio.sleep(30 * 60)

def handle_sigint(signum, frame):
    """ Käsittelee `Ctrl+C`-keskeytyksen ja sulkee ohjelman siististi. """
    global running_task
    duration = time.time() - start_time if start_time else 0
    print(f"\n🔴 Ohjelma lopetettiin käyttäjän toimesta (`Ctrl+C`) {duration:.2f} sekunnin jälkeen.")

    if running_task and not running_task.done():
        running_task.cancel()

        try:
            loop = asyncio.get_running_loop()
            if isinstance(running_task, asyncio.Task) and not loop.is_closed():
                loop.run_until_complete(running_task)
        except asyncio.CancelledError:
            print("✅ Asynkroninen tehtävä peruutettiin turvallisesti.")
        except RuntimeError:
            pass
    logging.shutdown()

    sys.exit(0)

def handle_sigtstp(signum, frame):
    """Käsittelee `Ctrl+Z`-keskeytyksen ja antaa huomion sekä jatkamisen ohjeen."""
    duration = time.time() - start_time if start_time else 0
    print(f"\n🟡 Ohjelma keskeytettiin tilapäisesti (`Ctrl+Z`) {duration:.2f} sekunnin jälkeen.")
    print("ℹ️ Jatka suoritusta komennolla: `fg`")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTSTP, handle_sigtstp)

    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            print("⚠️  ERROR: Tapahtumasilmukka on jo käynnissä, käytetään `loop.create_task()`.")
            loop.create_task(run_scheduled_task())
        else:
            asyncio.run(run_scheduled_task())  # Käynnistetään ajastus heti
    except RuntimeError:
        asyncio.run(run_scheduled_task())
    except Exception as e:
        print(f"❌ ERROR: Virhe ohjelman suorittamisessa: {e}")