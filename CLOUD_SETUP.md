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
| File storage | [Supabase Storage](https://supabase.com) | Free tier (1 GB) |

---

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
name = "Admin User"
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
- Use **Load from cloud** in step 1 to reopen a previous upload
- Use **My cloud files** in the sidebar to download saved files

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
