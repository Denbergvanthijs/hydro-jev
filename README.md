# hydro-jev

Lokale Python-app die Home Assistant-context aan Jev geeft, zodat Jev beslist of het pas ingezaaide gazon nu vijf minuten water nodig heeft. De applicatie wordt handmatig per run gestart; plan deze pas later in als de dry-run-uitvoer eerst voldoende is gecontroleerd.

De huidige versie kan de pomp nooit inschakelen. Er is geen codepad voor `switch.turn_on` of een andere pomp-service-call.

## Installatie op Windows

Open de projectmap in VS Code en voer in de PowerShell-terminal uit:

```powershell
conda create --name hydro-jev python=3.12
conda activate hydro-jev
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Selecteer daarna in VS Code de interpreter van de `hydro-jev` Conda-omgeving.

## Omgevingsvariabelen

Vul `.env` lokaal in. Dit bestand staat op de ignore-lijst en mag nooit worden gecommit.

```dotenv
HA_URL=http://192.168.1.101:8123
HA_TOKEN=je_home_assistant_long_lived_access_token
TYPESAFE_API_KEY=je_typesafe_api_key
LAWN_SOWING_DATE=2026-09-26
DRY_RUN=true
```

Maak in Home Assistant een Long-Lived Access Token aan via je gebruikersprofiel. De token wordt alleen als `Authorization: Bearer ...` gebruikt en wordt niet gelogd.

Maak een API key aan bij TypeSafe en zet die in `TYPESAFE_API_KEY`. De officiële SDK gebruikt die key voor TypeSafe's eigen API en vraagt Jev op met model `jev`.

De projectbeschrijving bevat geen entity-ID’s voor elektriciteitsprijzen. Als je die in HA hebt, configureer ze in `.env`:

```dotenv
HA_PRICE_ENTITY_ID=sensor.jouw_actuele_prijs
HA_PRICE_FORECAST_ENTITY_ID=sensor.jouw_prijsverwachting
```

De prijsverwachting wordt gelezen uit de `prices`- of `forecast`-state-attributen wanneer die een lijst met prijsrecords bevatten. Ontbrekende of niet herkenbare data wordt als ontbrekend doorgegeven, niet ingevuld.

## Dry run

Start de applicatie vanuit de projectmap:

```powershell
python main.py
```

De run haalt states en 12 uur HA-history op, vraagt met de officiële Home Assistant REST API de beschikbare uurlijkse weerforecast op, bouwt een gestructureerde context, roept Jev aan en past de lokale safety-laag toe. De forecast-opvraag is uitsluitend data ophalen. Er wordt nooit een Home Assistant-pompservice aangeroepen, ook niet wanneer `DRY_RUN` handmatig op `false` is gezet. De standaard blijft `DRY_RUN=true`.

De beslissing verschijnt als JSON op het scherm en in de logs. Ontbrekende sensoren en API-data worden vermeld. Zonder betrouwbare dagelijkse sproeiduur blokkeert de safety-laag een positief sproeiadvies, omdat de daglimiet anders niet te controleren is.

De elektrische prijslimiet van €0,70/kWh is instructie voor Jev, geen lokale if/else-beslisregel. Jev beslist ook zelf of de omstandigheden extreem droog zijn en geeft een droogtescore van 0 tot 4 terug. De applicatie vraagt alleen advies voor NU precies vijf minuten sproeien; de score bepaalt niet de irrigatiebeslissing.

## Tests en kwaliteitschecks

```powershell
pytest
ruff check .
ruff format --check .
ty check
```

De tests gebruiken fakes en fixtures; ze verbinden niet met Home Assistant of TypeSafe en bevatten geen mogelijkheid om de pomp te starten.

## Veiligheidsmechanisme

- `MAX_MINUTES_PER_DAY = 20` en `DRY_RUN=true` staan centraal in de configuratie. Jev krijgt deze instellingen niet als aanpasbare beslisvelden.
- Een ontbrekende of ongeldige Jev-respons wordt behandeld als niet sproeien.
- Een ongeldige sproeiduur, onbetrouwbare dagelijkse sproeiduur of overschrijding van de daglimiet blokkeert het advies.
- De enige uitvoer is een advies; pompbediening is niet geïmplementeerd.
- Geheimen komen niet in logs. Logs bevatten wel de context, Jev-kans, droogtescore, veiligheidsinterventie en uiteindelijke dry-run-uitkomst.

## Projectstructuur

De actuele regenhistorie wordt niet als een opgetelde millimeterwaarde verzonnen: deze versie stuurt HA-weatherhistorie en beschikbare neerslagobservaties door, en houdt `recent_rainfall_mm` expliciet leeg zolang er geen betrouwbare bron/aggregatie is.
