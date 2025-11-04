/**
 * WaitUntil
 *
 * Usage:
 *   // Single one-off check:
 *   new WaitUntil('/mypage').checkOnce();
 *
 *   // Poll repeatedly until the list is empty, then redirect:
 *   const w = new WaitUntil('/mypage');
 *   w.startPolling(2000); // poll every 2 seconds
 *   // w.stop(); // call stop() if you want to cancel polling
 */
class WaitUntil {
  /**
   * @param {string} path - target path to redirect to (e.g. "/mypage")
   * @param {Object} [opts]
   * @param {string} [opts.endpoint='/check_tasks'] - API endpoint to POST to
   * @param {string} [opts.contentType='application/json'] - request content-type
   */
  constructor(path, opts = {}) {
    if (!path || typeof path !== 'string') {
      throw new TypeError('path must be a non-empty string');
    }
    this.path = path;
    this.endpoint = opts.endpoint || '/check_tasks';
    this.contentType = opts.contentType || 'application/json';
    this._pollTimer = null;
    this._stopped = false;
  }

  /**
   * Perform a single check. If the returned list is empty, redirect to `this.path`.
   * If the list is non-empty, do nothing.
   *
   * @returns {Promise<{redirected: boolean, data: any}>}
   */
  async checkOnce() {
    try {
      const res = await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': this.contentType },
        body: JSON.stringify({ path: this.path })
      });

      if (!res.ok) {
        // HTTP error — treat as "do nothing" but surface info to console
        console.error(`WaitUntil: server returned ${res.status} ${res.statusText}`);
        return { redirected: false, data: null };
      }

      const data = await res.json();

      // Expect data to be an array (the API returns a list)
      if (Array.isArray(data) && data.length === 0) {
        // redirect to the requested path
        window.location.href = this.path;
        return { redirected: true, data };
      }

      // non-empty list -> do nothing
      return { redirected: false, data };
    } catch (err) {
      console.error('WaitUntil: request failed', err);
      return { redirected: false, data: null };
    }
  }

  /**
   * Start polling the endpoint every `intervalMs` milliseconds.
   * If the returned list becomes empty, redirect and stop polling.
   *
   * @param {number} intervalMs - e.g. 2000 for 2 seconds
   */
  startPolling(intervalMs = 2000) {
    if (this._pollTimer) return; // already polling
    this._stopped = false;

    const poll = async () => {
      if (this._stopped) return;
      const result = await this.checkOnce();
      // If checkOnce redirected, polling is effectively finished because page is unloading.
      // If it didn't redirect and still non-empty, schedule next poll.
      if (!result.redirected && !this._stopped) {
        this._pollTimer = setTimeout(poll, intervalMs);
      } else {
        this.stop();
      }
    };

    // initial immediate check
    poll();
  }

  /**
   * Stop polling (if previously started)
   */
  stop() {
    this._stopped = true;
    if (this._pollTimer) {
      clearTimeout(this._pollTimer);
      this._pollTimer = null;
    }
  }
}
