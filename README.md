# FX Atlas

Globe des taux directeurs, de l'inflation et des devises de 21 grandes banques centrales. Les données viennent de sources officielles et sont mises à jour automatiquement chaque jour.

**Site :** https://loukabac-coder.github.io/fx-atlas/

## Ce que montre le site
- **Globe 3D** (et carte plate) colorié selon la métrique choisie : taux directeur, taux réel, inflation, écart à la cible, variation du taux sur 12 mois, écart de taux face aux États-Unis, taux à 10 ans, performance de la devise face au dollar depuis le 1er janvier.
- **Fiche pays** (clic sur un pays) : dirigeant, taux et inflation avec leur date et leur source, cible d'inflation, dernière et prochaine réunion, graphique sur 3 ans, devise.
- **Calendrier** des réunions de toutes les banques centrales suivies.
- **Devises** : convertisseur et comparateur (1 jour, 1 semaine, 1 mois, depuis le 1er janvier, 1 an).
- **Classement** triable, avec export CSV.
- **Sources & qualité** : journal du robot, statut de chaque donnée.

## Mise à jour automatique
Le robot (`robot/update.py`) tourne sur GitHub Actions vers 6 h 17 (heure de Paris), puis en semaine après le fixing de la BCE. Pour le lancer à la main : onglet **Actions**, puis **Mise à jour quotidienne des données**, puis **Run workflow**.

Une valeur douteuse n'écrase jamais une bonne valeur. Le site garde alors la dernière valeur validée et la marque « pas à jour ». Le robot passe en rouge si plus de 20 % des données essentielles manquent.

## Sources
- BIS : taux directeurs, inflation.
- Sites des banques centrales : Canada, BCE, Angleterre, Brésil, Fed de New York, ainsi que les calendriers des réunions.
- BCE : taux de change.
- OCDE : taux à 10 ans.
- Wikidata : noms des dirigeants, affichés seulement s'ils sont confirmés sur le site officiel de la banque centrale.

Le détail des règles et de l'architecture est dans `CLAUDE.md`.
