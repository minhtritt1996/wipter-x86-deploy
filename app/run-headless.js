#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const http = require('http');

// Set environment variables for Wipter main.js
process.env.NODE_ENV = 'production';
process.type = 'browser';
process.resourcesPath = path.resolve(__dirname, '../resources');
process.env.DIST_ELECTRON = path.resolve(__dirname, 'dist-electron');
process.env.DIST = path.resolve(__dirname, 'dist');
process.env.PUBLIC = path.resolve(__dirname, 'dist');
process.env.WIPTER_USER_DATA = process.env.WIPTER_USER_DATA || '/root/.config/wipter-app';

const electron = require('./mock-electron.js');

process.on('uncaughtException', (err) => {
  console.error('[Headless] Handled uncaughtException:', err?.message || err);
});
process.on('unhandledRejection', (reason) => {
  console.error('[Headless] Handled unhandledRejection:', reason);
});

console.log('====================================================');
console.log('   WIPTER HEADLESS NODE (ALPINE LINUX OPTIMIZED)   ');
console.log('====================================================');

let mainWin = null;
let currentDeviceId = null;
let currentSessionId = null;
let isRegistered = false;

const currentStatus = {
  status: 'Connecting...',
  ipType: 'Detecting...',
  location: 'Detecting...',
  traffic: '0.00 MB',
  totalEarned: 'USD 0.00',
  speedUp: '0 B/s',
  speedDown: '0 B/s',
  updatedAt: new Date().toISOString()
};

function saveStatus() {
  try {
    currentStatus.updatedAt = new Date().toISOString();
    fs.writeFileSync(
      path.join(process.env.WIPTER_USER_DATA, 'status.json'),
      JSON.stringify(currentStatus, null, 2)
    );
  } catch (e) {}
}

function getAccessToken() {
  try {
    const credPath = path.join(process.env.WIPTER_USER_DATA, 'secure-credentials.json');
    if (fs.existsSync(credPath)) {
      const creds = JSON.parse(fs.readFileSync(credPath, 'utf8'));
      const val = creds?.com?.wipter?.auth?.['production:root'];
      if (val && val.startsWith('plain:')) {
        return Buffer.from(val.slice(6), 'base64').toString('utf8');
      }
    }
  } catch (e) {}
  return null;
}

async function refreshEarningsAndTraffic() {
  const token = getAccessToken();
  if (!token) return;
  try {
    const earnings = await electron.ipcMain.invoke('GET_EARNINGS', token);
    if (earnings) {
      const bytes = earnings.traffic_in_bytes || 0;
      const cents = earnings.amount_in_cents || 0;
      currentStatus.traffic = `${(bytes / 1024 / 1024).toFixed(2)} MB`;
      currentStatus.totalEarned = `USD ${(cents / 100).toFixed(2)}`;
      console.log(`[Headless] Account Balance Synced: Traffic = ${currentStatus.traffic} | Earnings = ${currentStatus.totalEarned}`);
      saveStatus();
    }
  } catch (err) {
    console.error('[Headless] Error refreshing earnings:', err?.message || err);
  }
}

// Lightweight HTTP status server on port 9222 (replaces Chromium DevTools)
const statusServer = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(currentStatus, null, 2));
});
const statusPort = parseInt(process.env.STATUS_PORT || '9222');
statusServer.listen(statusPort, '0.0.0.0', () => {
  console.log(`[Headless] Realtime status API listening on 0.0.0.0:${statusPort}`);
});

electron._bus.on('window-created', (win) => {
  mainWin = win;
  electron._bus.currentWindow = win;
  console.log('[Headless] Virtual window initialized.');
});

electron._bus.on('ipc-send', async (channel, ...args) => {
  if (channel === 'WS:INITIALIZED') {
    console.log('[Headless] STOMP WebSocket Initialized! Registering device...');
    try {
      const devInfoResp = await electron.ipcMain.invoke('DEVICE_INFO');
      const dev = devInfoResp ? devInfoResp.device : null;
      if (!dev) {
        console.error('[Headless] Failed to get device info!');
        return;
      }
      console.log(`[Headless] Device ID: ${dev.deviceId}`);
      console.log(`[Headless] Device Platform: ${dev.devicePlatform} (${dev.platformVersion})`);

      let evidence = null;
      try {
        evidence = await electron.ipcMain.invoke('ENVIRONMENT_EVIDENCE');
      } catch (err) {}
      console.log('[Headless] Publishing registration with evidence...');

      // Send registration payload to /app/topic/registration
      await electron.ipcMain.invoke('WS:SEND', '/app/topic/registration', {
        ...dev,
        environmentEvidence: evidence
      }, {});

      // Send session options
      await electron.ipcMain.invoke('WS:SEND', '/app/topic/session-options', {
        sendStats: true
      }, {});

      isRegistered = true;
    } catch (err) {
      console.error('[Headless] Error during registration:', err);
    }
  } else if (channel === 'WS:CONNECTED') {
    console.log('[Headless] Status: Online 🟢 (Connected to Wipter network)');
    currentStatus.status = 'Online 🟢';
    saveStatus();
    refreshEarningsAndTraffic();
    try {
      await electron.ipcMain.invoke('UPDATE_APP_CONNECTED_STATE', 'Online');
    } catch (e) {}
  } else if (channel === 'WS:DISCONNECTED') {
    console.log('[Headless] Status: Disconnected 🔴', args);
    currentStatus.status = 'Disconnected 🔴';
    saveStatus();
    try {
      await electron.ipcMain.invoke('UPDATE_APP_CONNECTED_STATE', 'Connecting');
    } catch (e) {}
  } else if (channel === 'GET_LOCATION') {
    const loc = args[0];
    if (loc) {
      const city = loc.location?.city || '';
      const region = loc.location?.region || '';
      const country = loc.location?.country_code || '';
      currentStatus.location = [city, region, country].filter(Boolean).join(', ');
      currentStatus.ipType = loc.ip_type === 'RESIDENTIAL' ? 'Residential Proxy IP' : (loc.ip_type || 'Unknown');
      console.log(`[Headless] Location: ${currentStatus.location}`);
      console.log(`[Headless] IP Type: ${currentStatus.ipType}`);
      saveStatus();
    }
  } else if (channel === 'WS:GET_HOME_METRICS') {
    const metrics = args[0];
    if (metrics) {
      if (metrics.trafficUpSpeed !== undefined) currentStatus.speedUp = `${metrics.trafficUpSpeed} B/s`;
      if (metrics.trafficDownSpeed !== undefined) currentStatus.speedDown = `${metrics.trafficDownSpeed} B/s`;
      saveStatus();
    }
  } else if (channel === 'HTTPS_RESPONSE') {
    const [requestId, payload] = args;
    try {
      await electron.ipcMain.invoke('WS:SEND', `/app/topic/tunnel-response/${requestId}`, payload, {});
    } catch (e) {
      console.error('[Headless] Failed to send HTTPS_RESPONSE:', e);
    }
  } else if (channel === 'PROXY_RESPONSE_ERROR') {
    const [requestId, error] = args;
    try {
      await electron.ipcMain.invoke('WS:SEND', `/app/topic/proxy-request-error/${requestId}`, error, {});
    } catch (e) {
      console.error('[Headless] Failed to send PROXY_RESPONSE_ERROR:', e);
    }
  }
});

// Periodic session stats & earnings refresh
setInterval(async () => {
  if (isRegistered) {
    try {
      await electron.ipcMain.invoke('WS:SEND', '/app/topic/session-options', {
        sendStats: true
      }, {});
      await refreshEarningsAndTraffic();
    } catch (e) {}
  }
}, 20000);

// Load main.js
require('./dist-electron/main/main.js');

// After main.js sets up its handlers, trigger connection
setTimeout(async () => {
  try {
    const cfgFile = path.join(process.env.WIPTER_USER_DATA, 'config.json');
    if (fs.existsSync(cfgFile)) {
      const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
      currentDeviceId = cfg.socketId;
    }
    if (!currentDeviceId) {
      currentDeviceId = crypto.randomUUID();
      fs.mkdirSync(process.env.WIPTER_USER_DATA, { recursive: true });
      fs.writeFileSync(cfgFile, JSON.stringify({ socketId: currentDeviceId }));
    }
    currentSessionId = crypto.randomUUID();

    console.log(`[Headless] Initiating connection: deviceId=${currentDeviceId}, sessionId=${currentSessionId}`);
    await electron.ipcMain.invoke('WS:CONNECT', currentDeviceId, currentSessionId);
  } catch (err) {
    console.error('[Headless] Failed to start connection:', err);
  }
}, 2000);
