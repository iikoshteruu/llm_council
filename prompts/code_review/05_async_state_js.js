/**
 * WebSocket connection manager with reconnection and message queue.
 * Review this code for bugs, race conditions, and correctness problems.
 */

class ConnectionManager {
  constructor(url, options = {}) {
    this.url = url;
    this.maxRetries = options.maxRetries || 5;
    this.retryDelay = options.retryDelay || 1000;
    this.retryCount = 0;
    this.messageQueue = [];
    this.listeners = {};
    this.connected = false;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.connected = true;
      this.retryCount = 0;
      this.flushQueue();
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const handlers = this.listeners[data.type] || [];
      handlers.forEach(fn => fn(data.payload));
    };

    this.ws.onclose = () => {
      this.connected = false;
      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        setTimeout(() => this.connect(), this.retryDelay * this.retryCount);
      }
    };

    this.ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };
  }

  send(type, payload) {
    const message = JSON.stringify({ type, payload });
    if (this.connected) {
      this.ws.send(message);
    } else {
      this.messageQueue.push(message);
    }
  }

  flushQueue() {
    while (this.messageQueue.length > 0) {
      const msg = this.messageQueue.shift();
      this.ws.send(msg);
    }
  }

  on(type, callback) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(callback);
    return () => {
      this.listeners[type] = this.listeners[type].filter(fn => fn !== callback);
    };
  }

  close() {
    this.maxRetries = 0;
    this.ws.close();
  }
}

/**
 * Data fetcher with caching and deduplication.
 */
async function createFetcher(baseUrl) {
  const cache = {};
  const inflight = {};

  return {
    async get(path, options = {}) {
      const key = `${path}?${JSON.stringify(options.params || {})}`;

      if (cache[key] && Date.now() - cache[key].ts < (options.ttl || 30000)) {
        return cache[key].data;
      }

      if (inflight[key]) {
        return inflight[key];
      }

      const url = new URL(path, baseUrl);
      if (options.params) {
        Object.entries(options.params).forEach(([k, v]) => {
          url.searchParams.set(k, v);
        });
      }

      inflight[key] = fetch(url.toString(), {
        headers: options.headers || {},
        signal: options.signal,
      })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(data => {
          cache[key] = { data, ts: Date.now() };
          delete inflight[key];
          return data;
        })
        .catch(err => {
          delete inflight[key];
          throw err;
        });

      return inflight[key];
    },

    invalidate(pathPrefix) {
      Object.keys(cache).forEach(key => {
        if (key.startsWith(pathPrefix)) {
          delete cache[key];
        }
      });
    },

    async batch(paths, options = {}) {
      return Promise.all(paths.map(p => this.get(p, options)));
    },
  };
}

/**
 * Reactive state store with subscription management.
 */
function createStore(initialState) {
  let state = { ...initialState };
  let subscribers = [];
  let batchDepth = 0;
  let pendingNotify = false;

  function getState() {
    return state;
  }

  function setState(updater) {
    const prev = state;
    if (typeof updater === 'function') {
      state = { ...state, ...updater(state) };
    } else {
      state = { ...state, ...updater };
    }
    if (batchDepth > 0) {
      pendingNotify = true;
    } else {
      notify(prev);
    }
  }

  function notify(prev) {
    subscribers.forEach(fn => fn(state, prev));
    pendingNotify = false;
  }

  function subscribe(fn) {
    subscribers.push(fn);
    return () => {
      subscribers = subscribers.filter(s => s !== fn);
    };
  }

  function batch(fn) {
    batchDepth++;
    fn();
    batchDepth--;
    if (batchDepth === 0 && pendingNotify) {
      notify(state);
    }
  }

  return { getState, setState, subscribe, batch };
}
