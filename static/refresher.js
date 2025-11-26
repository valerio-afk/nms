class PartialRefresher {
  constructor(intervalMs = 1000) {
    this.targets = new Map();  // id -> url
    this.intervalMs = intervalMs;
    this.timerId = null;
    this._inFlight = new Map(); // id -> Promise flag to avoid duplicates
    this.once_ids = []
  }

  register(id, url) { this.targets.set(id, url); }
  register_once(id, url)
  {
    this.register(id, url);
    this.once_ids.push(id);
  }
  unregister(id) { this.targets.delete(id); }

  start() {
    if (this.timerId) return;
    this.timerId = setInterval(() => this.refreshAll(), this.intervalMs);
  }
  stop() {
    if (!this.timerId) return;
    clearInterval(this.timerId);
    this.timerId = null;
  }

  async refreshAll() {
    for (const [id, url] of this.targets.entries())
    {
      // Skip if a fetch for this id is still in-flight
      if (this._inFlight.get(id)) continue;
      this._inFlight.set(id, true);

      (async () => {
        try {
          // If you need cookies/session auth, include credentials
          const response = await fetch(url, {
            method: 'GET',
            cache: 'no-store',
            credentials: 'same-origin' // or 'include' if cross-site cookies are required
          });

          console.log(`[refresher] ${id} -> ${url} status=${response.status} ok=${response.ok}`);

          // log important headers for debugging
          try {
            console.log(`[refresher] ${id} content-type:`, response.headers.get('content-type'));
          } catch (e) {
            console.warn('[refresher] could not read headers', e);
          }

          // get body anyway (text) so we can show errors in the UI and inspect content
          const text = await response.text();

          // Option: if the server returned HTML but also a login page or an error,
          // you will see it in `text` and can decide what to do.
          if (!response.ok) {
            // Show the error HTML / message in the element so you can see it visually
            console.warn(`[refresher] Non-OK response for ${id}: ${response.status}`);
            const el = document.getElementById(id);
            if (el) {
              // Optionally prepend a debug banner so you see the status
              el.outerHTML = `<div style="border:2px solid #f5c6cb;padding:0.5rem;margin-bottom:0.5rem;">
                  <strong>Refresh error:</strong> ${response.status} ${response.statusText}
                </div>` + text;
            }
          } else {
            // success -> replace content
            const el = document.getElementById(id);
            if (el) el.outerHTML = text;
          }
        } catch (err) {
          console.error(`[refresher] Fetch failed for ${id} (${url}):`, err);
          const el = document.getElementById(id);
          if (el) el.outerHTML = `<div style="color:darkred">Error fetching ${url}: ${err.message}</div>`;
        } finally {
          // mark as done
          this._inFlight.set(id, false);
        }
      })();

      for (const id of this.once_ids)
      {
        this.unregister(id)
      }

      this.once_ids = []
    }
  }
}


const GlobalRefresher = new PartialRefresher(3000);