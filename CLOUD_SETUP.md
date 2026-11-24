# CleanMap — Online login (Streamlit Cloud)

CleanMap on [Streamlit Community Cloud](https://share.streamlit.io) uses **username / password login** only.  
Files are **uploaded from your computer** in the browser and are **not** persisted to cloud storage.

## Secrets (Streamlit Cloud)

Paste into **App settings → Secrets**:

```toml
[auth]
cookie_name = "cleanmap_auth"
cookie_key = "replace-with-a-long-random-string"
cookie_expiry_days = 30

[auth.credentials.usernames.admin]
email = "admin@yourcompany.com"
name = "admin"
password = "admin123"
```

Use plain-text passwords in secrets for `streamlit-authenticator` (hashed on first login).  
Sign in with the **username** (`admin`), not the email.

## Remove old cloud secrets

If you previously added a `[cloud]` section or `supabase_*` / `bitbucket_*` keys, **delete those lines** from Streamlit secrets and **reboot** the app.

## Local run without login

If `[auth]` is missing locally, use **Continue without login (local only)** on the sign-in page.

## Deploy

- GitHub repo branch: **`cleanmap-v2`**
- Main file: **`app.py`**