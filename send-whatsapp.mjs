import { makeWASocket, useMultiFileAuthState } from '@whiskeysockets/baileys';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.join(__dirname, 'baileys-auth');
const jid = process.argv[2];
const message = process.argv[3];

if (!jid || !message) {
  console.error('Usage: node send-whatsapp.mjs "<jid>" "<message>"');
  process.exit(1);
}

async function send() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const sock = makeWASocket({ auth: state, syncFullHistory: false });
  sock.ev.on('creds.update', saveCreds);

  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Connection timeout')), 15000);
    sock.ev.on('connection.update', async (update) => {
      const { connection } = update;
      if (connection === 'open') {
        clearTimeout(timer);
        try {
          await sock.sendMessage(jid, { text: message });
          console.log('OK');
        } catch (e) {
          console.error(`SEND_ERROR: ${e.message}`);
        }
        process.exit(0);
      }
      if (connection === 'close') {
        clearTimeout(timer);
        reject(new Error('Connection closed before open'));
      }
    });
  });
}

send().catch(e => {
  console.error(`ERROR: ${e.message}`);
  process.exit(1);
});