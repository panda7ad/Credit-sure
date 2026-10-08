window.creditSureRequest = async (url, options = {}) => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal, cache: "no-store", credentials: "omit" });
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
    if (error.name === "AbortError") throw new Error("The request timed out. Please try again shortly.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and try again.");
    throw error;
  } finally { clearTimeout(timer); }
};
