window.creditSureRequest = async (url, options = {}) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, cache: "no-store" });
    const text = await response.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch {
      throw new Error("The server returned an unexpected response. Please try again shortly.");
    }
    if (!response.ok) {
      const detail = Array.isArray(body?.detail) ? body.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join("\n") : body?.detail;
      const error = new Error(detail || "The request could not be completed.");
      error.status = response.status;
      error.requestId = response.headers.get("X-Request-ID");
      error.retryAfter = response.headers.get("Retry-After");
      throw error;
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The request timed out. Retry with the same details; duplicate saves are prevented.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and try again.");
    throw error;
  } finally { clearTimeout(timer); }
};

window.creditSureReady = (async () => {
  const config = await window.creditSureRequest("/api/config");
  if (!config.configured) return null;
  if (!window.supabase?.createClient) {
    throw new Error("The sign-in service did not load. Check your connection and refresh.");
  }
  const client = window.supabase.createClient(
    config.supabase_url,
    config.supabase_anon_key,
    {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
        storage: window.sessionStorage,
        storageKey: "creditsure-auth"
      },
      global: {
        fetch: (url, options = {}) => fetch(url, { ...options,
          signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(20000)]) : AbortSignal.timeout(20000) })
      }
    }
  );
  const updateNavigation = (session) => {
    document.querySelectorAll("[data-signed-out]").forEach((element) => {
      element.hidden = Boolean(session);
    });
    document.querySelectorAll("[data-signed-in]").forEach((element) => {
      element.hidden = !session;
    });
  };
  client.auth.onAuthStateChange((event, session) => {
    if (event === "PASSWORD_RECOVERY") window.creditSureRecoveryActive = true;
    updateNavigation(session);
  });
  const { data } = await client.auth.getSession();
  // Remove the previous localStorage session after migrating to tab-scoped storage.
  const project = new URL(config.supabase_url).hostname.split(".")[0];
  window.localStorage.removeItem(`sb-${project}-auth-token`);
  updateNavigation(data.session);
  return { client, config };
})();

// Public pages never leave an unhandled rejected promise.
window.creditSureReady.catch(() => {});
