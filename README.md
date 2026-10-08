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
HA_URL=http://192.168.1.101
HA_TOKEN=je_home_assistant_long_lived_access_token
TYPESAFE_API_KEY=je_typesafe_api_key
HA_TIMEOUT_SECONDS=10
TIMEZONE=Europe/Amsterdam
HA_PUMP_ENTITY_ID=switch.athom_stekker_kantoor_switch
HA_WEATHER_ENTITY_ID=weather.forecast_home
LAWN_AREA_M2=45
SPRINKLER_COUNT=2
LAWN_SOWING_DATE=2026-09-26
WATERING_MINUTES=5
MAX_MINUTES_PER_DAY=20
MAX_ELECTRICITY_PRICE_EUR_KWH=0.70
DRY_RUN=true
```

Maak in Home Assistant een Long-Lived Access Token aan via je gebruikersprofiel. De token wordt alleen als `Authorization: Bearer ...` gebruikt en wordt niet gelogd.

Maak een API key aan bij TypeSafe en zet die in `TYPESAFE_API_KEY`. De officiële SDK gebruikt die key voor TypeSafe's eigen API. Zonder modeloverride kiest de SDK het gedocumenteerde standaardmodel `jev-latest`.

Alle irrigatiesensoren zijn configureerbaar. De standaardwaarden staan in `.env.example`; vervang ze wanneer jouw Home Assistant andere entity-ID's gebruikt:

```dotenv
HA_PUMP_POWER_ENTITY_ID=sensor.athom_stekker_kantoor_power
HA_CUMULATIVE_ENERGY_ENTITY_ID=sensor.athom_stekker_kantoor_energy
HA_WATERING_EVENTS_TODAY_ENTITY_ID=sensor.hydrofoor_inschakelingen_vandaag
HA_WATERING_EVENTS_WEEK_ENTITY_ID=sensor.hydrofoor_inschakelingen_deze_week
HA_TODAY_WATERING_MINUTES_ENTITY_ID=sensor.hydrofoor_inschakelduur_vandaag
HA_WATERING_MINUTES_WEEK_ENTITY_ID=sensor.hydrofoor_inschakelduur_deze_week
HA_ENERGY_KWH_TODAY_ENTITY_ID=sensor.hydrofoor_verbruik_vandaag
HA_ENERGY_KWH_WEEK_ENTITY_ID=sensor.hydrofoor_verbruik_deze_week
SAMPLE_CONTEXT_PATH=data\sample_context.json
```

De projectbeschrijving bevat geen entity-ID’s voor elektriciteitsprijzen. Als je die in HA hebt, configureer ze in `.env`:

```dotenv
HA_PRICE_ENTITY_ID=sensor.jouw_actuele_prijs
HA_PRICE_FORECAST_ENTITY_ID=sensor.jouw_prijsverwachting
```

`HA_PRICE_ENTITY_ID` levert de actuele prijs uit de state-waarde. `HA_PRICE_FORECAST_ENTITY_ID` levert toekomstige prijzen uit een lijst in de state-attributen. Dat mag dezelfde entity zijn wanneer die beide bevat: de Frank Energie-entity hierboven heeft een actuele state en een `prices`-lijst met records (`from`, `price`, `till`). De applicatie leest dan de huidige prijs en filtert de lijst op de komende 12 uur. Ontbrekende of niet herkenbare data wordt als ontbrekend doorgegeven, niet ingevuld.

De gazonoppervlakte en het aantal sproeiers zijn eveneens configureerbaar:

```dotenv
LAWN_AREA_M2=45
SPRINKLER_COUNT=2
```

## Dry run

Start de applicatie vanuit de projectmap:

```powershell
python main.py
```

Standaard gebruikt dit de live Home Assistant-data. Om de meegeleverde context uit `data/sample_context.json` te gebruiken zonder verbinding met HA:

```powershell
python main.py --source sample
```

Beide routes gebruiken dezelfde Jev- en safety-stappen. De sample-route heeft geen `HA_TOKEN` nodig, maar vraagt nog wel een `TYPESAFE_API_KEY` om Jev echt aan te roepen. Je kunt een ander contextbestand kiezen met `--sample-file pad\naar\context.json`. Dezelfde functies zijn ook vanuit Python te gebruiken: `run_with_home_assistant(...)`, `run_with_sample_json(...)` en `run_context(...)` in `main.py`.

De run haalt states en 12 uur HA-history op, vraagt met de officiële Home Assistant REST API de beschikbare uurlijkse weerforecast op, bouwt een gestructureerde context, roept Jev aan en past de lokale safety-laag toe. De forecast-opvraag is uitsluitend data ophalen. Er wordt nooit een Home Assistant-pompservice aangeroepen, ook niet wanneer `DRY_RUN` handmatig op `false` is gezet. De standaard blijft `DRY_RUN=true`.

De beslissing verschijnt als JSON op het scherm en in de logs. Ontbrekende sensoren en API-data worden vermeld. Zonder betrouwbare dagelijkse sproeiduur blokkeert de safety-laag een positief sproeiadvies, omdat de daglimiet anders niet te controleren is.

De elektrische prijslimiet is instructie voor Jev, geen lokale if/else-beslisregel. Jev beslist ook zelf of de omstandigheden extreem droog zijn en geeft een droogtescore van 0 tot 4 terug. De applicatie vraagt advies voor het aantal minuten uit `WATERING_MINUTES`; de score bepaalt niet de irrigatiebeslissing.

## Tests en kwaliteitschecks

```powershell
python -m pytest
python -m pytest --cov --cov-report=term-missing
python -m ruff check . --fix
python -m ruff format .
python -m ty check
```

De tests gebruiken fakes en fixtures; ze verbinden niet met Home Assistant of TypeSafe en bevatten geen mogelijkheid om de pomp te starten.

## Veiligheidsmechanisme

- `WATERING_MINUTES`, `MAX_MINUTES_PER_DAY`, `MAX_ELECTRICITY_PRICE_EUR_KWH` en `HA_TIMEOUT_SECONDS` zijn configureerbaar via `.env`.
- Een ontbrekende of ongeldige Jev-respons wordt behandeld als niet sproeien.
- Een ongeldige sproeiduur, onbetrouwbare dagelijkse sproeiduur of overschrijding van de daglimiet blokkeert het advies.
- De enige uitvoer is een advies; pompbediening is niet geïmplementeerd.
- Geheimen komen niet in logs. Logs bevatten wel de context, Jev-kans, droogtescore, veiligheidsinterventie en uiteindelijke dry-run-uitkomst.
