import { showBanner } from "/static/common.js";

const formEl = document.getElementById("login-form");
const bannerEl = document.getElementById("login-banner");

formEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(formEl);
    const payload = {
        username: String(formData.get("username") || "").trim(),
        password: String(formData.get("password") || ""),
    };

    if (!payload.username || !payload.password) {
        showBanner(bannerEl, "아이디와 비밀번호를 모두 입력해 주세요.", "error");
        return;
    }

    try {
        showBanner(bannerEl, "로그인 중입니다.", "loading");
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "로그인에 실패했습니다.");
        }
        const params = new URLSearchParams(window.location.search);
        const next = params.get("next") || "/";
        window.location.href = next;
    } catch (error) {
        showBanner(bannerEl, error.message, "error");
    }
});
