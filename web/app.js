const $ = (selector) => document.querySelector(selector);
const api = async (path, options = {}) => {
  const token = localStorage.getItem("token");
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || "Request failed.");
  return data;
};
const message = (text) => $("#message").textContent = text;

let profileExists = false;
async function loadProfile() {
  try { const profile = await api("/profile"); profileExists = true; $("#welcome").textContent = profile.full_name || "Your profile"; $("#candidate").full_name.value = profile.full_name || ""; $("#candidate").skills.value = profile.skills.join(", "); $("#skills").innerHTML = profile.skills.map(s => `<span class="chip">${s}</span>`).join(""); $("#profile-copy").textContent = "Recommendations combine this profile with your latest parsed resume, when available."; }
  catch { $("#profile-copy").textContent = "No saved profile yet. Upload a resume first or create one through the API documentation, then return here."; }
}
function showDashboard() { $("#auth").hidden = true; $("#dashboard").hidden = false; loadProfile(); }
$("#login").addEventListener("submit", async (event) => { event.preventDefault(); try { const data = await api("/login", {method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}); localStorage.setItem("token", data.access_token); showDashboard(); } catch (err) { message(err.message); } });
$("#register").addEventListener("submit", async (event) => { event.preventDefault(); try { await api("/register", {method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}); message("Account created. Sign in to continue."); } catch (err) { message(err.message); } });
$("#candidate").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.target); const payload = {full_name: form.get("full_name") || null, skills: String(form.get("skills") || "").split(",").map(s => s.trim()).filter(Boolean)}; try { await api("/profile", {method: profileExists ? "PUT" : "POST", body: JSON.stringify(payload)}); message("Profile saved."); loadProfile(); } catch (err) { message(err.message); } });
$("#upload").addEventListener("submit", async (event) => { event.preventDefault(); const token = localStorage.getItem("token"); try { const response = await fetch("/resume/upload", {method:"POST", headers:{Authorization:`Bearer ${token}`}, body:new FormData(event.target)}); const data = await response.json(); if (!response.ok) throw new Error(data.error?.message || "Resume upload failed."); message("Resume extracted and saved. Find matches when ready."); } catch (err) { message(err.message); } });
$("#match").addEventListener("click", async () => { message("Analyzing your profile, retrieving internships, and ranking matches…"); $("#results").innerHTML = ""; try { const data = await api("/internships/match", {method:"POST",body:JSON.stringify({top_k:5})}); $("#skills").innerHTML = data.candidate_skills.map(s => `<span class="chip">${s}</span>`).join(""); $("#results").innerHTML = data.recommendations.map((r, i) => `<article class="card"><div class="top"><div><p class="eyebrow">#${i+1} RECOMMENDATION</p><h2>${r.title}</h2><p class="meta">${r.company}${r.location ? " · " + r.location : ""}</p></div><div class="score">${r.match_score}%</div></div><p>${r.description}</p><p class="match"><strong>Matching skills:</strong> ${r.matching_skills.join(", ") || "None listed"}</p>${r.missing_skills.length ? `<p class="missing"><strong>Missing required skills:</strong> ${r.missing_skills.join(", ")}</p>` : ""}<p>${r.reason}</p><p class="meta">${r.duration ? "Duration: " + r.duration : ""}${r.stipend ? " · " + r.stipend : ""}</p>${r.application_url ? `<a href="${r.application_url}" target="_blank" rel="noreferrer">Open application →</a>` : ""}</article>`).join(""); message(data.recommendations.length ? "Matches ready." : "No internships matched your profile."); } catch (err) { message(err.message); } });
if (localStorage.getItem("token")) showDashboard();
