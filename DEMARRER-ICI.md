# Mettre FX Atlas en ligne

## 1. Extraire cette archive
Le dossier `fx-atlas` doit contenir `web`, `collector`, `scripts`, `tests`, `package.json`, `requirements.txt` et `.github`. Ils sont réellement inclus dans cette archive.
Pour regarder immédiatement : ouvrir `OUVRIR-LE-SITE.html` (copie locale figée).

## 2. Créer un nouveau dépôt public
Sur GitHub, cliquer sur `+` en haut à droite → `New repository`. Nom : `fx-atlas`. Choisir `Public`, cocher `Add a README file`, puis `Create repository`. La branche doit être nommée `main`. Ne pas remplacer votre dépôt heatmap existant.

## 3. Envoyer le projet
Dans le dépôt : `Add file` → `Upload files`. Déposer LE CONTENU du dossier `fx-atlas`, pas le ZIP, pas le dossier parent. Envoyer les dossiers `web`, `collector`, `scripts`, `tests`, `evidence`, `docs` et les fichiers de la racine. Cliquer `Commit changes`.
Ne pas déposer les fichiers à l’intérieur d’un sous-dossier `fx-atlas` du dépôt : `package.json` doit se voir directement dans l’onglet Code.

**Le dossier caché .github est important.** S’il apparaît dans votre explorateur, déposer également ce dossier. Sur Windows : Affichage → Afficher → Éléments masqués. Sur macOS : Cmd + Maj + point.
S’il ne se téléverse pas : ouvrir le fichier visible `ACTIVER-AUTOMATISATION.yml`, copier tout son texte ; sur GitHub faire `Add file` → `Create new file`, donner EXACTEMENT ce nom : `.github/workflows/update.yml`, coller le texte, puis `Commit changes`. Ne pas entourer le texte de guillemets ni de balises Markdown.

## 4. Activer l’hébergement
Dans le dépôt : `Settings` → `Pages` → `Build and deployment` → `Source` → sélectionner `GitHub Actions`.
Si le premier lancement automatique échoue avant cette activation, ce n’est pas une raison de remettre les fichiers : relancer après avoir choisi cette option.

## 5. Lancer et voir le lien
Onglet `Actions` → `Actualiser et publier FX Atlas` → `Run workflow` → branche `main` → bouton vert `Run workflow`.
Le job `deploy` affiche le lien public. `Settings` → `Pages` affiche aussi l’adresse après publication. Elle est normalement de la forme `https://VOTRE-PSEUDO.github.io/fx-atlas/` : ceci est un exemple, pas un lien de déploiement déjà réalisé.

**Lire le résultat :** une collecte critique en erreur laisse le workflow rouge, même si la publication du site avec les dernières valeurs conservées a réussi. Le panneau « Qualité des données » indique les sources en panne. La réussite de la publication ne valide pas toutes les sources.

## Ensuite
Deux programmations quotidiennes UTC (07:23 et 18:43) sont incluses ; GitHub peut les retarder, et les désactive après 60 jours sans activité sur un dépôt public. Les commits réels des rapports maintiennent normalement l’activité. Cela ne constitue pas une garantie de disponibilité.
Aucune mise à jour quotidienne manuelle n’est prévue ; les changements de structure des sources peuvent nécessiter une correction du robot.

## En cas de refus de git push du robot
Settings → Actions → General → Workflow permissions → Read and write permissions → Save, si cette option est autorisée par votre compte. Une règle de protection de branche ou d’organisation peut nécessiter une exception pour le robot ; elle ne peut pas être contournée par cette livraison.

Documentation officielle :
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
