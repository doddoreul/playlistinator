# Agent

## Règles pour l'agent (HAUTE PRIORITÉ)

- **Jamais de commit ni de push sans une demande explicite de l'utilisateur à chaque fois.**
  Une demande de commit à un moment donné ne constitue PAS une autorisation permanente.
  Chaque commit/push doit être précédé d'une demande claire et ponctuelle de l'utilisateur.
- Ne jamais utiliser de services payants de GitHub sauf demande explicite de l'utilisateur.
- En cas de doute, demander avant d'agir. Ne jamais supposer une autorisation.
- **Ne jamais nettoyer/supprimer/renommer/modifier les fichiers dans `media/` ni la base `data/playlistinator.db` lors d'un rebuild ou de tests.** Les données utilisateur sont précieuses. Aucune modification de `media/` sous aucun prétexte.
- **Ne jamais désactiver/déplacer les plugins de `plugins/` vers `plugins_available/`.** Les plugins activés doivent rester actifs.

## Règles secondaires

- (ajouter ici d'autres contraintes si nécessaire)