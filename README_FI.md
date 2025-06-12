# 📈 Sijoitusbotti (julkinen esiversio)

Tämä on julkinen ja yksinkertaistettu esikatseluversio henkilökohtaisesti kehitetystä sijoitusbotista. Botti analysoi osakkeiden ja ETF:ien tietoja, tekee osto- ja myyntisuosituksia ja lähettää ilmoituksia Telegramin kautta. Ohjelman tavoitteena on havainnollistaa ohjelmointiosaamista ilman, että varsinainen sijoituslogiikka tai kaikki ominaisuudet paljastetaan.

## 🔧 Ominaisuudet

- Lataa reaaliaikaisia osaketietoja API-rajapinnan kautta
- Tekee teknisiä ja perustunnusluvuista johdettuja analyyseja
- Antaa osto- ja myyntisuosituksia valituista osakkeista ja ETF:istä
- Lähettää suositukset Telegramin kautta käyttäjälle
- Myyntisuosituksia annetaan vain jo omistetuista kohteista
- Tallentaa osakkeiden ja ETF:ien ostohinnat paikalliseen SQLite-tietokantaan
- Käyttöliittymä ja tulosteet suomeksi
- Ohjelman logiikka hyödyntää mm. seuraavia tietoja:
  - PE- ja PB-luvut
  - Sektoritiedot
  - Liukuvat keskiarvot
  - Omistushinta-analyysi

⚠️ Tämä versio ei sisällä täydellistä algoritmista logiikkaa eikä tarkkoja laskentakaavoja.

## 🔐 Tietoturva ja yksityisyys

- Tämä versio ei sisällä API-avaimia tai salasanoja
- Täysi versio käyttää suolattua ja salattua avaintiedostoa (AES + suolaus), jonka purku vaatii salasanan
- Telegram-yhteys toimii vain lähetyskanavana – ohjelmaa ei voi ohjata Telegramin kautta

## 🛠️ Käytetyt teknologiat

- Python 3
- `yfinance` osaketietojen hakemiseen
- `sqlite3` paikalliseen tietokantaan
- `ssl`, `base64`, `cryptography` salaukseen ja avainten käsittelyyn
- `tmux` ja `venv` kehitysympäristöissä käyttöön ja testaukseen
- Telegram Bot API viestien lähettämiseen

## 🧾 Dokumentaatio ja lähteet

Ohjelman kehityksessä on hyödynnetty muun muassa seuraavia lähteitä:

- https://pypi.org/project/yfinance/
- https://core.telegram.org/bots/api
- https://sqlite.org/docs.html
- https://www.investopedia.com/
- https://www.morningstar.com/
- https://stackoverflow.com/
- https://realpython.com/
- https://cryptography.io/

## 📄 Huomautukset

- Tämä versio on tarkoitettu ainoastaan ohjelmointiosaamisen havainnollistamiseen
- Ei sisällä koko alkuperäistä logiikkaa tai kaupallisia ominaisuuksia
- Suositukset eivät ole sijoitusneuvoja
- Ohjelman käyttö ja laajentaminen omalla vastuulla

© 2025 Ralf Isorinne. All rights reserved.
