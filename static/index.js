import {
    apiJson,
    escapeHtml,
    expiryLabel,
    formatDate,
    formatDateTime,
    hideBanner,
    joinSafeLines,
    logout,
    showBanner,
} from "/static/common.js";

// Dashboard state keeps the list view and the currently opened modal in sync.
const state = {
    customers: [],
    summary: null,
    search: "",
    searchTimer: null,
    activeCustomer: null,
};

const customerListEl = document.getElementById("customer-list");
const insightListEl = document.getElementById("insight-list");
const statusBannerEl = document.getElementById("status-banner");
const searchInputEl = document.getElementById("search-input");
const modalEl = document.getElementById("customer-modal");
const modalContentEl = document.getElementById("customer-modal-content");
const modalCloseEls = document.querySelectorAll("[data-close-modal]");
const logoutEl = document.getElementById("logout-button");

function getEventElement(event) {
    return event.target instanceof Element ? event.target : null;
}

async function fetchCustomers(query = "", options = {}) {
    const { silent = false } = options;
    try {
        if (!silent) {
            showBanner(statusBannerEl, "고객 보드를 불러오는 중입니다.", "loading");
        }

        const url = query ? `/api/customers?q=${encodeURIComponent(query)}` : "/api/customers";
        const data = await apiJson(url);
        state.customers = data.customers;
        state.summary = data.summary;
        renderSummary();
        renderCustomerList();
        renderInsights();
        if (!silent) hideBanner(statusBannerEl);
    } catch (error) {
        renderCustomerList(true);
        renderInsights(true);
        showBanner(statusBannerEl, error.message, "error");
    }
}

// The summary row uses the same API payload as the customer cards.
function renderSummary() {
    if (!state.summary) return;
    document.getElementById("summary-customers").textContent = state.summary.customer_count;
    document.getElementById("summary-vips").textContent = state.summary.vip_count;
    document.getElementById("summary-remaining").textContent = state.summary.remaining_sessions_total;
    document.getElementById("summary-focus").textContent = state.summary.focus_count;
    document.getElementById("summary-low-balance").textContent = state.summary.low_balance_count;
    document.getElementById("summary-expiring-soon").textContent = state.summary.expiring_soon_count;
}

// Each customer card stays lightweight. Detailed histories are loaded lazily.
function renderCustomerList(hasError = false) {
    if (hasError) {
        customerListEl.innerHTML = emptyState("보드를 불러오지 못했습니다.", "API 연결 상태를 확인한 뒤 다시 시도해 주세요.");
        return;
    }
    if (!state.customers.length) {
        customerListEl.innerHTML = emptyState("검색 결과가 없습니다.", "다른 이름이나 연락처로 다시 검색해 보세요.");
        return;
    }
    customerListEl.innerHTML = state.customers.map(renderCustomerCard).join("");
}

// The right rail highlights only the items the owner should react to first.
function renderInsights(hasError = false) {
    if (hasError) {
        insightListEl.innerHTML = insightCard("연결 오류", "운영 인사이트를 구성하지 못했습니다.", "bg-[#fff1f4] text-[#864d63]");
        return;
    }

    const tickets = state.customers.flatMap((customer) =>
        customer.tickets.map((ticket) => ({ ...ticket, customer_name: customer.name }))
    );
    const lowBalance = tickets
        .filter((ticket) => ticket.remaining_sessions > 0 && ticket.remaining_sessions <= 2)
        .slice(0, 3);
    const expiringSoon = tickets
        .filter((ticket) => ticket.days_until_expiry !== null && ticket.days_until_expiry <= 14)
        .slice(0, 3);
    const vipMemos = state.customers
        .filter((customer) => customer.grade === "VIP")
        .slice(0, 2)
        .map((customer) => `${customer.name} · ${customer.memo}`);

    const cards = [];
    if (lowBalance.length) {
        cards.push(
            insightCard(
                "티켓 소진 임박",
                joinSafeLines(lowBalance.map((ticket) => `${ticket.customer_name} · ${ticket.title} (${ticket.remaining_sessions}회)`)),
                "bg-[#fff2f5] text-[#7b4258]"
            )
        );
    }
    if (expiringSoon.length) {
        cards.push(
            insightCard(
                "만료 체크",
                joinSafeLines(expiringSoon.map((ticket) => `${ticket.customer_name} · ${ticket.title} (${expiryLabel(ticket.days_until_expiry)})`)),
                "bg-[#fff7ef] text-[#7d5a2f]"
            )
        );
    }
    if (vipMemos.length) {
        cards.push(
            insightCard("VIP 응대 메모", joinSafeLines(vipMemos), "bg-[#fff9fb] text-[#6d3b4f]")
        );
    }
    if (!cards.length) {
        cards.push(insightCard("안정 상태", "즉시 대응이 필요한 티켓이 없습니다.", "bg-white text-[#765767]"));
    }
    insightListEl.innerHTML = cards.join("");
}

function renderCustomerCard(customer) {
    const gradeTone = {
        VIP: "bg-[#5f3047] text-white",
        Gold: "bg-[#e8d5af] text-[#6d4e1e]",
        Regular: "bg-[#f7e9ee] text-[#7e5b6c]",
    };
    const ticketMarkup = customer.tickets.length
        ? customer.tickets.map(renderTicket).join("")
        : `<div class="rounded-[24px] border border-dashed border-[#e8d1d8] bg-white/70 px-4 py-5 text-sm text-[#8a6978]">등록된 티켓이 없습니다.</div>`;

    return `
        <article data-customer-card="${customer.id}" class="luxury-stroke cursor-pointer overflow-hidden rounded-[32px] bg-[linear-gradient(180deg,rgba(255,255,255,.86),rgba(255,245,247,.92))] shadow-card transition hover:-translate-y-0.5">
            <div class="h-1.5 bg-gradient-to-r from-[#f4d7e0] via-[#c6a46a] to-[#6b334b]"></div>
            <div class="px-5 py-5 sm:px-6">
                <div class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                    <div class="min-w-0">
                        <div class="flex flex-wrap items-center gap-2">
                            <span class="rounded-full px-3 py-1 text-xs font-semibold ${gradeTone[customer.grade] || gradeTone.Regular}">${escapeHtml(customer.grade)}</span>
                            <span class="rounded-full bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#aa8393]">상세 보기</span>
                        </div>
                        <div class="mt-4 flex flex-wrap items-end gap-3">
                            <h3 class="font-display text-3xl text-[#53263a]">${escapeHtml(customer.name)}</h3>
                            <span class="pb-1 text-sm text-[#967181]">${escapeHtml(customer.phone)}</span>
                        </div>
                        <div class="mt-4 flex flex-wrap gap-2 text-sm text-[#7f6471]">
                            <span class="rounded-full bg-white/80 px-4 py-2 ring-1 ring-[#f1dde2]">마지막 방문 ${formatDate(customer.last_visit)}</span>
                            <span class="rounded-full bg-[#fff5eb] px-4 py-2 text-[#8b6732] ring-1 ring-[#f0debe]">잔여 ${customer.total_remaining_sessions}회</span>
                        </div>
                    </div>
                    <div class="w-full rounded-[24px] bg-[linear-gradient(180deg,rgba(255,255,255,.75),rgba(255,244,248,.86))] p-4 text-sm text-[#715867] ring-1 ring-white/60 xl:max-w-sm">
                        <p class="text-[11px] font-semibold uppercase tracking-[0.22em] text-[#a78392]">Consulting Memo</p>
                        <p class="mt-3 leading-7">${escapeHtml(customer.memo || "메모 없음")}</p>
                    </div>
                </div>
                <div class="mt-5 space-y-3">${ticketMarkup}</div>
            </div>
        </article>
    `;
}

function renderTicket(ticket) {
    const isDisabled = ticket.remaining_sessions === 0;
    const maxAmount = Math.max(ticket.remaining_sessions, 1);
    return `
        <section class="rounded-[26px] bg-[linear-gradient(180deg,rgba(255,255,255,.86),rgba(255,246,247,.96))] p-4 ring-1 ring-[#f3dde4]">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                        <h4 class="text-lg font-semibold text-[#553040]">${escapeHtml(ticket.title)}</h4>
                        <span class="rounded-full bg-[#fff6e8] px-3 py-1 text-xs font-semibold text-[#8a6730]">${expiryLabel(ticket.days_until_expiry)}</span>
                    </div>
                    <div class="mt-3 flex flex-wrap items-center gap-3 text-sm text-[#816775]">
                        <span>잔여 ${ticket.remaining_sessions} / 총 ${ticket.total_sessions}</span>
                        <span>사용 ${ticket.used_sessions}회</span>
                    </div>
                    <div class="mt-4 h-2.5 overflow-hidden rounded-full bg-[#f3e2e7]">
                        <div class="h-full rounded-full bg-gradient-to-r from-[#f0c0d0] via-[#d6b06b] to-[#7d4059]" style="width:${ticket.progress_percent}%"></div>
                    </div>
                </div>
                <div data-no-modal="true" class="w-full rounded-[24px] bg-white/90 p-4 shadow-sm ring-1 ring-[#f3e2e7] lg:w-[240px]">
                    <label class="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#aa8393]">차감 횟수</label>
                    <div class="mt-3 flex items-center gap-2">
                        <button type="button" data-no-modal="true" data-step="-1" data-ticket-id="${ticket.id}" class="flex h-10 w-10 items-center justify-center rounded-full bg-[#faf1f4] text-lg text-[#7b5868] ring-1 ring-[#f1dde2]">-</button>
                        <input data-no-modal="true" data-ticket-amount="${ticket.id}" type="number" min="1" max="${maxAmount}" value="1" class="h-10 flex-1 rounded-full border-none bg-[#fff7f8] text-center text-sm font-semibold text-[#5a3143] ring-1 ring-[#f1dde2] focus:ring-2 focus:ring-[#d6b06b]/40">
                        <button type="button" data-no-modal="true" data-step="1" data-ticket-id="${ticket.id}" class="flex h-10 w-10 items-center justify-center rounded-full bg-[#faf1f4] text-lg text-[#7b5868] ring-1 ring-[#f1dde2]">+</button>
                    </div>
                    <button type="button" data-no-modal="true" data-deduct-ticket="${ticket.id}" class="mt-4 flex h-11 w-full items-center justify-center rounded-full bg-gradient-to-r from-[#6b334b] to-[#c09a5c] px-4 text-sm font-semibold text-white shadow-md disabled:cursor-not-allowed disabled:from-slate-300 disabled:to-slate-300" ${isDisabled ? "disabled" : ""}>${isDisabled ? "잔여 없음" : "시술 후 티켓 차감"}</button>
                </div>
            </div>
        </section>
    `;
}

function emptyState(title, description) {
    return `<div class="luxury-stroke rounded-[28px] bg-white/80 px-6 py-10 text-center shadow-card"><h3 class="font-display text-2xl text-[#5a2e42]">${escapeHtml(title)}</h3><p class="mt-3 text-sm text-[#876876]">${escapeHtml(description)}</p></div>`;
}

function insightCard(title, description, toneClass) {
    return `<div class="rounded-[24px] px-4 py-4 ${toneClass}"><p class="text-[11px] font-semibold uppercase tracking-[0.2em] opacity-70">${title}</p><p class="mt-2 text-sm leading-7">${description}</p></div>`;
}

async function handleDeduction(ticketId, button) {
    const amountInput = document.querySelector(`[data-ticket-amount="${ticketId}"]`);
    const amount = Number.parseInt(amountInput?.value || "1", 10);
    if (!Number.isInteger(amount) || amount < 1) {
        showBanner(statusBannerEl, "차감 횟수는 1 이상이어야 합니다.", "error");
        amountInput?.focus();
        return;
    }

    button.disabled = true;
    const previousLabel = button.textContent;
    button.textContent = "처리 중...";

    try {
        const data = await apiJson(`/api/tickets/${ticketId}/deduct`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ amount }),
        });
        await fetchCustomers(state.search, { silent: true });
        if (state.activeCustomer) {
            await openCustomerModal(state.activeCustomer.id, { silent: true });
        }
        showBanner(statusBannerEl, data.message, "success");
    } catch (error) {
        showBanner(statusBannerEl, error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = previousLabel;
    }
}

// Customer detail data is fetched on demand to keep the dashboard fast.
async function openCustomerModal(customerId, options = {}) {
    const { silent = false } = options;
    try {
        if (!silent) {
            showBanner(statusBannerEl, "고객 상세 정보를 불러오는 중입니다.", "loading");
        }
        const data = await apiJson(`/api/customers/${customerId}`);
        state.activeCustomer = data.customer;
        modalContentEl.innerHTML = renderCustomerModal(data.customer);
        modalEl.hidden = false;
        modalEl.classList.remove("modal-hidden");
        modalEl.setAttribute("aria-hidden", "false");
        document.body.classList.add("overflow-hidden");
        if (!silent) {
            hideBanner(statusBannerEl);
        }
    } catch (error) {
        showBanner(statusBannerEl, error.message, "error");
    }
}

function closeCustomerModal() {
    state.activeCustomer = null;
    modalEl.classList.add("modal-hidden");
    modalEl.hidden = true;
    modalEl.setAttribute("aria-hidden", "true");
    document.body.classList.remove("overflow-hidden");
}

function renderCustomerModal(customer) {
    const visitMarkup = customer.visit_records.length
        ? customer.visit_records.map((visit) => `
            <article class="rounded-[24px] bg-white/85 p-4 ring-1 ring-[#f1dde2]">
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <h4 class="font-semibold text-[#553040]">${escapeHtml(visit.treatment_name)}</h4>
                    <span class="rounded-full bg-[#fff5eb] px-3 py-1 text-xs font-semibold text-[#8b6732] ring-1 ring-[#f0debe]">${formatDate(visit.visit_date)}</span>
                </div>
                <p class="mt-2 text-sm text-[#7f6471]">${escapeHtml(visit.staff_name || "담당자 미기록")}</p>
                <p class="mt-2 text-sm leading-6 text-[#6d5562]">${escapeHtml(visit.notes || "메모 없음")}</p>
            </article>
        `).join("")
        : `<div class="rounded-[24px] bg-white/80 p-4 text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">방문 기록이 없습니다.</div>`;

    const consentMarkup = customer.consents.length
        ? customer.consents.map((consent) => renderConsentCard(consent)).join("")
        : `<div class="rounded-[24px] bg-white/80 p-4 text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">작성된 동의서가 없습니다.</div>`;

    const ticketMarkup = customer.tickets.length
        ? customer.tickets.map((ticket) => `
            <article class="rounded-[24px] bg-white/85 p-4 ring-1 ring-[#f1dde2]">
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <h4 class="font-semibold text-[#553040]">${escapeHtml(ticket.title)}</h4>
                    <span class="rounded-full bg-[#fff6e8] px-3 py-1 text-xs font-semibold text-[#8a6730]">${expiryLabel(ticket.days_until_expiry)}</span>
                </div>
                <p class="mt-2 text-sm text-[#7f6471]">잔여 ${ticket.remaining_sessions} / 총 ${ticket.total_sessions}</p>
            </article>
        `).join("")
        : `<div class="rounded-[24px] bg-white/80 p-4 text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">보유 티켓이 없습니다.</div>`;

    return `
        <div class="fade-up rounded-[34px] bg-[linear-gradient(180deg,rgba(255,250,251,.98),rgba(255,245,247,.96))] p-5 shadow-card sm:p-6">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <p class="text-xs font-semibold uppercase tracking-[0.2em] text-[#aa8393]">Customer Detail</p>
                    <h3 class="mt-2 font-display text-4xl text-[#53263a]">${escapeHtml(customer.name)}</h3>
                    <div class="mt-3 flex flex-wrap gap-2 text-sm text-[#7f6471]">
                        <span class="rounded-full bg-white/80 px-4 py-2 ring-1 ring-[#f1dde2]">${escapeHtml(customer.phone)}</span>
                        <span class="rounded-full bg-white/80 px-4 py-2 ring-1 ring-[#f1dde2]">${escapeHtml(customer.grade)}</span>
                        <span class="rounded-full bg-[#fff5eb] px-4 py-2 text-[#8b6732] ring-1 ring-[#f0debe]">잔여 ${customer.total_remaining_sessions}회</span>
                    </div>
                    <p class="mt-4 max-w-2xl text-sm leading-7 text-[#6d5562]">${escapeHtml(customer.memo || "메모 없음")}</p>
                </div>
                <button type="button" data-close-modal="true" class="rounded-full bg-white px-4 py-2 text-sm font-semibold text-[#7b5567] ring-1 ring-[#ead7b8]">닫기</button>
            </div>

            <div class="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <section class="space-y-4">
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#aa8393]">남은 티켓</p>
                        <div class="mt-3 space-y-3">${ticketMarkup}</div>
                    </div>
                    <div>
                        <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#aa8393]">과거 방문 기록</p>
                        <div class="mt-3 space-y-3">${visitMarkup}</div>
                    </div>
                </section>

                <section>
                    <p class="text-xs font-semibold uppercase tracking-[0.18em] text-[#aa8393]">작성된 동의서</p>
                    <div class="mt-3 space-y-3">${consentMarkup}</div>
                </section>
            </div>
        </div>
    `;
}

function renderConsentCard(consent) {
    const preview = consent.signature_available
        ? `<img src="/api/consents/${consent.id}/signature" alt="서명 미리보기" class="signature-preview h-28 w-full rounded-[18px] object-contain ring-1 ring-[#f1dde2]">`
        : `<div class="signature-preview flex h-28 items-center justify-center rounded-[18px] text-sm text-[#8a6978] ring-1 ring-[#f1dde2]">서명 이미지 없음</div>`;

    return `
        <article class="rounded-[24px] bg-white/85 p-4 ring-1 ring-[#f1dde2]">
            <div class="flex flex-wrap items-center justify-between gap-2">
                <h4 class="font-semibold text-[#553040]">${escapeHtml(consent.treatment_name)}</h4>
                <span class="rounded-full bg-[#fff5eb] px-3 py-1 text-xs font-semibold text-[#8b6732] ring-1 ring-[#f0debe]">${formatDateTime(consent.signed_at)}</span>
            </div>
            <div class="mt-3">${preview}</div>
            <p class="mt-3 text-sm leading-6 text-[#6d5562]">${joinSafeLines(consent.agreement_items)}</p>
            ${consent.notes ? `<p class="mt-3 text-sm text-[#8a6978]">${escapeHtml(consent.notes)}</p>` : ""}
            <a href="/api/consents/${consent.id}/pdf" class="mt-4 inline-flex rounded-full bg-gradient-to-r from-[#6b334b] to-[#c09a5c] px-4 py-2 text-sm font-semibold text-white">PDF 다운로드</a>
        </article>
    `;
}

searchInputEl.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    clearTimeout(state.searchTimer);
    state.searchTimer = window.setTimeout(() => fetchCustomers(state.search), 250);
});

customerListEl.addEventListener("click", (event) => {
    const target = getEventElement(event);
    if (!target) return;

    const stepButton = target.closest("[data-step]");
    if (stepButton) {
        const ticketId = stepButton.dataset.ticketId;
        const input = document.querySelector(`[data-ticket-amount="${ticketId}"]`);
        const min = Number.parseInt(input.min, 10);
        const max = Number.parseInt(input.max, 10);
        const step = Number.parseInt(stepButton.dataset.step, 10);
        const currentValue = Number.parseInt(input.value || "1", 10);
        input.value = String(Math.min(max, Math.max(min, currentValue + step)));
        return;
    }

    const deductButton = target.closest("[data-deduct-ticket]");
    if (deductButton) {
        handleDeduction(deductButton.dataset.deductTicket, deductButton);
        return;
    }

    if (target.closest("[data-no-modal]")) return;
    const card = target.closest("[data-customer-card]");
    if (card) {
        openCustomerModal(card.dataset.customerCard);
    }
});

modalEl.addEventListener("click", (event) => {
    const target = getEventElement(event);
    if (!target) return;

    if (target.closest("[data-close-modal]")) {
        event.preventDefault();
        event.stopPropagation();
        closeCustomerModal();
        return;
    }

    if (target === modalEl) {
        closeCustomerModal();
    }
});

modalCloseEls.forEach((button) => {
    button.addEventListener("click", closeCustomerModal);
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modalEl.classList.contains("modal-hidden")) {
        closeCustomerModal();
    }
});

logoutEl?.addEventListener("click", logout);

fetchCustomers();
