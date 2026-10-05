import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import qrcode from "qrcode-terminal";
import pino from "pino";

const API_URL = process.env.BRIDGE_API_URL || "http://localhost:8000/bridge/message";

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState("auth_info");
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger: pino({ level: "silent" }),
    printQRInTerminal: false,
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\nScan this QR code with WhatsApp on your phone:\n");
      qrcode.generate(qr, { small: true });
    }

    if (connection === "open") {
      console.log("\n✅ Connected to WhatsApp! The agent is now live.\n");
    }

    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      console.log("Connection closed, status:", statusCode);
      if (statusCode !== DisconnectReason.loggedOut) {
        start(); // reconnect
      } else {
        console.log("Logged out. Delete the auth_info folder and run again to re-scan.");
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      try {
        if (msg.key.fromMe) continue;
        if (!msg.key.remoteJid) continue;
        // Ignore groups and broadcast/status
        if (msg.key.remoteJid.endsWith("@g.us")) continue;
        if (msg.key.remoteJid === "status@broadcast") continue;

        const text =
          msg.message?.conversation ||
          msg.message?.extendedTextMessage?.text ||
          msg.message?.imageMessage?.caption ||
          "";

        if (!text.trim()) continue;

        const phone = msg.key.remoteJid.split("@")[0].split(":")[0];
        console.log(`📩 [${phone}]: ${text}`);

        let reply = "Sorry, I couldn't process that right now. Please try again.";
        try {
          const res = await fetch(API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phone, text }),
          });
          const data = await res.json();
          if (data.response) reply = data.response;
        } catch (e) {
          console.log("Failed to reach FastAPI server:", e.message);
        }

        await sock.sendMessage(msg.key.remoteJid, { text: reply });
        console.log(`🤖 Replied to ${phone}`);
      } catch (e) {
        console.log("Message handling error:", e.message);
      }
    }
  });
}

start();
