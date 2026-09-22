const EventEmitter = require('events');
const path = require('path');
const fs = require('fs');

const bus = new EventEmitter();
const ipcHandlers = new Map();
const ipcListeners = new Map();

class WebContents extends EventEmitter {
  constructor() {
    super();
  }
  send(channel, ...args) {
    bus.emit('ipc-send', channel, ...args);
    this.emit(channel, ...args);
  }
  isDestroyed() {
    return false;
  }
  openDevTools() {}
  setWindowOpenHandler() {
    return { action: 'deny' };
  }
}

const allWindows = [];

class BrowserWindow extends EventEmitter {
  constructor(opts = {}) {
    super();
    this.webContents = new WebContents();
    this._visible = false;
    allWindows.push(this);
    bus.emit('window-created', this);
  }
  loadURL() {}
  loadFile() {
    setTimeout(() => {
      this.webContents.emit('did-finish-load');
    }, 100);
  }
  setSize() {}
  setMaximumSize() {}
  show() {
    this._visible = true;
  }
  hide() {
    this._visible = false;
  }
  close() {
    const idx = allWindows.indexOf(this);
    if (idx !== -1) allWindows.splice(idx, 1);
  }
  isMinimized() {
    return false;
  }
  restore() {}
  isVisible() {
    return this._visible;
  }
  focus() {}
  isDestroyed() {
    return false;
  }
  static getAllWindows() {
    return allWindows;
  }
  static getFocusedWindow() {
    return allWindows[0] || null;
  }
  static fromId() {
    return allWindows[0] || null;
  }
  static fromWebContents(wc) {
    return allWindows.find(w => w.webContents === wc) || null;
  }
}

const app = new EventEmitter();
app.commandLine = {
  appendSwitch: () => {},
  hasSwitch: () => false,
  getSwitchValue: () => ''
};
app.whenReady = () => Promise.resolve();
app.isReady = () => true;
app.getPath = (name) => {
  if (name === 'userData') {
    return process.env.WIPTER_USER_DATA || '/root/.config/wipter-app';
  }
  return '/tmp';
};
app.getVersion = () => '1.25.988';
app.name = 'wipter-app';
app.getName = () => 'wipter-app';
app.isPackaged = true;
app.requestSingleInstanceLock = () => true;
app.disableHardwareAcceleration = () => {};
app.setAppUserModelId = () => {};
app.quit = () => process.exit(0);
app.exit = (code = 0) => process.exit(code);

const ipcMain = {
  handle: (channel, listener) => {
    ipcHandlers.set(channel, listener);
  },
  on: (channel, listener) => {
    ipcListeners.set(channel, listener);
  },
  removeHandler: (channel) => {
    ipcHandlers.delete(channel);
  },
  removeAllListeners: () => {
    ipcListeners.clear();
  },
  invoke: async (channel, ...args) => {
    const handler = ipcHandlers.get(channel);
    if (!handler) {
      throw new Error(`No handler registered for '${channel}'`);
    }
    const dummyEvent = {
      sender: bus.currentWindow ? bus.currentWindow.webContents : new WebContents()
    };
    return await handler(dummyEvent, ...args);
  }
};

const safeStorage = {
  isEncryptionAvailable: () => false,
  getSelectedStorageBackend: () => 'basic_text',
  encryptString: (str) => Buffer.from(str),
  decryptString: (buf) => buf.toString()
};

class Tray extends EventEmitter {
  constructor() {
    super();
  }
  setToolTip() {}
  setContextMenu() {}
}

const Menu = {
  buildFromTemplate: () => ({}),
  setApplicationMenu: () => {}
};

const nativeImage = {
  createFromPath: () => ({}),
  createFromDataURL: () => ({})
};

const nativeTheme = new EventEmitter();
nativeTheme.themeSource = 'system';

const powerMonitor = new EventEmitter();

const powerSaveBlocker = {
  start: () => 1,
  stop: () => true,
  isStarted: () => true
};

const dialog = {
  showMessageBox: async () => ({ response: 0 })
};

const shell = {
  openExternal: async () => {}
};

const session = {
  defaultSession: {
    webRequest: {
      onHeadersReceived: () => {}
    },
    getPreloads: () => [],
    setPreloads: () => {}
  },
  fromPartition: () => session.defaultSession
};

const contextBridge = {
  exposeInMainWorld: () => {}
};

module.exports = {
  app,
  BrowserWindow,
  ipcMain,
  safeStorage,
  Tray,
  Menu,
  nativeImage,
  nativeTheme,
  powerMonitor,
  powerSaveBlocker,
  dialog,
  shell,
  session,
  contextBridge,
  webContents: {
    getAllWebContents: () => []
  },
  _bus: bus
};
