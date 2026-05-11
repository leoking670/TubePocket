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
    const label = "在 TubePocket 中打开此视频";
    button.setAttribute("aria-label", label);
    button.title = label;
    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    for (const d of ["M12 3v12", "m7 10 5 5 5-5", "M5 21h14"]) {
      const path = document.createElementNS(svgNs, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    }
    button.appendChild(svg);
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
      display: "inline-grid",
      placeItems: "center",
      width: "44px",
      height: "44px",
      padding: "0",
      border: "1px solid rgba(255,255,255,.18)",
      borderRadius: "50%",
      background: "rgba(17,24,39,.86)",
      backdropFilter: "blur(6px)",
      webkitBackdropFilter: "blur(6px)",
      boxShadow: "0 6px 18px rgba(15,23,42,.28)",
      color: "#fff",
      cursor: "pointer",
    });
  }

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${BUTTON_ID} {
        transition: transform .18s ease, background-color .18s ease, box-shadow .18s ease;
      }
      #${BUTTON_ID} svg {
        width: 22px;
        height: 22px;
        display: block;
      }
      #${BUTTON_ID}:hover {
        background: rgba(17,24,39,.96);
        box-shadow: 0 10px 24px rgba(15,23,42,.36);
        transform: translateY(-1px) scale(1.04);
      }
      #${BUTTON_ID}:active {
        transform: translateY(0) scale(0.96);
      }
      #${BUTTON_ID}:focus-visible {
        outline: 2px solid #ffffff;
        outline-offset: 2px;
      }
      @media (max-width: 720px) {
        #${BUTTON_ID} {
          right: 12px;
          bottom: 72px;
          width: 36px;
          height: 36px;
        }
        #${BUTTON_ID} svg {
          width: 18px;
          height: 18px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function injectButton() {
    if (!document.body) {
      return;
    }
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
  window.addEventListener("DOMContentLoaded", tick);
  window.addEventListener("load", tick);
  document.addEventListener("yt-navigate-finish", tick);
  new MutationObserver(tick).observe(document.documentElement, { childList: true, subtree: true });
  tick();
})();
