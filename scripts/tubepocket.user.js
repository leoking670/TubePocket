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
    button.textContent = "TubePocket";
    button.title = "Open this video in TubePocket";
    button.addEventListener("click", openTubePocket);
    button.style.border = "1px solid var(--yt-spec-10-percent-layer, #d0d0d0)";
    button.style.borderRadius = "18px";
    button.style.padding = "0 14px";
    button.style.height = "36px";
    button.style.cursor = "pointer";
    button.style.font = "inherit";
    button.style.background = "var(--yt-spec-badge-chip-background, #f2f2f2)";
    button.style.color = "var(--yt-spec-text-primary, #0f0f0f)";
    return button;
  }

  function findActionBar() {
    return (
      document.querySelector("#top-level-buttons-computed") ||
      document.querySelector("ytd-menu-renderer #top-level-buttons-computed") ||
      document.querySelector("#actions-inner") ||
      document.querySelector("#menu-container")
    );
  }

  function injectButton() {
    if (document.getElementById(BUTTON_ID) || !currentVideoUrl()) {
      return;
    }
    const actionBar = findActionBar();
    if (!actionBar) {
      return;
    }
    actionBar.appendChild(makeButton());
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

