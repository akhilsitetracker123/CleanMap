# CleanMap — Online Login + Cloud Storage Setup

This guide turns CleanMap into an **online app** with:

- **Username / password login**
- **Cloud file storage** (uploads, lookup files, field definitions, cleansed outputs)
- Access from **any browser, anywhere**

CleanMap uses:

| Piece | Service | Cost |
|-------|---------|------|
| App hosting | [Streamlit Community Cloud](https://share.streamlit.io) | Free tier |
| Login | Built-in (`streamlit-authenticator`) | Free |
| File storage | **Bitbucket** repo *or* [Supabase Storage](https://supabase.com) | Per your org |

Set `provider = "bitbucket"` or `provider = "supabase"` in secrets (see below).

---

## Option A — Bitbucket cloud storage (recommended for Sitetraker)

Use a **separate repository** for migration files (e.g. `cleanmap-data`), **not** the application source repo `cleanmap`. Each upload creates a Git commit under `cleanmap-files/{username}/...`.

### A1. Create or pick a Bitbucket repo

1. [Bitbucket](https://bitbucket.org) → workspace **sitetraker** (or yours).
2. Create repo **`cleanmap-data`** (private).
3. Default branch **`main`** is fine.

### A2. Create a Bitbucket API token (not your login password)

Your normal Bitbucket **account password will not work** with the REST API.

**API tokens are not under “Bitbucket personal settings”.** They live on your **Atlassian account**:

1. In Bitbucket, click your **avatar** (top-right) → **Account settings** (opens Atlassian account), **or** go directly to [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Open the **Security** tab → **Create and manage API tokens** → **Create API token with scopes**.
3. Name it (e.g. `cleanmap-cloud`), set expiry, choose app **Bitbucket**.
4. Scopes (minimum for CleanMap file storage), scoped to workspace **sitetraker** when asked.

   You must tick these **exact** repository scopes (under Bitbucket → Repositories):

   | Scope | Purpose |
   |-------|---------|
   | `read:repository:bitbucket` | List/download files |
   | `write:repository:bitbucket` | Upload/delete files |

   **Admin scopes alone do not work** (`admin:repository`, `admin:workspace`, `delete:*`, etc. do not satisfy `read:repository:bitbucket`). If verify returns HTTP 403 with “lack privilege scopes”, create a **new** token with the two scopes above.
5. Copy the token once (you cannot view it again).

If you **do not see** “Create and manage API tokens”, your org may restrict tokens — ask your **Atlassian/Bitbucket admin** to allow user API tokens or provision one for `cleanmap-data`.

**Legacy App passwords** (only if still listed): [bitbucket.org/account/settings/app-passwords](https://bitbucket.org/account/settings/app-passwords/) — use Bitbucket **username** (from [Bitbucket account settings](https://bitbucket.org/account/settings/)), not email, plus the app password.

### A3. Secrets (Streamlit Cloud or `.streamlit/secrets.toml`)

```toml
[cloud]
enabled = true
provider = "bitbucket"
bitbucket_workspace = "sitetraker"
bitbucket_repo = "cleanmap-data"
bitbucket_branch = "main"
bitbucket_root = "cleanmap-files"
bitbucket_username = "you@yourcompany.com"
bitbucket_app_password = "paste_api_token_here"
```

For API tokens: **username = Atlassian email**, **bitbucket_app_password = the token** (the field name is historical).

Skip Supabase keys when using Bitbucket.

---

## Option B — Supabase cloud storage

## Step 1 — Create Supabase project (cloud storage)

1. Go to [supabase.com](https://supabase.com) and create a free account.
2. **New project** → pick a name and password → wait for the project to finish provisioning.
3. Open **Storage** → **New bucket**:
   - Name: `cleanmap-files`
   - **Private** bucket (recommended)
4. Open **Project Settings → API** and copy:
   - **Project URL** → `supabase_url`
   - **service_role** key → `supabase_key` (keep secret — server-side only)

---

## Step 2 — Configure login + cloud secrets

Copy the example file:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
[auth]
cookie_name = "cleanmap_auth"
cookie_key = "use-a-long-random-string-here"
cookie_expiry_days = 30

[auth.credentials.usernames.admin]
email = "admin@yourcompany.com"
name = "admin"
password = "YourSecurePassword123"

[cloud]
enabled = true
supabase_url = "https://YOUR_PROJECT.supabase.co"
supabase_key = "YOUR_SERVICE_ROLE_KEY"
bucket = "cleanmap-files"
```

### Add more users

Duplicate the `[auth.credentials.usernames.admin]` block with a new username:

```toml
[auth.credentials.usernames.analyst]
email = "analyst@yourcompany.com"
name = "Migration Analyst"
password = "AnotherSecurePassword456"
```

Passwords can be plain text in secrets — they are hashed automatically on first login.

Optional — pre-hash a password:

```bash
python generate_auth_hash.py
```

---

## Step 3 — Test locally

```bash
cd excel-validator
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

You should see a **Sign in** page. After login:

- Uploaded files are saved to Supabase under `{username}/uploads/`
- Cleansed outputs go to `{username}/outputs/`
- Workflow Steps 1–4 use **upload from your computer** only (no loading files from cloud in the workflow).
- Sidebar **My cloud files** lists uploads and exports automatically (download or delete only — no separate cloud upload control).

---

## Step 4 — Deploy online (Streamlit Cloud)

1. Push code to **GitHub** (do not commit `secrets.toml` or real Excel data).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your repo, branch `main`, main file `app.py`.
4. Open **Advanced settings → Secrets** and paste the same content as `.streamlit/secrets.toml`.
5. Deploy → share the URL with your team (e.g. `https://cleanmap-xxx.streamlit.app`).

Each team member signs in with their username/password. Files are stored per user in the cloud bucket.

---

## What gets saved to the cloud

| Folder | Contents |
|--------|----------|
| `{user}/uploads/` | Main Excel files you upload |
| `{user}/lookups/` | Lookup reference files |
| `{user}/field_definitions/` | Object field definition files |
| `{user}/outputs/` | Cleansed Excel after validation |

---

## Security notes

- Use the **service_role** key only in Streamlit secrets (never in frontend code or GitHub).
- Migration Excel may contain sensitive data — confirm with IT before using a public cloud.
- For stricter control, deploy on a **company VM** instead of Streamlit Cloud and restrict access by VPN.
- Rotate passwords and the Supabase service key if they are ever exposed.

---

## Local mode (no login)

If `secrets.toml` is missing or has no `[auth]` section, the app offers **Continue without login (local only)** — same behavior as before, with no cloud storage.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Login page but credentials fail | Check username spelling and password in secrets |
| "Could not save to cloud" | Verify Supabase URL, service key, and bucket name |
| Bucket upload 403 | Use **service_role** key, not anon key |
| Files not listed | Confirm `[cloud] enabled = true` |
| App works locally but not online | Add secrets in Streamlit Cloud dashboard |
