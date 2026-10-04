# hydro-jev

Je bent mijn programmeerassistent voor een Python hobbyproject genaamd "hydro-jev".

DOEL
Ik wil een Python-applicatie bouwen die Home Assistant gebruikt om automatisch te bepalen of mijn pas ingezaaide gazon op dit moment gesproeid moet worden.

De applicatie draait voorlopig lokaal op mijn laptop vanuit VS Code. Home Assistant draait op mijn Raspberry Pi en is bereikbaar via de Home Assistant REST API.

Gebruik voor Jev uitsluitend de officiële TypeSafe Python SDK:
<https://docs.typesafe.ai/sdk/python/usage>

Gebruik voor Home Assistant uitsluitend de officiële REST API:
<https://developers.home-assistant.io/docs/api/rest/>

Gebruik dus geen eigen HTTP-protocol, scraping, databasekopie of onofficiële Jev-integratie.

BELANGRIJK

- Controleer bij twijfel eerst de actuele officiële documentatie van TypeSafe en Home Assistant.
- Verzin geen SDK-methodes, imports, parameters of response-formaten.
- Gebruik de officiële TypeSafe SDK zoals die momenteel in de documentatie wordt beschreven.
- Houd de implementatie eenvoudig en goed leesbaar.
- Geen onnodige frameworks.
- Gebruik Python type hints.
- Gebruik Pydantic waar dat logisch is voor gestructureerde data en typed responses.
- Secrets mogen nooit hardcoded worden.
- Gebruik een .env-bestand en .gitignore.
- Schrijf code alsof dit een klein maar serieus Python-project is.
- We bouwen eerst lokaal en veilig. De pomp mag voorlopig NOOIT automatisch worden ingeschakeld.

PROJECTDOEL

De applicatie wordt ieder uur uitgevoerd.

Home Assistant levert de context:

1. actuele weersinformatie
2. weersverwachting
3. recente sproeihistorie
4. hoeveel er vandaag al gesproeid is
5. leeftijd van het gazon
6. actuele elektriciteitsprijs
7. beschikbare elektriciteitsprijzen voor de komende uren

Vervolgens krijgt Jev deze context en beslist uitsluitend:

"Moet het gazon NU gesproeid worden voor 5 minuten?"

De uiteindelijke Jev-beslissing moet daarom ongeveer deze informatie bevatten:

- sproeien_nu: boolean
- probability: float

Jev moet daadwerkelijk de irrigatiebeslissing nemen. Bouw dus niet een klassieke if/else-regelset die de beslissing vooraf voor Jev bepaalt.

WEL moet er na Jev een harde veiligheidslaag zitten. Die veiligheidslaag is geen irrigatie-algoritme, maar voorkomt dat een foutieve Jev-beslissing schade veroorzaakt.

CONTEXT OVER HET GAZON

- Gazon: 9 x 5 meter = 45 m²
- Er zijn twee sprinklers.
- Beide sprinklers draaien tegelijk.
- Grondwater/hydrofoor voedt de sprinklers.
- Het gazon is op zaterdag 26 september 2026 geverticuteerd, ingezaaid en bemest.
- Zaaidatum moet in de configuratie staan en niet verspreid door de code voorkomen.

HOME ASSISTANT

Home Assistant URL staat in .env:

HA_URL=<http://192.168.1.101:8123>

Authenticatie gebeurt via een Long-Lived Access Token:

HA_TOKEN=...

Gebruik:

Authorization: Bearer <token>

Belangrijke entities:

Pomp:
switch.athom_stekker_kantoor_switch

Pompstroom:
sensor.athom_stekker_kantoor_current

Pompkracht:
sensor.athom_stekker_kantoor_power

Cumulatief energieverbruik:
sensor.athom_stekker_kantoor_energy

Sproeibeurten vandaag:
sensor.hydrofoor_inschakelingen_vandaag

Sproeibeurten deze week:
sensor.hydrofoor_inschakelingen_deze_week

Sproeiduur vandaag:
sensor.hydrofoor_inschakelduur_vandaag

Sproeiduur deze week:
sensor.hydrofoor_inschakelduur_deze_week

Energieverbruik vandaag:
sensor.hydrofoor_verbruik_vandaag

Energieverbruik deze week:
sensor.hydrofoor_verbruik_deze_week

Weer via Met.no integratie:
weather.forecast_home

Gebruik de HA REST API voor actuele states.

Gebruik de HA history API om de daadwerkelijke geschiedenis van de pomp/sproeibeurten op te halen.

Geef Jev minimaal de relevante sproeihistorie van de afgelopen 12 uur.

WEER

Jev moet, indien beschikbaar, informatie krijgen over:

- huidige temperatuur
- luchtvochtigheid
- actuele neerslag
- neerslag in de afgelopen 12 uur
- verwachte neerslag in de komende 12 uur
- temperaturen in de komende 12 uur
- overige beschikbare relevante weersinformatie

Geef de informatie gestructureerd door aan Jev.

Geef niet blind de volledige HA weather entity door als dat niet nodig is.

Als HA geen bepaalde forecastinformatie beschikbaar maakt, behandel dat als ontbrekende data. Verzin nooit waarden.

ELEKTRICITEITSPRIJS

De actuele elektriciteitsprijs moet aan Jev worden doorgegeven.

Indien beschikbare toekomstige prijzen aanwezig zijn, geef ook de prijzen voor de komende 12 uur door.

De prijs is geen primaire reden om wel/niet te sproeien.

Regel:

- boven €0,70/kWh is de prijs normaal gesproken extreem duur en mag Jev ervoor kiezen niet te sproeien;
- bij extreme droogte mag Jev deze prijsgrens negeren.

Jev moet zelf bepalen of de omstandigheden extreem droog zijn.

Gebruik geen hardcoded regel zoals:
if price > 0.70: don't water

De beslissing blijft bij Jev.

TIJDVENSTER

Jev krijgt:

- relevante (weers)geschiedenis van de afgelopen 12 uur
- beschikbare weersverwachting voor de komende 12 uur
- beschikbare elektriciteitsprijzen voor de komende 12 uur

Als minder data beschikbaar is, moet de applicatie gewoon functioneren en de ontbrekende data expliciet aangeven.

SPROEIHISTORIE

Het is belangrijk dat Jev kan zien dat recent sproeien invloed heeft op de beslissing.

Bijvoorbeeld:

09:00 -> 5 minuten gesproeid
10:00 -> niet opnieuw sproeien
11:00 -> mogelijk nog steeds niet nodig
12:00 -> opnieuw beoordelen

Geef daarom niet alleen "minuten vandaag" door, maar ook een bruikbare tijdreeks van recente sproeibeurten.

De applicatie moet uit de HA history kunnen afleiden wanneer de pomp aan/uit is gegaan en daar sproeisessies van maken.

Een sproeisessie bevat minimaal:

- starttijd
- eindtijd
- duur in minuten

Als een sessie niet betrouwbaar bepaald kan worden, geef dat aan in de data in plaats van iets te verzinnen.

JEV BESLISSING

Gebruik de officiële TypeSafe SDK.

Gebruik een typed response/model zodat de output van Jev niet als willekeurige tekst hoeft te worden geparsed.

Gewenste response:

class IrrigationDecision(...):
    sproeien_nu: bool
    probability: float

De exacte implementatie moet aansluiten op de actuele officiële TypeSafe SDK-documentatie.

Jev moet begrijpen:

- het doel is alleen bepalen of NU sproeien nodig is;
- recente sproeibeurten zijn belangrijk;
- toekomstige regen kan reden zijn om nu niet te sproeien;
- felle zonneschijn kan een reden zijn om nu niet te sproeien, om het gras niet te verbranden;
- het gras is recent bijgezaaid dus regelmatig water is van belang;
- recente regen is belangrijk;
- hoge elektriciteitsprijzen zijn alleen relevant als het niet dringend/extreem droog is;
- Jev mag zelf bepalen hoe droog het gazon is op basis van de beschikbare context;

VEILIGHEID

De Jev-output moet (voor nu) altijd door een lokale veiligheidslaag gaan.

Deze waarden moeten centraal configureerbaar zijn:

MAX_MINUTES_PER_DAY = 20
DRY_RUN = true

Deze waarden mogen NIET door Jev worden aangepast.

De veiligheidslaag moet bijvoorbeeld:

1. voorkomen dat de dagelijkse limiet wordt overschreden;
2. een ongeldige of ontbrekende Jev-beslissing als "niet sproeien" behandelen;
3. negatieve of onrealistische sproeiduur afwijzen;
4. nooit automatisch de pomp starten zolang DRY_RUN=true.

Kies een duidelijke veilige behandeling en log waarom.

DRY RUN

Gebruik:

DRY_RUN=true

als standaard.

Wanneer DRY_RUN=true:

- haal alle data op;
- roep Jev aan;
- voer de veiligheidslaag uit;
- toon de uiteindelijke beslissing;
- log de beslissing;
- schakel de pomp NOOIT in.

Er mag geen codepad zijn waarbij een test automatisch de pomp activeert.

Maak pas later een expliciete mogelijkheid om de HA service-call te activeren.

ARCHITECTUUR

Gebruik ongeveer deze structuur:

hydro-jev/
├── .env
├── .gitignore
├── requirements.txt
├── README.md
├── main.py
├── config.py
├── ha/
│   ├── __init__.py
│   ├── client.py
│   └── history.py
├── jev/
│   ├── __init__.py
│   ├── client.py
│   └── models.py
├── irrigation/
│   ├── __init__.py
│   ├── context.py
│   └── safety.py
└── tests/
    ├── test_history.py
    ├── test_safety.py
    └── test_context.py

Als je een betere eenvoudige structuur hebt, mag je daarvan afwijken, maar houd de verantwoordelijkheden gescheiden.

RESPONSIBILITIES

ha/client.py:

- Home Assistant REST API client
- get_state()
- get_history()
- eventueel call_service(), maar deze mag voorlopig niet gebruikt worden

ha/history.py:

- vertaal HA state-history naar betekenisvolle sproeisessies

irrigation/context.py:

- verzamel alle relevante HA-data
- maak één nette Python/Pydantic context voor Jev

jev/client.py:

- configureer de officiële TypeSafe SDK
- stuur de context naar Jev
- ontvang de typed IrrigationDecision

jev/models.py:

- Pydantic models voor Jev input/output waar passend

irrigation/safety.py:

- harde veiligheidsregels
- nooit verantwoordelijk voor het bepalen van de irrigatiebehoefte

main.py:

- orchestration
- context ophalen
- Jev aanroepen
- safety uitvoeren
- resultaat tonen/loggen

TESTS

Maak tests voor ten minste:

1. Geen recente sproeibeurt -> safety laat beslissing door.
2. Daglimiet bereikt -> sproeien wordt geblokkeerd.
3. Ongeldige Jev-output -> niet sproeien.
4. Sproeihistorie met meerdere aan/uit-cycli -> correcte sessies.
5. Onvolledige HA-data -> context kan nog steeds worden opgebouwd.

BELANGRIJK VOOR TESTBAARHEID

De kernlogica mag niet afhankelijk zijn van live Home Assistant.

Gebruik dependency injection waar eenvoudig.

Tests moeten met fixtures/mocks kunnen draaien zonder verbinding met HA of OpenRouter.

Maak eventueel een voorbeeldbestand:

data/sample_context.json

zodat de Jev-context lokaal bekeken en getest kan worden.

LOGGING

Gebruik Python logging.

Log minimaal:

- tijdstip
- actuele relevante context
- Jev-beslissing
- sproeiduur
- droogte-inschatting
- reden
- veiligheidsinterventie indien van toepassing
- uiteindelijke beslissing

Log nooit:

- HA_TOKEN
- JEV_API_KEY
- andere secrets

README

Maak een README met:

1. doel van het project
2. installatie
3. virtual environment
4. requirements installeren
5. .env instellen
6. Home Assistant token aanmaken
7. OpenRouter API key instellen
8. dry-run uitvoeren
9. tests uitvoeren
10. projectstructuur
11. veiligheidsmechanisme

INSTALLATIE

Ga uit van Windows + VS Code.

Geef commando's voor:

miniconda omgeving opzetten en het activeren van de virtual environment.

GIT

.env mag NOOIT worden gecommit.

CODEKWALITEIT

Gebruik:

- Python 3.12+
- Ruff, Ty en Pytest
- type hints
- dataclasses of Pydantic waar passend
- duidelijke functies
- kleine modules
- geen globale HTTP calls
- geen verborgen side effects
- geen over-engineering
- geen async tenzij het daadwerkelijk voordeel oplevert
- geen databasekopie van Home Assistant

WERKWIJZE

Voer dit project niet blind volledig uit zonder controle.

Werk in deze volgorde:

1. Inspecteer eerst de huidige workspace.
2. Bepaal welke bestanden al bestaan.
3. Controleer of requirements/projectconfiguratie al aanwezig zijn.
4. Controleer de actuele TypeSafe SDK-documentatie voordat je SDK-code schrijft.
5. Controleer de actuele Home Assistant REST API-documentatie voordat je HA-code schrijft.
6. Stel daarna een kort implementatieplan voor.
7. Implementeer vervolgens de basis.
8. Geef duidelijk aan welke bestanden je hebt aangemaakt of gewijzigd.
9. Geef daarna aan welke commando's ik in VS Code moet uitvoeren om het lokaal te testen.
10. Start nog GEEN echte Home Assistant service-call.
11. DRY_RUN moet standaard true zijn.

Als een API of SDK niet precies overeenkomt met bovenstaande aannames, pas de implementatie aan de officiële actuele documentatie aan in plaats van een fictieve API te gebruiken.
