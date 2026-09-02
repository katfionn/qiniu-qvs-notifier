# Qiniu QVS Notifier

[简体中文](../README.md) | [English](README.en.md) | [Español](README.es.md) | [Français](README.fr.md)

Surveillance des appareils Qiniu QVS avec alertes lors des changements d’état via DingTalk ou un autre webhook. Le tableau de bord Web et le moniteur d’arrière-plan partagent le même moteur de surveillance, la configuration et le stockage SQLite.

## Installation

### Docker : Web uniquement

Docker fournit uniquement le service Web ; il ne contient ni TUI interactive ni choix de mode de service.

```bash
docker compose up -d --build
```

Ouvrez `http://localhost:8000`. Le répertoire monté `./config` conserve les paramètres et les appareils. `restart: always` relance le service après une panne ou le redémarrage de l’hôte.

### Code source : installateur et gestionnaire TUI

Utilisez Python 3.9 ou une version ultérieure :

```bash
python install.py
```

Le point d’entrée vérifie les dépendances et peut installer `requirements.txt`, puis ouvre la TUI. Choisissez un mode :

- **Service Web** : lance le tableau de bord et le moniteur intégré sur `http://127.0.0.1:8000`.
- **Service TUI/moniteur** : lance uniquement le moniteur non interactif en arrière-plan. La TUI reste un outil de gestion au premier plan.

La TUI permet l’installation, l’état, le démarrage, l’arrêt, le redémarrage, la commande de journaux, la configuration, le choix de langue et la désinstallation. Les services existants sont gérés sans être dupliqués.

## Services natifs et désinstallation

Sous Linux, l’installateur crée une unité systemd dynamique avec `WorkingDirectory`, `ExecStart`, `Restart=on-failure` et `systemctl enable` ; utilisez `sudo` pour modifier les services.

Sous Windows, pywin32 `ServiceFramework` enregistre un véritable service Windows. Les droits administrateur sont requis et la stratégie de récupération redémarre les services en échec.

Choisissez **Uninstall Qiniu QVS Notifier** dans la TUI. Après deux confirmations, le service natif et le démarrage automatique sont supprimés, puis vous pouvez conserver ou supprimer `config/` (identifiants et données des appareils).

## Langues

Ce README est disponible en chinois simplifié, anglais, espagnol et français ; le chinois est la langue par défaut.

L’application fournit actuellement le chinois simplifié (`zh-CN`) et l’anglais (`en-US`) pour l’installateur, la TUI, les messages de service/API et l’interface Web. Le choix est enregistré dans `config/settings.yaml`.

## Développement

Utilisez `python run_web.py --reload` uniquement pour le développement Web local. Les services de production et Docker n’utilisent pas le mode reload.
