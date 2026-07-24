const API = "";

export function getToken() {
  return localStorage.getItem("admin_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("admin_token", token);
  else localStorage.removeItem("admin_token");
}

export async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...opts.headers };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + path, { ...opts, headers });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err);
  }
  return res.json();
}

export async function checkAuth() {
  try {
    await api("/api/admin/check");
    return true;
  } catch {
    return false;
  }
}

export async function login(email, password) {
  const data = await api("/api/admin/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.token);
  return data;
}

export async function getJobs(offset = 0, limit = 50) {
  return api(`/api/admin/jobs?offset=${offset}&limit=${limit}`);
}

export async function getThemes() {
  return api("/api/themes");
}

export async function getJobStatus(jobId) {
  return api("/api/status/" + jobId);
}

export async function generateBook(formData) {
  const res = await fetch(API + "/api/generate", { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteJob(jobId) {
  return api("/api/admin/jobs/" + jobId, { method: "DELETE" });
}

export async function retryJob(jobId) {
  return api("/api/admin/jobs/" + jobId + "/retry", { method: "POST" });
}
