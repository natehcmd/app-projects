import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { authenticate } from '@google-cloud/local-auth';
import { google } from 'googleapis';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const CREDENTIALS_PATH = path.join(PROJECT_ROOT, 'credentials.json');
const TOKEN_PATH = path.join(PROJECT_ROOT, 'token.json');

const SCOPES = [
  'https://www.googleapis.com/auth/gmail.modify',
  'https://www.googleapis.com/auth/gmail.labels'
];

async function main() {
  if (!fs.existsSync(CREDENTIALS_PATH)) {
    console.error('Missing credentials.json in project root.');
    process.exit(1);
  }
  console.log('Starting OAuth flow — sign in as np.howard9@gmail.com when prompted...');
  const auth = await authenticate({ scopes: SCOPES, keyfilePath: CREDENTIALS_PATH });
  const token = auth.credentials;
  fs.writeFileSync(TOKEN_PATH, JSON.stringify(token, null, 2));
  console.log('✅ Token saved to', TOKEN_PATH);
  const gmail = google.gmail({ version: 'v1', auth });
  const profile = await gmail.users.getProfile({ userId: 'me' });
  console.log('✅ Connected as:', profile.data.emailAddress);
}

main().catch(console.error);
