# 📈 Investment Bot (Public Preview Version)

This is a public and simplified preview version of a personally developed investment bot. The bot analyzes stock and ETF data, makes buy/sell recommendations, and sends notifications via Telegram. The goal is to demonstrate programming capability without revealing full investment logic or proprietary features.

## 🔧 Features

- Downloads real-time stock data via API
- Performs technical and fundamental analysis
- Issues buy/sell suggestions for selected stocks and ETFs
- Sends recommendations to the user via Telegram
- Issues sell suggestions only for owned assets
- Remembers purchase prices for assets in a local SQLite database
- User interface and outputs are in Finnish
- Analysis includes:
  - PE and PB ratios
  - Sector information
  - Moving averages
  - Purchase price-based insights

⚠️ This version does not include full algorithmic logic or exact formulas.

## 🔐 Privacy and Security

- No API keys or passwords are included
- Full version uses salted and encrypted key file (AES + salt), decrypted using a password
- Telegram is used only for sending messages – it cannot control the bot

## 🛠️ Technologies Used

- Python 3
- `yfinance` for stock data
- `sqlite3` for local database
- `ssl`, `base64`, `cryptography` for encryption and key handling
- `tmux` and `venv` for development and testing
- Telegram Bot API for message delivery

## 🧾 Documentation and Sources

The following sources were used in development:

- https://pypi.org/project/yfinance/
- https://core.telegram.org/bots/api
- https://sqlite.org/docs.html
- https://www.investopedia.com/
- https://www.morningstar.com/
- https://stackoverflow.com/
- https://realpython.com/
- https://cryptography.io/

## 📄 Notes

- This version is intended solely to showcase programming skills
- Does not include full original logic or commercial features
- Recommendations are not financial advice
- Use and modification at your own risk

© 2025 Ralf Isorinne. All rights reserved.
