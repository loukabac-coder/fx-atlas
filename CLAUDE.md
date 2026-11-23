# FX Atlas — règles du projet

Site de suivi des taux directeurs, de l'inflation et des devises (préparation d'entretiens en salle des marchés).
Propriétaire : Louka (pas développeur). Toujours répondre en français, simplement.

## Règles non négociables sur les données
1. **Zéro donnée inventée.** Chaque chiffre vient d'une source officielle ou reconnue (banques centrales, BIS, BCE, OCDE, instituts statistiques). Introuvable = `n/d`. Jamais de valeur de mémoire.
2. **Chaque donnée affichée porte sa source et la date de la valeur** (pas seulement la date du robot). Valeur ancienne = signalée (« ancienne valeur »).
3. **Tout est automatique, tous les jours** : taux, inflation, change, réunions, dirigeants. Aucun chiffre codé en dur dans le site (`docs/`). Seule exception assumée : la cible d'inflation est écrite dans `config/countries.json`, mais le robot vérifie chaque jour qu'elle figure sur la page officielle (ou la lit directement, ex. Hongrie) ; sinon elle passe « à vérifier ».
4. **Validation avant publication** (`robot/validate.py`) : bornes + saut anormal. Une valeur douteuse n'écrase jamais une bonne : la dernière valeur validée est gardée et marquée « pas à jour » avec sa date. Un saut est accepté seulement si la source le confirme au passage suivant.
5. **Un pays qui plante ne fait jamais planter les autres.** Journal lisible (`docs/data/journal.md`, `log.json`, résumé GitHub Actions). Le workflow échoue (rouge) si > 20 % des données essentielles manquent.
6. **Identifiants de séries vérifiés en interrogeant réellement la source.** En cas de doute : le dire, ne pas deviner.
7. **Dirigeants** : nom pris dans Wikidata, affiché seulement s'il est retrouvé sur une page officielle de la banque centrale (`governor_check`). Sinon `n/d`.

## Architecture
- `config/countries.json` : liste des pays (identifiants de séries, pages officielles). **Ajouter un pays = ajouter un bloc ici** (code BIS, pays ISO3 pour la carte, devise, code OCDE, QID Wikidata de la banque, cible + page de contrôle, lecteur de calendrier).
- `robot/` : Python (requests, BeautifulSoup, pypdf).
  - `update.py` : programme principal → écrit `docs/data/{atlas,history,fx,log,state}.json` et `journal.md`.
  - `sources.py` : BIS (WS_CBPOL, WS_LONG_CPI), BCE (EXR, FM DFR), Banque du Canada (Valet V39079), Banque d'Angleterre (IADB IUDBEDR), BCB (SGS 432), Fed de New York (fourchette), OCDE (DF_FINMARK IRLT), Wikidata.
  - `calendars.py` : un lecteur par banque centrale (dates d'annonce des décisions).
  - `validate.py` : contrôles de plausibilité.
  - `probe.py` : outil de dev (branche `probe`) qui télécharge les réponses brutes des sources.
- `docs/` : site statique publié par GitHub Pages (globe.gl, Chart.js, polices locales). Aucun chiffre en dur.
- `.github/workflows/daily.yml` : robot 2×/jour + bouton « Run workflow ».
- `tests/` : `python -m unittest discover -s tests` (sans réseau, pages officielles enregistrées).

## Contraintes
- 100 % gratuit. Aucune clé secrète dans le code (aucune n'est nécessaire aujourd'hui).
- L'environnement de développement de Claude ne joint pas les sites de données : tester le robot via GitHub Actions sur la branche `dev`, jamais directement sur `main`.
- FRED bloque les serveurs GitHub (délais d'attente) : ne pas l'utiliser.
