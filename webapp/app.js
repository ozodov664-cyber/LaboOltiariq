/* LaboOltiariq — Telegram Mini App (bitta fayl, build kerak emas) */
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) {
  tg.ready(); tg.expand();
  // Premium mavzu: Telegram'ning o'z (och/qora) mavzusidan qat'i nazar, ilova doim
  // o'zining brendli to'q rangdagi ko'rinishida ochiladi.
  try { tg.setHeaderColor("#0A0E13"); } catch (e) {}
  try { tg.setBackgroundColor("#0A0E13"); } catch (e) {}
}
const INIT_DATA = tg ? tg.initData : "";

const state = {
  dispatcherPassword: null,
  adminPassword: null,
  order: { region_id: null, tariff_id: null, payment_method: "naqd",
    pickup_text: "", pickup_lat: null, pickup_lng: null,
    dest_text: "", dest_lat: null, dest_lng: null, est_km: 4 },
  meta: null,
  driverWatchId: null,
  polls: [],
};

// ---------------- API ----------------
async function api(method, path, body, extraHeaders) {
  const headers = Object.assign({ "Content-Type": "application/json", "X-Telegram-Init-Data": INIT_DATA }, extraHeaders || {});
  const res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  let json;
  try { json = await res.json(); } catch (e) { throw new Error("Server javob bermadi"); }
  if (!res.ok || !json.ok) throw new Error(json.error || "Xatolik yuz berdi");
  return json.data;
}
const get = (p, h) => api("GET", p, undefined, h);
const post = (p, b, h) => api("POST", p, b || {}, h);
const put = (p, b, h) => api("PUT", p, b || {}, h);
const del = (p, h) => api("DELETE", p, undefined, h);

function money(n) { return Math.round(n || 0).toLocaleString("ru-RU").replace(/,/g, " "); }

// ---------------- Router ----------------
function navigate(hash) { location.hash = hash; }
window.addEventListener("hashchange", () => { clearPolls(); render(); });
window.addEventListener("DOMContentLoaded", render);

function clearPolls() { state.polls.forEach(clearInterval); state.polls = []; }
function poll(fn, ms) { fn(); const id = setInterval(fn, ms); state.polls.push(id); }

function app() { return document.getElementById("app"); }
function html(s) { app().innerHTML = s; }
function topbar(title, backHash) {
  return `<div class="topbar">${backHash ? `<span class="back" onclick="navigate('${backHash}')">‹</span>` : ""}<h1>${title}</h1></div>`;
}
function showError(msg) {
  const box = document.getElementById("err-box");
  if (box) box.innerHTML = `<div class="error">⚠️ ${msg}</div>`;
  else if (tg && tg.showAlert) tg.showAlert(msg);
  else alert(msg);
}

function render() {
  const hash = location.hash.slice(1) || "/";
  const parts = hash.split("/").filter(Boolean);
  const root = parts[0];
  if (!root) return renderHome();
  if (root === "client") return renderClient(parts[1], parts[2]);
  if (root === "driver") return renderDriver(parts[1]);
  if (root === "dispatcher") return renderDispatcher(parts[1]);
  if (root === "admin") return renderAdmin(parts[1]);
  renderHome();
}

// ---------------- HOME ----------------
function renderHome() {
  html(`
    ${topbar("LaboOltiariq Taxi")}
    <div class="container">
      <div class="role-list">
        <div class="role-card" onclick="navigate('client')">
          <div class="role-ic">🚕</div>
          <div><div class="role-name">Mijoz</div><div class="role-desc">Taksi buyurtma qilish</div></div>
          <span class="role-chev">›</span>
        </div>
        <div class="role-card" onclick="navigate('driver')">
          <div class="role-ic">🚗</div>
          <div><div class="role-name">Haydovchi</div><div class="role-desc">Buyurtmalarni qabul qilish</div></div>
          <span class="role-chev">›</span>
        </div>
        <div class="role-card" onclick="navigate('dispatcher')">
          <div class="role-ic">☎️</div>
          <div><div class="role-name">Dispetcher</div><div class="role-desc">Buyurtmalarni boshqarish</div></div>
          <span class="role-chev">›</span>
        </div>
        <div class="role-card" onclick="navigate('admin')">
          <div class="role-ic">⚙️</div>
          <div><div class="role-name">Admin</div><div class="role-desc">Sozlamalar va boshqaruv</div></div>
          <span class="role-chev">›</span>
        </div>
      </div>
    </div>
  `);
}

// ================= CLIENT =================
async function renderClient(sub, arg) {
  if (!sub) return renderClientHome();
  if (sub === "order") return renderClientOrder();
  if (sub === "status") return renderClientStatus(arg);
  if (sub === "history") return renderClientHistory();
  renderClientHome();
}

async function renderClientHome() {
  html(`${topbar("Mijoz", "")}<div class="container center">Yuklanmoqda...</div>`);
  let me;
  try { me = await get("/api/client/me"); } catch (e) { return showError(e.message); }
  if (!me || !me.name || !me.phone) return renderClientRegister();
  let active;
  try { active = await get("/api/client/order/active"); } catch (e) { active = null; }
  if (active) return navigate(`client/status/${active.id}`);
  html(`
    ${topbar("Mijoz", "")}
    <div class="container">
      <div class="card"><b>👋 ${me.name}</b><div class="muted">${me.phone}</div></div>
      <button class="btn" onclick="navigate('client/order')">🚕 Taksi chaqirish</button>
      <button class="btn secondary" onclick="navigate('client/history')">📋 Buyurtmalarim</button>
    </div>
  `);
}

function renderClientRegister() {
  html(`
    ${topbar("Ro'yxatdan o'tish", "")}
    <div class="container">
      <p class="muted">Taksi chaqirish uchun ismingiz va telefon raqamingizni kiriting.</p>
      <label>Ismingiz</label><input id="c-name" placeholder="Ism Familiya">
      <label>Telefon raqam</label><input id="c-phone" placeholder="+998901234567">
      <div id="err-box"></div>
      <button class="btn" onclick="clientRegisterSubmit()">Davom etish</button>
    </div>
  `);
}
async function clientRegisterSubmit() {
  const name = document.getElementById("c-name").value.trim();
  const phone = document.getElementById("c-phone").value.trim();
  if (!name || !phone) return showError("Ism va telefon kerak.");
  try { await post("/api/client/register", { name, phone }); navigate("client"); }
  catch (e) { showError(e.message); }
}

async function renderClientOrder() {
  html(`${topbar("Buyurtma berish", "client")}<div class="container center">Yuklanmoqda...</div>`);
  if (!state.meta) {
    try { state.meta = await get("/api/client/meta"); } catch (e) { return showError(e.message); }
  }
  const o = state.order;
  const regionOpts = state.meta.regions.map(r => `<option value="${r.id}" ${o.region_id == r.id ? "selected" : ""}>${r.name}</option>`).join("");
  html(`
    ${topbar("Buyurtma berish", "client")}
    <div class="container">
      <label>Hudud</label>
      <select id="o-region">${regionOpts}</select>

      <label>Qayerdan (manzil)</label>
      <input id="o-pickup" placeholder="Masalan: Bozor yonida" value="${o.pickup_text || ""}">

      <label>Qayerga (manzil)</label>
      <input id="o-dest" placeholder="Masalan: Avtovokzal" value="${o.dest_text || ""}">

      <div class="map-toolbar">
        <button type="button" class="pin-btn pin-pickup active" id="pin-pickup-btn" onclick="setPinMode('pickup')">🟢 Qayerdan</button>
        <button type="button" class="pin-btn pin-dest" id="pin-dest-btn" onclick="setPinMode('dest')">🔴 Qayerga</button>
        <button type="button" class="pin-btn pin-gps" onclick="useMyLocation()">📍 Men shu yerdaman</button>
      </div>
      <div id="order-map"></div>
      <div class="muted center" id="map-hint" style="margin:-6px 0 12px;">Xaritada bosing yoki markerni surib joyni belgilang</div>

      <label>Taxminiy masofa (km) ${o.pickup_lat && o.dest_lat ? '<span class="muted">(xarita bo\'yicha avtomatik hisoblandi)</span>' : ''}</label>
      <input id="o-km" type="number" min="0" step="0.5" value="${o.est_km}">

      <label>To'lov turi</label>
      <select id="o-pay">
        <option value="naqd" ${o.payment_method === "naqd" ? "selected" : ""}>💵 Naqd</option>
        <option value="karta" ${o.payment_method === "karta" ? "selected" : ""}>💳 Karta</option>
      </select>

      <div class="spacer"></div>
      <div id="tariff-list"></div>
      <div id="err-box"></div>
      <button class="btn" id="order-submit-btn" onclick="clientSubmitOrder()" disabled>Mashina tanlang</button>
    </div>
  `);
  document.getElementById("o-region").onchange = e => { o.region_id = e.target.value; refreshTariffPrices(); };
  document.getElementById("o-pickup").onchange = e => { o.pickup_text = e.target.value; };
  document.getElementById("o-dest").onchange = e => { o.dest_text = e.target.value; };
  document.getElementById("o-km").onchange = e => { o.est_km = parseFloat(e.target.value) || 0; refreshTariffPrices(); };
  document.getElementById("o-pay").onchange = e => { o.payment_method = e.target.value; };
  if (!o.region_id && state.meta.regions[0]) o.region_id = state.meta.regions[0].id;
  initOrderMap();
  refreshTariffPrices();
}

// ---------------- ORDER MAP (Yandex Taxi kabi: xaritadan qayerdan/qayerga belgilash) ----------------
let orderMap = null, pickupMarker = null, destMarker = null, pinMode = "pickup";
const DEFAULT_CENTER = [39.6270, 66.9750]; // Qarshi, O'zbekiston — hech qanday nuqta bo'lmasa shu yerdan boshlanadi

function setPinMode(which) {
  pinMode = which;
  const pb = document.getElementById("pin-pickup-btn"), db_ = document.getElementById("pin-dest-btn");
  if (pb) pb.classList.toggle("active", which === "pickup");
  if (db_) db_.classList.toggle("active", which === "dest");
  const hint = document.getElementById("map-hint");
  if (hint) hint.textContent = which === "pickup" ? "Xaritada bosing — QAYERDAN nuqtasini belgilaysiz" : "Xaritada bosing — QAYERGA nuqtasini belgilaysiz";
}

function initOrderMap() {
  const el = document.getElementById("order-map");
  if (!el || typeof L === "undefined") return;
  const o = state.order;
  const center = o.pickup_lat ? [o.pickup_lat, o.pickup_lng] : DEFAULT_CENTER;
  orderMap = L.map("order-map", { attributionControl: false }).setView(center, o.pickup_lat ? 14 : 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(orderMap);

  if (o.pickup_lat) placeMarker("pickup", o.pickup_lat, o.pickup_lng, false);
  if (o.dest_lat) placeMarker("dest", o.dest_lat, o.dest_lng, false);

  orderMap.on("click", (e) => {
    placeMarker(pinMode, e.latlng.lat, e.latlng.lng, true);
    // birinchi nuqta qo'yilgach, avtomatik ikkinchisiga o'tkazamiz — tezroq bo'lsin
    if (pinMode === "pickup" && !state.order.dest_lat) setPinMode("dest");
  });

  // agar hali hech qanday nuqta yo'q bo'lsa, foydalanuvchining joriy joylashuvidan boshlaymiz (ruxsat bergan bo'lsa)
  if (!o.pickup_lat && navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      if (state.order.pickup_lat) return; // foydalanuvchi shu orada o'zi bosgan bo'lishi mumkin
      orderMap.setView([pos.coords.latitude, pos.coords.longitude], 14);
    }, () => {}, { timeout: 4000 });
  }
  setTimeout(() => orderMap && orderMap.invalidateSize(), 150);
}

function makeDivIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div class="pin-marker" style="background:${color}"></div>`,
    iconSize: [22, 22], iconAnchor: [11, 22],
  });
}

function placeMarker(which, lat, lng, fromUser) {
  const o = state.order;
  const color = which === "pickup" ? "#2BB68A" : "#E85D52";
  if (which === "pickup") {
    o.pickup_lat = lat; o.pickup_lng = lng;
    if (fromUser || !o.pickup_text) { o.pickup_text = "Xaritadan belgilangan nuqta"; }
    const inp = document.getElementById("o-pickup"); if (inp) inp.value = o.pickup_text;
    if (pickupMarker) orderMap.removeLayer(pickupMarker);
    pickupMarker = L.marker([lat, lng], { draggable: true, icon: makeDivIcon(color) }).addTo(orderMap);
    pickupMarker.on("dragend", () => { const p = pickupMarker.getLatLng(); placeMarker("pickup", p.lat, p.lng, true); });
  } else {
    o.dest_lat = lat; o.dest_lng = lng;
    if (fromUser || !o.dest_text) { o.dest_text = "Xaritadan belgilangan nuqta"; }
    const inp = document.getElementById("o-dest"); if (inp) inp.value = o.dest_text;
    if (destMarker) orderMap.removeLayer(destMarker);
    destMarker = L.marker([lat, lng], { draggable: true, icon: makeDivIcon(color) }).addTo(orderMap);
    destMarker.on("dragend", () => { const p = destMarker.getLatLng(); placeMarker("dest", p.lat, p.lng, true); });
  }
  recalcRouteKm();
}

async function recalcRouteKm() {
  const o = state.order;
  if (!(o.pickup_lat && o.dest_lat)) return;
  try {
    const r = await post("/api/client/route_km", {
      pickup_lat: o.pickup_lat, pickup_lng: o.pickup_lng,
      dest_lat: o.dest_lat, dest_lng: o.dest_lng,
    });
    o.est_km = r.km;
    const km = document.getElementById("o-km"); if (km) km.value = r.km;
  } catch (e) { /* jim, mavjud km bilan davom etamiz */ }
  refreshTariffPrices();
}

function useMyLocation() {
  if (!navigator.geolocation) return showError("Brauzeringiz joylashuvni qo'llab-quvvatlamaydi.");
  navigator.geolocation.getCurrentPosition(pos => {
    const { latitude, longitude } = pos.coords;
    placeMarker(pinMode, latitude, longitude, true);
    if (orderMap) orderMap.setView([latitude, longitude], 15);
    if (pinMode === "pickup" && !state.order.dest_lat) setPinMode("dest");
  }, () => showError("Joylashuvga ruxsat berilmadi."));
}

async function refreshTariffPrices() {
  const box = document.getElementById("tariff-list");
  if (!box) return;
  const o = state.order;
  if (!o.region_id) return;
  box.innerHTML = state.meta.tariffs.map(t => `<div class="option" id="opt-${t.id}"><span class="name">${t.name}</span><span class="price">...</span></div>`).join("");
  for (const t of state.meta.tariffs) {
    try {
      const r = await get(`/api/client/price?region_id=${o.region_id}&tariff_id=${t.id}&km=${o.est_km || 0}`);
      const elOpt = document.getElementById(`opt-${t.id}`);
      if (!elOpt) continue;
      elOpt.querySelector(".price").textContent = money(r.price) + " so'm";
      elOpt.onclick = () => {
        o.tariff_id = t.id;
        document.querySelectorAll(".option").forEach(x => x.classList.remove("selected"));
        elOpt.classList.add("selected");
        const btn = document.getElementById("order-submit-btn");
        btn.disabled = false;
        btn.textContent = `Buyurtma berish — ${money(r.price)} so'm`;
      };
    } catch (e) { /* skip */ }
  }
}

async function clientSubmitOrder() {
  const o = state.order;
  if (!o.tariff_id || !o.region_id) return showError("Mashina turini tanlang.");
  try {
    const order = await post("/api/client/order", o);
    navigate(`client/status/${order.id}`);
  } catch (e) { showError(e.message); }
}

async function renderClientStatus(orderId) {
  html(`${topbar("Buyurtma", "client")}<div class="container" id="status-box">Yuklanmoqda...</div>`);
  poll(async () => {
    let order;
    try { order = await get(`/api/client/order/${orderId}`); } catch (e) { return; }
    const box = document.getElementById("status-box");
    if (!box) return;
    const labels = { new: "Qidirilmoqda", accepted: "Haydovchi topildi", in_progress: "Yo'lda", waiting: "Kutmoqda", finished: "Yakunlandi", cancelled: "Bekor qilindi" };
    let driverHtml = "";
    if (order.driver) {
      driverHtml = `
        <div class="card">
          <div class="row"><b>🚗 ${order.driver.name}</b><span>⭐ ${order.driver.rating}</span></div>
          <div class="muted">${order.driver.phone || ""}</div>
        </div>
        <div id="map"></div>
      `;
    }
    let actions = "";
    if (order.status === "new" || order.status === "accepted") {
      actions = `<button class="btn danger" onclick="clientCancelOrder(${orderId})">Bekor qilish</button>`;
    }
    if (order.status === "finished" && order.rating == null) {
      actions = `
        <div class="card center">
          <div>Safarni baholang</div>
          <div class="stars" id="stars">
            ${[1,2,3,4,5].map(i => `<span class="star" data-i="${i}" onclick="clientRate(${orderId},${i})">★</span>`).join("")}
          </div>
        </div>`;
    }
    if (order.status === "finished" || order.status === "cancelled") {
      actions += `<button class="btn secondary" onclick="navigate('client')">Bosh sahifa</button>`;
      clearPolls();
    }
    box.innerHTML = `
      <div class="card">
        <span class="status-badge status-${order.status}">${labels[order.status] || order.status}</span>
        <div class="price-big">${money(order.price)} so'm</div>
        <div class="muted">${order.tariff} · ${order.region}</div>
        <div class="row"><span>📍 ${order.pickup_text || "-"}</span></div>
        <div class="row"><span>🏁 ${order.dest_text || "-"}</span></div>
      </div>
      ${driverHtml}
      ${actions}
    `;
    if (order.driver && order.driver.lat) drawDriverMap(order.driver, order);
  }, 3000);
}

let clientMap = null, clientMarker = null;
function drawDriverMap(driver, order) {
  const el = document.getElementById("map");
  if (!el || typeof L === "undefined") return;
  if (!clientMap) {
    clientMap = L.map("map").setView([driver.lat, driver.lng], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap" }).addTo(clientMap);
  }
  if (clientMarker) clientMap.removeLayer(clientMarker);
  clientMarker = L.marker([driver.lat, driver.lng]).addTo(clientMap).bindPopup(driver.name);
  clientMap.setView([driver.lat, driver.lng]);
  if (order.pickup_lat) L.circleMarker([order.pickup_lat, order.pickup_lng], { color: "green" }).addTo(clientMap);
}

async function clientCancelOrder(orderId) {
  if (tg && tg.showConfirm) { tg.showConfirm("Buyurtmani bekor qilasizmi?", async (ok) => { if (ok) doCancel(orderId); }); }
  else if (confirm("Buyurtmani bekor qilasizmi?")) doCancel(orderId);
}
async function doCancel(orderId) {
  try { await post(`/api/client/order/${orderId}/cancel`); navigate("client"); } catch (e) { showError(e.message); }
}
async function clientRate(orderId, stars) {
  document.querySelectorAll("#stars .star").forEach(s => s.classList.toggle("on", +s.dataset.i <= stars));
  try { await post(`/api/client/order/${orderId}/rate`, { stars }); setTimeout(() => navigate("client"), 600); } catch (e) { showError(e.message); }
}

async function renderClientHistory() {
  html(`${topbar("Buyurtmalarim", "client")}<div class="container" id="hist">Yuklanmoqda...</div>`);
  let orders;
  try { orders = await get("/api/client/orders"); } catch (e) { return showError(e.message); }
  const labels = { new: "Qidirilmoqda", accepted: "Qabul qilindi", in_progress: "Yo'lda", waiting: "Kutmoqda", finished: "Yakunlandi", cancelled: "Bekor qilindi" };
  document.getElementById("hist").innerHTML = orders.length ? orders.map(o => `
    <div class="list-item">
      <div class="row"><b>#${o.id} · ${o.tariff}</b><span class="status-badge status-${o.status}">${labels[o.status] || o.status}</span></div>
      <div class="muted">${o.region} · ${money(o.price)} so'm</div>
    </div>
  `).join("") : `<div class="muted center">Hali buyurtmalar yo'q</div>`;
}

// ================= DRIVER =================
async function renderDriver(sub) {
  html(`${topbar("Haydovchi", "")}<div class="container center">Yuklanmoqda...</div>`);
  let me;
  try { me = await get("/api/driver/me"); }
  catch (e) { return html(`${topbar("Haydovchi", "")}<div class="container"><div class="error">${e.message}</div></div>`); }

  let active;
  try { active = await get("/api/driver/order/active"); } catch (e) { active = null; }

  html(`
    ${topbar("Haydovchi", "")}
    <div class="container">
      <div class="card">
        <div class="row"><b>🚗 ${me.name}</b><span>⭐ ${me.rating}</span></div>
        <div class="muted">${me.tariff_name}</div>
        <div class="muted">Obuna: ${me.sub_active ? "✅ faol" : "❌ tugagan — admin bilan bog'laning"}</div>
      </div>
      <div class="card row">
        <b>Onlayn holat</b>
        <label class="switch"><input type="checkbox" id="online-toggle" ${me.status === "available" ? "checked" : ""}> Onlayn</label>
      </div>
      <div id="trip-box"></div>
      ${!active ? `<button class="btn secondary" onclick="driverStreetPickup()">🛣 Bordyurdan mijoz oldim</button>` : ""}
    </div>
  `);
  document.getElementById("online-toggle").onchange = async (e) => {
    try { await post("/api/driver/online", { online: e.target.checked }); if (e.target.checked) startDriverLocationWatch(); else stopDriverLocationWatch(); }
    catch (err) { e.target.checked = !e.target.checked; showError(err.message); }
  };
  // "available" — onlayn, buyurtma kutmoqda; "busy" — hozir safarda (masofa GPS orqali
  // avtomatik hisoblanishi uchun watch shu holatda ham ishlab turishi SHART, aks holda
  // sahifa qayta yuklansa (masalan ilova qayta ochilsa) safar davomida joylashuv
  // yuborilishi to'xtab, km ko'payishi to'xtab qolardi).
  if (me.status === "available" || me.status === "busy") startDriverLocationWatch();

  poll(async () => {
    let ord;
    try { ord = await get("/api/driver/order/active"); } catch (e) { return; }
    const box = document.getElementById("trip-box");
    if (!box) return;
    if (!ord) { box.innerHTML = ""; return; }
    const labels = { accepted: "Qabul qilindi", in_progress: "Yo'lda", waiting: "Kutmoqda" };
    let controls = "";
    if (ord.status === "accepted") controls = `<button class="btn" onclick="driverAction(${ord.id},'start')">▶️ Safarni boshlash</button>`;
    if (ord.status === "in_progress") controls = `
      <button class="btn secondary" onclick="driverAction(${ord.id},'km')">🔧 +1 km (GPS ishlamasa, qo'lda)</button>
      <button class="btn secondary" onclick="driverAction(${ord.id},'wait_on')">⏸ Kutish boshlash</button>
      <button class="btn danger" onclick="driverAction(${ord.id},'finish')">🏁 Safarni yakunlash</button>`;
    if (ord.status === "waiting") controls = `
      <button class="btn" onclick="driverAction(${ord.id},'wait_off')">▶️ Kutishni tugatish</button>
      <button class="btn danger" onclick="driverAction(${ord.id},'finish')">🏁 Safarni yakunlash</button>`;
    box.innerHTML = `
      <div class="card">
        <span class="status-badge status-${ord.status}">${labels[ord.status] || ord.status}</span>
        <div class="price-big">${money(ord.price)} so'm</div>
        <div class="muted">📍 ${ord.pickup_text || "-"}</div>
        <div class="muted">🏁 ${ord.dest_text || "-"}</div>
        <div class="muted">Masofa: ${ord.actual_km} km <span class="muted">(GPS orqali avtomatik)</span></div>
      </div>
      ${controls}
    `;
  }, 4000);
}

async function driverAction(orderId, action) {
  try { await post(`/api/driver/order/${orderId}/${action}`); } catch (e) { showError(e.message); }
}

function startDriverLocationWatch() {
  if (state.driverWatchId || !navigator.geolocation) return;
  state.driverWatchId = navigator.geolocation.watchPosition(pos => {
    post("/api/driver/location", { lat: pos.coords.latitude, lng: pos.coords.longitude }).catch(() => {});
  }, () => {}, { enableHighAccuracy: true, maximumAge: 10000 });
}
function stopDriverLocationWatch() {
  if (state.driverWatchId) { navigator.geolocation.clearWatch(state.driverWatchId); state.driverWatchId = null; }
}

async function driverStreetPickup() {
  let meta;
  try { meta = state.meta || await get("/api/client/meta"); } catch (e) { return showError(e.message); }
  const region = prompt("Hudud nomini kiriting:\n" + meta.regions.map(r => r.name).join(", "));
  const r = meta.regions.find(x => x.name.toLowerCase() === (region || "").toLowerCase());
  if (!r) return showError("Hudud topilmadi.");
  try { await post("/api/driver/street_pickup", { region_id: r.id }); render(); } catch (e) { showError(e.message); }
}

// ================= DISPATCHER =================
async function renderDispatcher(sub) {
  if (!state.dispatcherPassword) return renderDispatcherLogin();
  html(`${topbar("Dispetcher", "")}<div class="container center">Yuklanmoqda...</div>`);
  try { await get("/api/dispatcher/orders", { "X-Dispatcher-Password": state.dispatcherPassword }); }
  catch (e) { state.dispatcherPassword = null; return renderDispatcherLogin(e.message); }

  html(`
    ${topbar("Dispetcher", "")}
    <div class="container">
      <button class="btn secondary" onclick="navigate('dispatcher/add')">➕ Buyurtma qo'shish</button>
      <div class="spacer"></div>
      <b>📋 Faol buyurtmalar</b>
      <div id="d-orders"></div>
      <div class="spacer"></div>
      <b>🚦 Haydovchilar holati</b>
      <div id="d-drivers"></div>
    </div>
  `);
  if (sub === "add") return renderDispatcherAddOrder();

  poll(async () => {
    let orders;
    try { orders = await get("/api/dispatcher/orders", { "X-Dispatcher-Password": state.dispatcherPassword }); } catch (e) { return; }
    const box = document.getElementById("d-orders");
    if (!box) return;
    if (!orders.length) { box.innerHTML = `<div class="muted">Faol buyurtmalar yo'q</div>`; }
    else {
      box.innerHTML = orders.map(o => `
        <div class="list-item">
          <div class="row"><b>#${o.id} · ${o.tariff}</b><span class="status-badge status-${o.status}">${o.status}</span></div>
          <div class="muted">${o.client_name || "-"} · ${o.client_phone || "-"}</div>
          <div class="muted">${o.region} · ${money(o.price)} so'm</div>
          ${o.status === "new" ? `<div id="assign-${o.id}"></div>` : ""}
          ${o.status !== "finished" && o.status !== "cancelled" ? `<button class="btn small danger" onclick="dispatcherCancel(${o.id})">Bekor qilish</button>` : ""}
        </div>
      `).join("");
      for (const o of orders) {
        if (o.status !== "new") continue;
        const assignBox = document.getElementById(`assign-${o.id}`);
        if (!assignBox) continue;
        try {
          const drivers = await get(`/api/dispatcher/available_drivers/${o.tariff_id || ""}`, { "X-Dispatcher-Password": state.dispatcherPassword });
          if (!drivers.length) { assignBox.innerHTML = `<div class="muted">Mos bo'sh haydovchi yo'q</div>`; continue; }
          assignBox.innerHTML = `
            <select id="sel-${o.id}">${drivers.map(d => `<option value="${d.id}">${d.name} (⭐${d.rating})</option>`).join("")}</select>
            <button class="btn small" onclick="dispatcherAssign(${o.id})">Tayinlash</button>`;
        } catch (e) { /* skip */ }
      }
    }
  }, 5000);

  poll(async () => {
    let drivers;
    try { drivers = await get("/api/dispatcher/drivers", { "X-Dispatcher-Password": state.dispatcherPassword }); } catch (e) { return; }
    const box = document.getElementById("d-drivers");
    if (!box) return;
    box.innerHTML = drivers.map(d => `
      <div class="list-item row">
        <span>${d.name} · ${d.tariff_name}</span>
        <span class="muted">${d.status === "available" ? "🟢" : d.status === "busy" ? "🟡" : "⚪"} ⭐${d.rating}</span>
      </div>
    `).join("");
  }, 7000);
}

function renderDispatcherLogin(err) {
  html(`
    ${topbar("Dispetcher", "")}
    <div class="container">
      <label>Dispetcher parolini kiriting</label>
      <input id="d-pass" type="password">
      ${err ? `<div class="error">${err}</div>` : ""}
      <button class="btn" onclick="dispatcherLogin()">Kirish</button>
    </div>
  `);
}
async function dispatcherLogin() {
  const pass = document.getElementById("d-pass").value;
  try { await post("/api/dispatcher/login", { password: pass }); state.dispatcherPassword = pass; render(); }
  catch (e) { showError(e.message); }
}
async function dispatcherAssign(orderId) {
  const sel = document.getElementById(`sel-${orderId}`);
  if (!sel) return;
  try { await post(`/api/dispatcher/order/${orderId}/assign`, { driver_id: +sel.value }, { "X-Dispatcher-Password": state.dispatcherPassword }); }
  catch (e) { showError(e.message); }
}
async function dispatcherCancel(orderId) {
  try { await post(`/api/dispatcher/order/${orderId}/cancel`, {}, { "X-Dispatcher-Password": state.dispatcherPassword }); }
  catch (e) { showError(e.message); }
}

async function renderDispatcherAddOrder() {
  if (!state.meta) { try { state.meta = await get("/api/client/meta"); } catch (e) { return showError(e.message); } }
  html(`
    ${topbar("Buyurtma qo'shish", "dispatcher")}
    <div class="container">
      <label>Mijoz ismi</label><input id="a-name">
      <label>Mijoz telefoni</label><input id="a-phone" placeholder="+998...">
      <label>Hudud</label>
      <select id="a-region">${state.meta.regions.map(r => `<option value="${r.id}">${r.name}</option>`).join("")}</select>
      <label>Mashina turi</label>
      <select id="a-tariff">${state.meta.tariffs.map(t => `<option value="${t.id}">${t.name}</option>`).join("")}</select>
      <label>Qayerdan</label><input id="a-pickup">
      <label>Qayerga</label><input id="a-dest">
      <label>Taxminiy km</label><input id="a-km" type="number" value="4" min="0" step="0.5">
      <label>To'lov</label>
      <select id="a-pay"><option value="naqd">Naqd</option><option value="karta">Karta</option></select>
      <div id="err-box"></div>
      <button class="btn" onclick="dispatcherSubmitOrder()">Yaratish</button>
    </div>
  `);
}
async function dispatcherSubmitOrder() {
  const body = {
    client_name: document.getElementById("a-name").value.trim(),
    client_phone: document.getElementById("a-phone").value.trim(),
    region_id: +document.getElementById("a-region").value,
    tariff_id: document.getElementById("a-tariff").value,
    pickup_text: document.getElementById("a-pickup").value.trim(),
    dest_text: document.getElementById("a-dest").value.trim(),
    est_km: parseFloat(document.getElementById("a-km").value) || 0,
    payment_method: document.getElementById("a-pay").value,
  };
  try {
    await post("/api/dispatcher/order", body, { "X-Dispatcher-Password": state.dispatcherPassword });
    navigate("dispatcher");
  } catch (e) { showError(e.message); }
}

// ================= ADMIN =================
async function renderAdmin(sub) {
  if (!state.adminPassword) return renderAdminLogin();
  try { await get("/api/admin/stats", { "X-Admin-Password": state.adminPassword }); }
  catch (e) { state.adminPassword = null; return renderAdminLogin(e.message); }

  const tabs = [["stats","📊 Statistika"],["regions","🗺 Hududlar"],["tariffs","🚐 Narxlar"],["drivers","🚗 Haydovchilar"],["subs","💳 Obuna"],["passwords","🔐 Parollar"],["broadcast","📢 Xabar"]];
  const active = sub || "stats";
  html(`
    ${topbar("Admin", "")}
    <div class="container">
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">
        ${tabs.map(([k,l]) => `<span class="btn small ${active===k?'':'secondary'}" onclick="navigate('admin/${k}')">${l}</span>`).join("")}
      </div>
      <div id="admin-tab"></div>
    </div>
  `);
  const H = { "X-Admin-Password": state.adminPassword };
  const box = document.getElementById("admin-tab");
  try {
    if (active === "stats") {
      const s = await get("/api/admin/stats", H);
      box.innerHTML = `
        <div class="card"><div class="row"><span>Yakunlangan safarlar</span><b>${s.trips}</b></div></div>
        <div class="card"><div class="row"><span>Umumiy tushum</span><b>${money(s.revenue)} so'm</b></div></div>
        <div class="card"><div class="row"><span>Haydovchilar (jami / onlayn)</span><b>${s.drivers_total} / ${s.drivers_online}</b></div></div>
      `;
    } else if (active === "regions") return renderAdminRegions(box, H);
    else if (active === "tariffs") return renderAdminTariffs(box, H);
    else if (active === "drivers") return renderAdminDrivers(box, H);
    else if (active === "subs") return renderAdminSubs(box, H);
    else if (active === "passwords") return renderAdminPasswords(box, H);
    else if (active === "broadcast") return renderAdminBroadcast(box, H);
  } catch (e) { box.innerHTML = `<div class="error">${e.message}</div>`; }
}

function renderAdminLogin(err) {
  html(`
    ${topbar("Admin", "")}
    <div class="container">
      <label>Admin parolini kiriting</label>
      <input id="ad-pass" type="password">
      ${err ? `<div class="error">${err}</div>` : ""}
      <button class="btn" onclick="adminLogin()">Kirish</button>
    </div>
  `);
}
async function adminLogin() {
  const pass = document.getElementById("ad-pass").value;
  try { await post("/api/admin/login", { password: pass }); state.adminPassword = pass; navigate("admin/stats"); }
  catch (e) { showError(e.message); }
}

async function renderAdminRegions(box, H) {
  const regions = await get("/api/admin/regions", H);
  box.innerHTML = `
    ${regions.map(r => `
      <div class="list-item row">
        <span>${r.name} — minimalka ${money(r.minimalka)}, kutish ${money(r.wait_per_min)}/daq</span>
        <span class="btn small danger" onclick="adminDeleteRegion(${r.id})">O'chirish</span>
      </div>`).join("")}
    <div class="card">
      <b>Yangi hudud</b>
      <label>Nomi</label><input id="r-name">
      <label>Minimalka (so'm)</label><input id="r-min" type="number" value="15000">
      <label>Kutish narxi (so'm/daqiqa)</label><input id="r-wait" type="number" value="1000">
      <button class="btn" onclick="adminAddRegion()">Qo'shish</button>
    </div>
  `;
}
async function adminAddRegion() {
  const H = { "X-Admin-Password": state.adminPassword };
  try {
    await post("/api/admin/regions", {
      name: document.getElementById("r-name").value.trim(),
      minimalka: +document.getElementById("r-min").value,
      wait_per_min: +document.getElementById("r-wait").value,
    }, H);
    navigate("admin/regions"); render();
  } catch (e) { showError(e.message); }
}
async function adminDeleteRegion(id) {
  try { await del(`/api/admin/regions/${id}`, { "X-Admin-Password": state.adminPassword }); render(); }
  catch (e) { showError(e.message); }
}

async function renderAdminTariffs(box, H) {
  const tariffs = await get("/api/admin/tariffs", H);
  box.innerHTML = tariffs.map(t => `
    <div class="list-item">
      <div class="row"><b>${t.name}</b><span>${money(t.km_price)} so'm/km</span></div>
      <input id="t-${t.id}" type="number" value="${t.km_price}" style="margin-top:6px;">
      <button class="btn small" onclick="adminSaveTariff('${t.id}')">Saqlash</button>
    </div>
  `).join("");
}
async function adminSaveTariff(id) {
  const val = +document.getElementById(`t-${id}`).value;
  try { await put(`/api/admin/tariffs/${id}`, { km_price: val }, { "X-Admin-Password": state.adminPassword }); render(); }
  catch (e) { showError(e.message); }
}

async function renderAdminDrivers(box, H) {
  const drivers = await get("/api/admin/drivers", H);
  const meta = state.meta || (state.meta = await get("/api/client/meta"));
  box.innerHTML = `
    ${drivers.map(d => `
      <div class="list-item">
        <div class="row"><b>${d.name}</b><span>${d.blocked ? "🔒" : "🚗"} ${d.tariff_name}</span></div>
        <div class="muted">${d.phone || ""} · ⭐${d.rating} (${d.rating_count}) · parol: ${d.password}</div>
        <div class="muted">Obuna: ${d.sub_active ? "✅ faol" : "❌ tugagan"}</div>
        <button class="btn small secondary" onclick="adminToggleBlock(${d.id})">${d.blocked ? "Blokdan chiqarish" : "Bloklash"}</button>
        <button class="btn small secondary" onclick="adminResetPass(${d.id})">Yangi parol</button>
        <button class="btn small secondary" onclick="adminExtendSub(${d.id},7)">+7 kun</button>
        <button class="btn small secondary" onclick="adminExtendSub(${d.id},30)">+30 kun</button>
      </div>
    `).join("")}
    <div class="card">
      <b>Yangi haydovchi</b>
      <label>Telegram ID (haydovchi botga /start yozgan bo'lishi kerak)</label><input id="nd-id" type="number">
      <label>Ismi</label><input id="nd-name">
      <label>Telefon</label><input id="nd-phone">
      <label>Mashina turi</label>
      <select id="nd-tariff">${meta.tariffs.map(t => `<option value="${t.id}">${t.name}</option>`).join("")}</select>
      <button class="btn" onclick="adminAddDriver()">Qo'shish</button>
    </div>
  `;
}
async function adminAddDriver() {
  const H = { "X-Admin-Password": state.adminPassword };
  try {
    const r = await post("/api/admin/drivers", {
      telegram_id: +document.getElementById("nd-id").value,
      name: document.getElementById("nd-name").value.trim(),
      phone: document.getElementById("nd-phone").value.trim(),
      tariff_id: document.getElementById("nd-tariff").value,
    }, H);
    if (tg && tg.showAlert) tg.showAlert(`Yaratildi. Parol: ${r.password}`); else alert("Parol: " + r.password);
    render();
  } catch (e) { showError(e.message); }
}
async function adminToggleBlock(id) { try { await post(`/api/admin/drivers/${id}/toggle_block`, {}, { "X-Admin-Password": state.adminPassword }); render(); } catch (e) { showError(e.message); } }
async function adminResetPass(id) {
  try { const r = await post(`/api/admin/drivers/${id}/reset_password`, {}, { "X-Admin-Password": state.adminPassword }); if (tg && tg.showAlert) tg.showAlert("Yangi parol: " + r.password); else alert("Yangi parol: " + r.password); render(); }
  catch (e) { showError(e.message); }
}
async function adminExtendSub(id, days) { try { await post(`/api/admin/drivers/${id}/extend_subscription`, { days }, { "X-Admin-Password": state.adminPassword }); render(); } catch (e) { showError(e.message); } }

async function renderAdminSubs(box, H) {
  const p = await get("/api/admin/subscription_prices", H);
  box.innerHTML = `
    <div class="card">
      <label>Haftalik narx (so'm)</label><input id="sp-week" type="number" value="${p.week}">
      <label>Oylik narx (so'm)</label><input id="sp-month" type="number" value="${p.month}">
      <button class="btn" onclick="adminSaveSubs()">Saqlash</button>
    </div>
  `;
}
async function adminSaveSubs() {
  try {
    await put("/api/admin/subscription_prices", { week: +document.getElementById("sp-week").value, month: +document.getElementById("sp-month").value }, { "X-Admin-Password": state.adminPassword });
    if (tg && tg.showAlert) tg.showAlert("Saqlandi."); else alert("Saqlandi.");
  } catch (e) { showError(e.message); }
}

function renderAdminPasswords(box) {
  box.innerHTML = `
    <div class="card">
      <label>Yangi admin paroli</label><input id="pw-admin" type="password" placeholder="bo'sh qoldirsangiz o'zgarmaydi">
      <label>Yangi dispetcher paroli</label><input id="pw-disp" type="password" placeholder="bo'sh qoldirsangiz o'zgarmaydi">
      <button class="btn" onclick="adminSavePasswords()">Saqlash</button>
    </div>
  `;
}
async function adminSavePasswords() {
  const admin_password = document.getElementById("pw-admin").value.trim();
  const dispatcher_password = document.getElementById("pw-disp").value.trim();
  try {
    await put("/api/admin/passwords", { admin_password, dispatcher_password }, { "X-Admin-Password": state.adminPassword });
    if (admin_password) state.adminPassword = admin_password;
    if (tg && tg.showAlert) tg.showAlert("Saqlandi."); else alert("Saqlandi.");
    render();
  } catch (e) { showError(e.message); }
}

function renderAdminBroadcast(box) {
  box.innerHTML = `
    <div class="card">
      <label>Barcha haydovchilarga xabar</label>
      <textarea id="bc-text" rows="4"></textarea>
      <button class="btn" onclick="adminBroadcast()">Yuborish</button>
    </div>
  `;
}
async function adminBroadcast() {
  const text = document.getElementById("bc-text").value.trim();
  if (!text) return showError("Xabar matni bo'sh.");
  try {
    const r = await post("/api/admin/broadcast", { text }, { "X-Admin-Password": state.adminPassword });
    if (tg && tg.showAlert) tg.showAlert(`${r.sent}/${r.total} haydovchiga yuborildi.`); else alert(`${r.sent}/${r.total} yuborildi.`);
  } catch (e) { showError(e.message); }
}
