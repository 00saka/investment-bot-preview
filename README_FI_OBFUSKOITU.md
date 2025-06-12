# Sijoitusbotti (Julkinen esiversio)

Tämä ohjelma on yksinkertaistettu ja obfuskoitu versio henkilökohtaisesta sijoitusbotista, joka analysoi markkinadataa ja antaa osto- tai myyntisuosituksia.

Ohjelman käyttöliittymä (esimerkiksi käyttäjälle näkyvät viestit, kyselyt ja tulosteet) on pääosin suomenkielinen, koska ohjelma on alun perin kehitetty henkilökohtaiseen käyttöön. Dokumentaatio on saatavilla englanniksi.

Ohjelma hyödyntää myös paikallista SQLite-tietokantaa sijoitustietojen, kuten ostohintojen ja omien sijoitusten historian tallentamiseen. Näitä tietoja käytetään analyysien tukena.
 Varsinaista sijoittamista ei tapahdu automaattisesti, vaan ohjelma välittää suosituksia Telegramin kautta.

## Ominaisuudet

- Lataa ajankohtaiset osaketiedot API:n kautta
- Analysoi tietoja sisäisten laskentaperiaatteiden mukaan
- Antaa osto- tai myyntisuosituksia valittujen osakkeiden tai ETF:ien perusteella
- Lähettää suositukset Telegram-viestinä
- Muistaa omistusten ostohinnat ja hyödyntää niitä analyysissa

⚠️ **Tämä versio ei sisällä ohjelman täydellistä logiikkaa tai laskentakaavoja.**

## Yksityisyys ja turvallisuus

API-avaimia tai tunnistetietoja ei ole sisällytetty tiedostoon. Täydellinen versio käyttää salattua ulkoista avaintiedostoa, jota ei julkaista.

## Huomioitavaa

- Tämä versio on tarkoitettu ainoastaan ohjelmointitaitojen havainnollistamiseen.
- Ohjelma ei sisällä kaikkea alkuperäistä toiminnallisuutta tai logiikkaa.
- Suositukset eivät ole sijoitusneuvoja.

---

© 2025 Ralf Isorinne. **All rights reserved.**
