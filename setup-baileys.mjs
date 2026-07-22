import { makeWASocket, useMultiFileAuthState, DisconnectReason } from '@whiskeysockets/baileys';
import path from 'path';
import fs from 'fs';
import QRCode from 'qrcode';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.join(__dirname, 'baileys-auth');
const QR_FILE = path.join(__dirname, 'wa-qr.png');

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  const sock = makeWASocket({
    auth: state,
    syncFullHistory: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr && !fs.existsSync(QR_FILE)) {
      await QRCode.toFile(QR_FILE, qr, { width: 400 });
      console.log(`QR saved to ${QR_FILE}. Open it and scan with WhatsApp.`);
      execSync(`open "${QR_FILE}"`);
    }

    if (connection === 'open') {
      console.log('\nConnected! Fetching groups...');
      const groups = await sock.groupFetchAllParticipating();
      Object.entries(groups).forEach(([id, g]) => {
        console.log(`  "${g.subject}" — JID: ${id} (${g.participants} members)`);
      });
      console.log('\nAuth saved to baileys-auth/');
      process.exit(0);
    }

    if (connection === 'close') {
      const reason = lastDisconnect?.error?.output?.statusCode;
      console.log(`Connection closed (reason: ${reason})`);
      if (reason === DisconnectReason.loggedOut) {
        console.log('Logged out — starting fresh next time');
        return;
      }
      // 515 = restart required (pairing was successful!)
      console.log('Reconnecting in 3s...');
      setTimeout(() => connectToWhatsApp(), 3000);
    }
  });
}

connectToWhatsApp().catch(e => {
  console.error(e);
  process.exit(1);
});