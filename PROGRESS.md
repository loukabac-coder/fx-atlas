# Avancement FX Atlas

## Fait
- Robot quotidien (GitHub Actions) : taux directeurs (BIS + sources directes Canada, BCE, BoE, BCB ; fourchette Fed via la Fed de New York), inflation (BIS), taux 10 ans (OCDE), change (BCE), dirigeants (Wikidata confirmé sur page officielle), cibles (vérifiées sur page officielle), calendriers de 18 banques centrales.
- Contrôles : bornes, sauts confirmés au passage suivant, dates futures écartées, fraîcheur du taux jugée d'après les réunions, dernière bonne valeur gardée, journal.
- Site : globe 3D + carte plate, 8 métriques, fiche pays, calendrier, convertisseur/comparateur, classement + CSV, page qualité. Testé ordinateur + téléphone (dossier `captures/`).
- Tests sans réseau : `python -m unittest discover -s tests`.

## Reste à faire / idées
- Australie : brancher l'IPC mensuel de l'ABS (la BIS ne donne que le trimestriel, daté de juin 2026). Contrôle croisé du 23/11 : 4,3 % en sept. 2026 selon l'ABS.
- Calendriers non lisibles automatiquement : Pologne (anti-robot), Nouvelle-Zélande (403), réunions futures du Brésil.
- Dirigeants non confirmés automatiquement : Mexique, Brésil, Pologne, Inde, Corée, Indonésie, Nouvelle-Zélande (n/d affiché).
- Cibles « à vérifier » : Mexique, Brésil, Pologne, Nouvelle-Zélande (pages officielles illisibles par robot).
- Inflation BIS en retard de 1 à 2 mois : ajouter des sources nationales plus rapides pays par pays.

## Problèmes connus
- Voir `docs/data/journal.md` (mis à jour à chaque passage du robot).
