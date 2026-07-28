# Google Cloud OAuth Setup

Step-by-step guide to create the credentials needed for Gmail Sorter.

## 1. Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Name it something like `gmail-sorter`
4. Click **Create**

## 2. Enable the Gmail API

1. In your project, go to **APIs & Services** → **Library**
2. Search for **Gmail API**
3. Click **Enable**

## 3. Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** user type → **Create**
3. Fill in:
   - App name: `Gmail Sorter`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue**
5. On Scopes page, click **Add or Remove Scopes** and add:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.labels`
6. Click **Save and Continue**
7. On Test Users page, click **Add Users** and add your Gmail address
8. Click **Save and Continue**

## 4. Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `Gmail Sorter Desktop`
5. Click **Create**
6. Click **Download JSON**
7. Rename the downloaded file to `credentials.json`
8. Move it to the gmail-sorter project root (next to `package.json`)

## 5. Authenticate

```bash
cd /path/to/gmail-sorter
node src/setup.js
```

A browser window opens. Sign in with the Gmail account you want to sort and grant access. You'll see:

```
✅ Token saved to token.json
✅ Connected as: you@gmail.com
```

## Troubleshooting

### "Access blocked: This app is not verified"
Click **Advanced** → **Go to Gmail Sorter (unsafe)**. This is expected for personal OAuth apps.

### "redirect_uri_mismatch"
Make sure you selected **Desktop app** (not Web application) when creating the OAuth client.

### Token expired
Re-run `node src/setup.js` to get a fresh token.

## Security Notes

- `credentials.json` and `token.json` should **never** be shared or committed to git
- Add both to your `.gitignore`
- The OAuth token grants full read/write access to your Gmail — treat it like a password
