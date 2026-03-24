// Shared browser helpers used across dashboard, consent, login, and settings.

export function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

export function formatDate(value) {
    if (!value) return "기록 없음";
    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) return value;
    return new Intl.DateTimeFormat("ko-KR", {
        year: "numeric",
        month: "short",
        day: "numeric",
    }).format(new Date(year, month - 1, day));
}

export function formatDateTime(value) {
    if (!value) return "-";
    const normalized = value.replace(" ", "T");
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat("ko-KR", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(parsed);
}

export function expiryLabel(daysUntilExpiry) {
    if (daysUntilExpiry === null || daysUntilExpiry === undefined) return "만료일 미정";
    if (daysUntilExpiry < 0) return `${Math.abs(daysUntilExpiry)}일 지남`;
    if (daysUntilExpiry === 0) return "오늘 만료";
    return `${daysUntilExpiry}일 남음`;
}

export function joinSafeLines(lines) {
    return lines.map((line) => escapeHtml(line)).join("<br>");
}

export function showBanner(element, message, tone = "success", prefixClass = "") {
    const toneMap = {
        success: "bg-[#fff7ef] text-[#7a5b2e] ring-1 ring-[#f1debf]",
        error: "bg-[#fff1f4] text-[#874a61] ring-1 ring-[#f2d8df]",
        loading: "bg-white/80 text-[#7f6471] ring-1 ring-[#f0dfe5]",
    };
    element.className = `${prefixClass} rounded-2xl px-4 py-3 text-sm font-medium ${toneMap[tone] || toneMap.success}`.trim();
    element.textContent = message;
    element.classList.remove("hidden");
}

export function hideBanner(element) {
    element.classList.add("hidden");
}

export async function apiFetch(url, options = {}) {
    const response = await fetch(url, options);
    if (response.status === 401) {
        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
        throw new Error("로그인이 필요합니다.");
    }
    return response;
}

export async function apiJson(url, options = {}) {
    const response = await apiFetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch (error) {
        data = {};
    }

    if (!response.ok) {
        throw new Error(data.detail || data.message || "요청 처리 중 오류가 발생했습니다.");
    }
    return data;
}

export async function logout() {
    await apiJson("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
}
