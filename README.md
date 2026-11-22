# FX Atlas — site publiable et robot source

Cette livraison contient réellement l’interface, le robot Python, ses tests et le workflow GitHub. Ce n’est PAS l’archive d’aperçu précédente.

**Statut honnête :** version fonctionnelle à couverture partielle. Le transport HTTP du robot et la publication GitHub n’ont pas pu être validés depuis cet environnement (résolution DNS bloquée). Le premier lancement distant reste nécessaire. Aucune affirmation « entièrement automatique et vérifiée » avant ce contrôle.

## Voir le site immédiatement
Ouvrir `OUVRIR-LE-SITE.html` : copie locale autonome, données figées et signalées. Le vrai site déployé lit `web/data/latest.json`, actualisé par le robot.

## Mettre en ligne
Lire `DEMARRER-ICI.md`. Un dépôt GitHub public suffit ; aucune clé API n’est requise. Le dossier `.github` doit être présent. Une copie visible `ACTIVER-AUTOMATISATION.yml` permet de le recréer si votre outil de téléversement masque les dossiers commençant par un point.

## Exécuter et vérifier localement
```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
npm test
npm run build
npm start
```
Le serveur local s’ouvre à http://127.0.0.1:4173. Node 22 et Python 3.12+ sont requis. Aucun `npm install` n’est nécessaire : interface JavaScript/WebGL native, sans dépendance réseau.

Collecte réelle : `python -m collector.run --output web/data`.
Rejeu hors ligne uniquement : `python -m collector.run --offline-fixtures tests/fixtures --now 2026-11-22T22:00:00Z --output artifacts/replay`.
Tests navigateur facultatifs : installer `requirements-browser.txt`, exécuter `playwright install chromium`, puis `python scripts/browser_test.py` pendant que `npm start` tourne.

## Périmètre livré
Globe WebGL orientable et zoomable, projection carte, fiches pays, classement triable et filtrable, conversion FX, performances par période quand l’historique est suffisant, comparaison macro, calendrier et panneau de qualité. Les pays sans connecteur affichent n/d. Le globe dispose d’un rendu de secours Canvas.

## Écart technique au plan initial
Pour rendre la livraison autonome et sans installation front-end, l’interface utilise JavaScript natif, un globe WebGL local et des graphiques SVG plutôt que React/Three.js/ECharts. Le robot reste en Python et la cible est GitHub Pages. Cette simplification ne signifie pas que la couverture de données initialement demandée est complète.

## Données et limites
Lire `docs/SOURCES.md`, `docs/VERIFICATION.md` et `docs/LIMITES.md`. Les fixtures sont normalisées à partir des relevés web, pas des captures HTML brutes. Leur réussite ne prouve pas le fonctionnement du scraping en production. Elles ne sont jamais utilisées par le workflow quotidien.
