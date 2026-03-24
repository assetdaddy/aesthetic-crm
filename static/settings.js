import { apiJson, escapeHtml, logout, showBanner } from "/static/common.js";

const bannerEl = document.getElementById("settings-banner");
const overviewEl = document.getElementById("settings-overview");
const logoutEl = document.getElementById("logout-button");

async function fetchSettings() {
    try {
        showBanner(bannerEl, "관리자 설정 정보를 불러오는 중입니다.", "loading");
        const data = await apiJson("/api/admin/settings");
        overviewEl.innerHTML = `
            <article class="luxury-stroke rounded-[28px] bg-white/80 p-5 shadow-card">
                <p class="text-xs uppercase tracking-[0.18em] text-[#a78392]">Admin</p>
                <p class="mt-3 text-2xl font-semibold text-[#5a2e42]">${escapeHtml(data.username)}</p>
                <p class="mt-2 text-sm text-[#8b6b79]">버전 ${escapeHtml(data.app_version)}</p>
            </article>
            <article class="luxury-stroke rounded-[28px] bg-white/80 p-5 shadow-card">
                <p class="text-xs uppercase tracking-[0.18em] text-[#a78392]">Database</p>
                <p class="mt-3 text-2xl font-semibold text-[#5a2e42]">${escapeHtml(data.database_file)}</p>
                <p class="mt-2 text-sm text-[#8b6b79]">${data.database_size_kb} KB</p>
            </article>
            <article class="luxury-stroke rounded-[28px] bg-white/80 p-5 shadow-card">
                <p class="text-xs uppercase tracking-[0.18em] text-[#a78392]">Records</p>
                <p class="mt-3 text-2xl font-semibold text-[#5a2e42]">${data.customer_count} 고객 / ${data.consent_count} 동의서</p>
                <p class="mt-2 text-sm text-[#8b6b79]">방문 기록 ${data.visit_count}건</p>
            </article>
            <article class="luxury-stroke rounded-[28px] bg-white/80 p-5 shadow-card">
                <p class="text-xs uppercase tracking-[0.18em] text-[#a78392]">Backup</p>
                <p class="mt-3 text-2xl font-semibold text-[#5a2e42]">${escapeHtml(data.backup_directory)}</p>
                <p class="mt-2 text-sm text-[#8b6b79]">버튼 클릭 시 즉시 스냅샷 다운로드</p>
            </article>
        `;
        showBanner(bannerEl, "관리자 설정이 준비되었습니다.", "success");
    } catch (error) {
        showBanner(bannerEl, error.message, "error");
    }
}

logoutEl?.addEventListener("click", logout);
fetchSettings();
