import {
    apiJson,
    escapeHtml,
    formatDateTime,
    hideBanner,
    joinSafeLines,
    logout,
    showBanner,
} from "/static/common.js";

// Consent state is intentionally minimal: selected customer list plus signature state.
const state = { customers: [], hasSignature: false };

const customerSelectEl = document.getElementById("customer-select");
const customerNameEl = document.getElementById("customer-name");
const customerPhoneEl = document.getElementById("customer-phone");
const treatmentNameEl = document.getElementById("treatment-name");
const notesEl = document.getElementById("notes");
const formEl = document.getElementById("consent-form");
const statusBannerEl = document.getElementById("status-banner");
const recentConsentsEl = document.getElementById("recent-consents");
const signatureStateEl = document.getElementById("signature-state");
const clearSignatureEl = document.getElementById("clear-signature");
const resetFormEl = document.getElementById("reset-form");
const canvas = document.getElementById("signature-pad");
const logoutEl = document.getElementById("logout-button");

let context = null;
let drawing = false;

function setupCanvas(preserve = false) {
    const snapshot = preserve && state.hasSignature ? canvas.toDataURL("image/png") : null;
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = 2.4;
    context.strokeStyle = "#6A334B";
    context.fillStyle = "#fffaf8";
    context.fillRect(0, 0, rect.width, rect.height);

    if (snapshot) {
        const image = new Image();
        image.onload = () => context.drawImage(image, 0, 0, rect.width, rect.height);
        image.src = snapshot;
    }
}

// Signature capture uses Pointer Events so finger and stylus both work well.
function clearSignature() {
    state.hasSignature = false;
    setupCanvas(false);
    updateSignatureState();
}

function updateSignatureState() {
    signatureStateEl.textContent = state.hasSignature ? "서명 완료" : "서명 대기 중";
}

function getAgreementItems() {
    return Array.from(document.querySelectorAll('input[name="agreement-item"]:checked')).map((input) => input.value);
}

function getPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function startDrawing(event) {
    drawing = true;
    state.hasSignature = true;
    updateSignatureState();
    const point = getPoint(event);
    context.beginPath();
    context.moveTo(point.x, point.y);
    canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
}

function draw(event) {
    if (!drawing) return;
    const point = getPoint(event);
    context.lineTo(point.x, point.y);
    context.stroke();
    event.preventDefault();
}

function endDrawing(event) {
    if (!drawing) return;
    drawing = false;
    context.closePath();
    event.preventDefault();
}

function populateCustomerSelect(customers) {
    const options = ['<option value="">직접 입력</option>'];
    customers.forEach((customer) => {
        options.push(`<option value="${customer.id}">${escapeHtml(customer.name)} · ${escapeHtml(customer.phone)}</option>`);
    });
    customerSelectEl.innerHTML = options.join("");
}

async function fetchCustomers() {
    const data = await apiJson("/api/customers");
    state.customers = data.customers;
    populateCustomerSelect(state.customers);
}

// The recent panel doubles as an admin preview surface for saved signatures.
function renderRecentConsents(consents) {
    if (!consents.length) {
        recentConsentsEl.innerHTML = '<div class="rounded-[24px] bg-white/80 px-4 py-5 text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">저장된 전자 동의서가 아직 없습니다.</div>';
        return;
    }

    recentConsentsEl.innerHTML = consents.map((consent) => {
        const preview = consent.signature_available
            ? `<img src="/api/consents/${consent.id}/signature" alt="서명 미리보기" class="signature-preview h-28 w-full rounded-[18px] object-contain ring-1 ring-[#f1dde2]">`
            : `<div class="signature-preview flex h-28 items-center justify-center rounded-[18px] text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">서명 이미지 없음</div>`;
        return `
            <article class="rounded-[24px] bg-[linear-gradient(180deg,rgba(255,255,255,.84),rgba(255,245,247,.92))] p-4 ring-1 ring-[#f1dde2]">
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <h3 class="font-display text-2xl text-[#54283b]">${escapeHtml(consent.customer_name)}</h3>
                        <p class="mt-1 text-sm text-[#7b5f6d]">${escapeHtml(consent.treatment_name)}</p>
                    </div>
                    <span class="rounded-full bg-[#fff5eb] px-3 py-1 text-xs font-semibold text-[#8b6732] ring-1 ring-[#f0debe]">저장 완료</span>
                </div>
                <div class="mt-3">${preview}</div>
                <p class="mt-3 text-sm text-[#8b6b79]">${escapeHtml(consent.phone)}</p>
                <p class="mt-2 text-sm leading-6 text-[#6d5562]">${joinSafeLines(consent.agreement_items)}</p>
                <div class="mt-4 flex flex-wrap items-center gap-2">
                    <a href="/api/consents/${consent.id}/pdf" class="rounded-full bg-gradient-to-r from-[#6b334b] to-[#c09a5c] px-4 py-2 text-sm font-semibold text-white">PDF 다운로드</a>
                    <span class="text-xs uppercase tracking-[0.16em] text-[#a78392]">${formatDateTime(consent.signed_at)}</span>
                </div>
            </article>
        `;
    }).join("");
}

async function fetchRecentConsents() {
    const data = await apiJson("/api/consents?limit=6");
    renderRecentConsents(data.consents);
}

customerSelectEl.addEventListener("change", () => {
    const customer = state.customers.find((item) => String(item.id) === customerSelectEl.value);
    if (!customer) return;
    customerNameEl.value = customer.name;
    customerPhoneEl.value = customer.phone;
});

clearSignatureEl.addEventListener("click", clearSignature);
resetFormEl.addEventListener("click", () => {
    formEl.reset();
    clearSignature();
    hideBanner(statusBannerEl);
});

canvas.addEventListener("pointerdown", startDrawing);
canvas.addEventListener("pointermove", draw);
canvas.addEventListener("pointerup", endDrawing);
canvas.addEventListener("pointerleave", endDrawing);
canvas.addEventListener("pointercancel", endDrawing);
window.addEventListener("resize", () => setupCanvas(true));

formEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const agreementItems = getAgreementItems();
    const payload = {
        customer_id: customerSelectEl.value ? Number(customerSelectEl.value) : null,
        customer_name: customerNameEl.value.trim(),
        phone: customerPhoneEl.value.trim(),
        treatment_name: treatmentNameEl.value.trim(),
        agreement_items: agreementItems,
        notes: notesEl.value.trim(),
        signature_data_url: canvas.toDataURL("image/png"),
    };

    if (!payload.customer_name || !payload.phone || !payload.treatment_name) {
        showBanner(statusBannerEl, "고객명, 연락처, 시술명을 모두 입력해 주세요.", "error", "mt-4");
        return;
    }
    if (!agreementItems.length) {
        showBanner(statusBannerEl, "동의 항목을 하나 이상 선택해 주세요.", "error", "mt-4");
        return;
    }
    if (!state.hasSignature) {
        showBanner(statusBannerEl, "서명 패드에 직접 서명해 주세요.", "error", "mt-4");
        return;
    }

    try {
        showBanner(statusBannerEl, "전자 동의서를 저장하는 중입니다.", "loading", "mt-4");
        const data = await apiJson("/api/consents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        showBanner(statusBannerEl, data.message, "success", "mt-4");
        formEl.reset();
        clearSignature();
        await fetchRecentConsents();
    } catch (error) {
        showBanner(statusBannerEl, error.message, "error", "mt-4");
    }
});

logoutEl?.addEventListener("click", logout);

Promise.all([fetchCustomers(), fetchRecentConsents()])
    .catch((error) => showBanner(statusBannerEl, error.message, "error", "mt-4"))
    .finally(() => {
        setupCanvas(false);
        updateSignatureState();
    });
