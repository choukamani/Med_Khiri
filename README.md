# Cabinet Dr. Khiri — Backend RDV

Application FastAPI de prise de rendez-vous, branchee sur Google Calendar (Service Account) + envoi d'emails via SMTP Gmail.

- Frontend: `static/index.html`
- API: FastAPI / Uvicorn
- Calendar: Google Service Account (pas d'OAuth a renouveler)
- Emails: Gmail SMTP (App Password)

---

## 1. Pre-requis

- Docker installe sur le serveur de prod
- Un compte de service Google Cloud avec acces a Google Calendar
- Le calendrier Google partage avec l'email du service account (droits "Apporter des modifications")
- Un App Password Gmail (16 caracteres) pour l'envoi des emails

---

## 2. Fichiers necessaires en prod

Le repo Git ne contient PAS les secrets. Avant le build, il faut deposer manuellement a la racine du projet:

| Fichier | Description | Obligatoire |
|---|---|---|
| `meidcal-platform-80f8ef4be549.json` | Cle du Service Account Google (telechargee depuis GCP Console > IAM > Service Accounts > Keys) | OUI |

Les autres secrets (`SMTP_APP_PASSWORD`, `DOCTOR_EMAIL`, etc.) sont passes via `-e` au `docker run`, pas via fichier.

> Le fichier `.env` n'est PAS necessaire en prod si tu utilises les `-e` du `docker run`. Il sert uniquement en dev local.

---

## 3. Variables d'environnement

| Variable | Exemple | Description |
|---|---|---|
| `DOCTOR_EMAIL` | `khiribassem1@gmail.com` | Adresse email du medecin (recoit les notifs RDV) |
| `GOOGLE_CALENDAR_ID` | `khiribassem1@gmail.com` | ID du Google Calendar (souvent = email du proprietaire) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `meidcal-platform-80f8ef4be549.json` | Chemin (relatif a `/app`) vers la cle du service account |
| `SMTP_EMAIL` | `khiribassem1@gmail.com` | Adresse Gmail utilisee pour envoyer les confirmations |
| `SMTP_APP_PASSWORD` | `ibro ocrz mdxn huic` | App Password Gmail (16 caracteres avec espaces) |
| `PORT` | `8080` | Port d'ecoute interne du conteneur |
| `API_SECRET_KEY` | `un-secret-fort` | (Optionnel) Active les endpoints `/api/admin/*` (blocklist) |
| `FRONTEND_URL` | `https://rdv.drkhiri.tn` | (Optionnel) URL publique du frontend |

---

## 4. Deploiement Docker (production)

```bash
# 1. Cloner le repo
git clone <repo-url> drkhiri-app
cd drkhiri-app

# 2. Deposer la cle du service account a la racine
#    (transfert via scp/sftp depuis ta machine locale)
ls meidcal-platform-80f8ef4be549.json   # doit exister

# 3. Build de l'image
docker build -t drkhiri-app .

# 4. Lancer le conteneur
docker run -d --name drkhiri-app --restart unless-stopped \
  -p 8006:8080 \
  -e DOCTOR_EMAIL=khiribassem1@gmail.com \
  -e GOOGLE_CALENDAR_ID=khiribassem1@gmail.com \
  -e GOOGLE_SERVICE_ACCOUNT_FILE=meidcal-platform-80f8ef4be549.json \
  -e SMTP_EMAIL=khiribassem1@gmail.com \
  -e "SMTP_APP_PASSWORD=ibro ocrz mdxn huic" \
  -e PORT=8080 \
  drkhiri-app

# 5. Verifier
curl http://localhost:8006/health     # -> {"status":"ok"}
```

L'app est ensuite accessible sur **http://<serveur>:8006**.

### Mise a jour

```bash
git pull
docker build -t drkhiri-app .
docker stop drkhiri-app && docker rm drkhiri-app
# relancer la commande docker run du point 4
```

### Logs / debug

```bash
docker logs -f drkhiri-app
docker exec -it drkhiri-app sh
```

---

## 5. Lancement en local (dev, sans Docker)

```bash
# 1. Creer le venv et installer les deps
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# 2. Creer un fichier .env (copier .env.example) avec les vraies valeurs
cp .env.example .env
# Editer .env

# 3. Deposer aussi le JSON du service account a la racine

# 4. Lancer
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8006
```

Ouvrir http://localhost:8006

---

## 6. Configuration Google Calendar

Le medecin cree des evenements dans son calendrier avec le titre **`DISPO`** (insensible a la casse) et la plage horaire du creneau libre.

Exemple:
```
Titre: DISPO        Heure: 10:00 - 11:00
Titre: DISPO        Heure: 11:00 - 12:00
Titre: DISPO        Heure: 14:00 - 15:00
```

Quand un patient reserve via le site:
1. L'evenement `DISPO` est **supprime**
2. Un nouvel evenement `RDV - <Nom Patient>` est cree a sa place
3. Le medecin et le patient recoivent un email de confirmation

> Ne pas oublier de **partager le calendrier** avec l'email du service account (droits "Apporter des modifications a l'evenement"), sinon l'API renverra 403.

---

## 7. Endpoints principaux

| Methode | URL | Description |
|---|---|---|
| GET | `/` | Frontend (page de RDV) |
| GET | `/health` | Healthcheck |
| GET | `/api/slots/{YYYY-MM-DD}` | Creneaux dispos d'un jour |
| GET | `/api/slots/month/{year}/{month}` | Jours avec dispos sur un mois |
| POST | `/api/book` | Reserver un creneau |
| GET | `/api/admin/blocked` | (Admin) Liste des bloques — header `X-Admin-Token` |
| POST | `/api/admin/block` | (Admin) Bloquer un email/tel |
| POST | `/api/admin/unblock` | (Admin) Debloquer |

---

## 8. Securite — points d'attention

- La cle du service account (`meidcal-platform-*.json`) est **embarquee dans l'image Docker**. Ne pas pousser cette image sur un registre public.
- Pour activer les endpoints `/api/admin/*`, definir `API_SECRET_KEY` avec un secret fort. Sans ca, les routes admin renvoient 503.
- Mettre l'app derriere un reverse proxy (nginx/Caddy) avec HTTPS en prod.
- Les `App Password` Gmail peuvent etre revoques a tout moment depuis https://myaccount.google.com/apppasswords.
