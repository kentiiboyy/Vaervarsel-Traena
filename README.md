# Værvarsel Træna

En egen nettside med vær, flo og fjære, stormflo, bølger og nordlys for Træna.
Siden ligger gratis på GitHub Pages og oppdaterer seg selv hver time.

## Slik virker det

- `site/index.html` er selve nettsiden. Den leser `data.json` og henter nye tall hvert 10. minutt mens den er åpen.
- `fetch_data.py` henter data fra Kartverket, MET og NOAA og skriver `data.json`.
- `.github/workflows/oppdater.yml` kjører `fetch_data.py` hver time på GitHubs maskiner og legger ut siden på nytt.
  Hentingen skjer på GitHub (ikke i nettleseren), med en identifikasjon som peker til repoet ditt slik MET ber om.
  Det er derfor ingen problemer med at nettlesere ikke får hente data fra andre nettsteder.
- Svikter én kilde, beholdes forrige tall for den kilden, og resten oppdateres.

## Sette den opp (ca. 10 minutter)

1. **Lag en konto** på [github.com](https://github.com) hvis du ikke har en.
2. **Lag et nytt repo:** trykk «+» øverst til høyre → «New repository».
   Gi det navnet `vaervarsel-traena`, velg **Public** og trykk «Create repository».
3. **Last opp filene:** trykk «uploading an existing file» (eller «Add file» → «Upload files»).
   Dra inn `fetch_data.py`, `README.md`, `.gitignore` og hele mappa `site`. Trykk «Commit changes».
4. **Legg inn arbeidsflyten.** Mapper som starter med punktum (`.github`) blir ofte ikke med når man drar filer inn,
   så gjør dette for hånd: «Add file» → «Create new file». Skriv filnavnet
   `.github/workflows/oppdater.yml` (skråstrekene lager mappene), lim inn innholdet fra filen med samme navn,
   og trykk «Commit changes».
5. **Slå på nettsiden:** «Settings» → «Pages». Under «Build and deployment» → «Source», velg **GitHub Actions**.
6. **Kjør første oppdatering:** «Actions» → «Oppdater værdata» → «Run workflow».
   Etter et par minutter ligger siden på
   `https://<brukernavnet-ditt>.github.io/vaervarsel-traena/`
   (adressen står også under «Settings» → «Pages»).

Etter dette oppdateres siden av seg selv hver time.

## Eget domene (valgfritt)

Har du for eksempel `traena-vaer.no`:

1. «Settings» → «Pages» → «Custom domain»: skriv inn domenet og lagre.
2. Hos domeneleverandøren: lag en **CNAME**-oppføring for `www` som peker til `<brukernavnet-ditt>.github.io`.
   For domenet uten `www` legger du inn A-oppføringer til GitHubs adresser
   (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153).
3. Kryss av for «Enforce HTTPS» når valget dukker opp.

## Godt å vite

- GitHub stopper planlagte kjøringer i repoer som ikke har hatt aktivitet på 60 dager.
  Arbeidsflyten lager derfor en liten commit (`keepalive.txt`) hver mandag for å holde seg i gang.
  Stopper den likevel: gå til «Actions» og trykk «Enable workflow».
- Timene i GitHubs planlegger kan bli forsinket noen minutter når det er travelt.
- Varselet til telefonen kommer fortsatt fra Claude, som før. Det påvirkes ikke av nettsiden.
- Kilder: [Kartverket](https://www.kartverket.no/til-sjos/se-havniva) og [MET Norway](https://api.met.no) (CC BY 4.0),
  [NOAA SWPC](https://www.swpc.noaa.gov/products/planetary-k-index). Kildene er oppgitt nederst på siden.
- Endre sted: koordinatene står øverst i `fetch_data.py` (`LAT`, `LON`) og i `site/index.html` (`LAT`, `LON`, brukes til å regne ut når det er mørkt).
  Stormflonivåene (`LEVELS`) gjelder målestasjonen på Træna.
