// ==UserScript==
// @name         TubePocket
// @namespace    https://github.com/tubepocket/tubepocket
// @version      0.1.0
// @description  Open the current YouTube video in TubePocket.
// @author       TubePocket contributors
// @match        https://www.youtube.com/watch*
// @match        https://m.youtube.com/watch*
// @grant        none
// @license      GPL-3.0-only
// ==/UserScript==
// SPDX-License-Identifier: GPL-3.0-only

(function () {
  "use strict";

  const BUTTON_ID = "tubepocket-open-button";
  const STYLE_ID = "tubepocket-open-style";

  function currentVideoUrl() {
    const url = new URL(window.location.href);
    const videoId = url.searchParams.get("v");
    if (!videoId) {
      return null;
    }
    return `https://www.youtube.com/watch?v=${encodeURIComponent(videoId)}`;
  }

  function openTubePocket() {
    const videoUrl = currentVideoUrl();
    if (!videoUrl) {
      return;
    }
    window.location.href = `tubepocket://open?url=${encodeURIComponent(videoUrl)}`;
  }

  function makeButton() {
    const button = document.createElement("button");
    button.id = BUTTON_ID;
    button.type = "button";
    button.setAttribute("aria-label", "Open this video in TubePocket");
    button.title = "Open in TubePocket";
    button.innerHTML = `
      <span class="tp-mark">TP</span>
      <span class="tp-text">TubePocket</span>
    `;
    button.addEventListener("click", openTubePocket);
    applyButtonStyle(button);
    injectStyle();
    return button;
  }

  function applyButtonStyle(button) {
    Object.assign(button.style, {
      position: "fixed",
      right: "24px",
      bottom: "96px",
      zIndex: "2147483647",
      display: "inline-flex",
      alignItems: "center",
      gap: "8px",
      minWidth: "142px",
      height: "42px",
      padding: "0 14px 0 10px",
      border: "1px solid rgba(255,255,255,.22)",
      borderRadius: "21px",
      background: "linear-gradient(135deg, #2563eb, #7c3aed)",
      boxShadow: "0 10px 28px rgba(15,23,42,.28)",
      color: "#fff",
      cursor: "pointer",
      font: "600 14px/1.2 Arial, sans-serif",
      letterSpacing: "0",
    });
  function injectStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${BUTTON_ID}:hover {
        filter: brightness(1.06);
        transform: translateY(-1px);
      }
      #${BUTTON_ID}:active {
        transform: translateY(0);
      }
      #${BUTTON_ID} .tp-mark {
        display: inline-grid;
        place-items: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        background: rgba(255,255,255,.18);
        font-size: 11px;
      }
      #${BUTTON_ID} .tp-text {
        white-space: nowrap;
      }
      @media (max-width: 720px) {
        #${BUTTON_ID} {
          right: 12px;
          bottom: 72px;
          min-width: 42px;
          width: 42px;
          padding: 0;
          justify-content: center;
        }
        #${BUTTON_ID} .tp-text {
          display: none;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function injectButton() {
    const videoUrl = currentVideoUrl();
    const existing = document.getElementById(BUTTON_ID);
    if (!videoUrl) {
      if (existing) {
        existing.remove();
      }
      return;
    }
    if (!existing) {
      document.body.appendChild(makeButton());
    }
  }

  let lastHref = "";
  function tick() {
    if (window.location.href !== lastHref) {
      lastHref = window.location.href;
      const old = document.getElementById(BUTTON_ID);
      if (old) {
        old.remove();
      }
    }
    injectButton();
  }

  setInterval(tick, 1000);
  document.addEventListener("yt-navigate-finish", tick);
  tick();
})();
