/**
 * whatsapp_service.js
 *
 * A small Express server that wraps whatsapp-web.js.
 * Python calls this service to send WhatsApp messages from your number to Alba.
 *
 * First run: scan the QR code that appears in the terminal with your WhatsApp.
 * Subsequent runs: session is restored from .wwebjs_auth/ automatically.
 *
 * Endpoints:
 *   POST /send  { chatId: "9715XXXXXXXX@c.us", message: "Hello" }
 *   GET  /health
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const express = require("express");

const app = express();
app.use(express.json());

const PORT = 3000;
let clientReady = false;

// ---------------------------------------------------------------------------
// WhatsApp client setup
// ---------------------------------------------------------------------------

const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: ".wwebjs_auth",
  }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

client.on("qr", (qr) => {
  console.log("\n📱 Scan this QR code with your WhatsApp:");
  qrcode.generate(qr, { small: true });
  console.log("\nWaiting for scan...\n");
});

client.on("authenticated", () => {
  console.log("✅ WhatsApp authenticated. Session saved.");
});

client.on("auth_failure", (msg) => {
  console.error("❌ Authentication failed:", msg);
  console.error("Delete .wwebjs_auth/ and restart to re-scan QR code.");
  process.exit(1);
});

client.on("ready", () => {
  clientReady = true;
  console.log("✅ WhatsApp client ready. Service is accepting requests on port", PORT);
});

client.on("disconnected", (reason) => {
  clientReady = false;
  console.warn("⚠️  WhatsApp disconnected:", reason);
  console.warn("Attempting to reinitialize...");
  client.initialize();
});

client.initialize();

// ---------------------------------------------------------------------------
// Express routes
// ---------------------------------------------------------------------------

app.get("/health", (req, res) => {
  res.json({
    status: clientReady ? "ready" : "not_ready",
    message: clientReady
      ? "WhatsApp client is ready to send messages"
      : "WhatsApp client is not ready yet. Wait for QR scan or session restore.",
  });
});

app.post("/send", async (req, res) => {
  const { chatId, message } = req.body;

  if (!chatId || !message) {
    return res.status(400).json({ error: "chatId and message are required" });
  }

  if (!clientReady) {
    return res.status(503).json({
      error: "WhatsApp client not ready. Scan QR code first.",
    });
  }

  try {
    await client.sendMessage(chatId, message);
    console.log(`📤 Sent to ${chatId}: "${message.substring(0, 60)}..."`);
    res.json({ success: true, chatId, message });
  } catch (err) {
    console.error("❌ Failed to send message:", err.message);
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------

app.listen(PORT, () => {
  console.log(`\n🚀 WhatsApp service listening on http://localhost:${PORT}`);
  console.log("Waiting for WhatsApp client to initialize...\n");
});
