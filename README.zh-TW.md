# TubePocket

[English](README.md)

TubePocket 是一個採用 `GPL-3.0-only` 授權的 Windows 桌面工具，用來透過 `yt-dlp` 視覺化選擇並下載 YouTube 影片、音訊或字幕。

一般使用者的入口是打包後的 `TubePocket.exe`。原始碼僅供審閱、開發與自行建置使用。從原始碼執行時，程式會刻意停用 `tubepocket://` URL Scheme 註冊功能。

## 需求

- Windows
- `yt-dlp` 已加入 `PATH`
- `ffmpeg` 已加入 `PATH`，用於影片合併與字幕轉換
- Chrome 或 Edge，並安裝 Tampermonkey
- 開發或自行建置時需要 Python 3.13 與 `uv`

TubePocket 不會內建或隨附 `yt-dlp`、`ffmpeg`。

## 開發

```powershell
uv sync --extra dev
uv run pytest
```

僅供檢查與開發用途啟動 GUI：

```powershell
uv run tubepocket-dev
```

開發模式 GUI 可以檢查邏輯與載入 URL，但不會註冊 `tubepocket://` 協定。協定註冊只支援 PyInstaller 建置出的執行檔。

如果你的環境使用本機代理，例如 `127.0.0.1:7890`，且 `uv sync` 發生 TLS 或連線錯誤，可以在目前 PowerShell 工作階段暫時指定 HTTP 代理：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
uv sync --extra dev
```

## 建置

```powershell
uv sync --extra dev
uv run pyinstaller tubepocket.spec
```

打包後的應用程式會輸出到：

```text
dist\TubePocket\TubePocket.exe
```

執行該檔案後，可以在狀態頁註冊或反註冊 URL Scheme。

## 瀏覽器腳本

將 `scripts/tubepocket.user.js` 安裝到 Tampermonkey。在 YouTube 影片頁面中，腳本會在操作區加入 TubePocket 按鈕。按鈕會開啟：

```text
tubepocket://open?url=<encoded-canonical-youtube-url>
```

播放清單參數會被忽略。桌面端只會收到目前影片的 URL。

## 協定註冊

TubePocket 只會寫入目前使用者的登錄檔 hive：

```text
HKCU\Software\Classes\tubepocket
```

應用程式提供：

- 註冊：將 `tubepocket://` 指向目前打包後的 `TubePocket.exe`。
- 重新註冊：當 exe 移動位置或舊註冊失效時，覆寫為目前位置。
- 反註冊：移除 `tubepocket` 協定鍵，適用於解除安裝或修復殘留註冊。

不需要系統管理員權限。

## 下載行為

每個下載任務只會下載一種類型：

- 影片：選擇一個影片格式。如果該格式只有影像沒有聲音，TubePocket 會選擇最相容的 audio-only 格式，並交由 `yt-dlp` 合併。
- 音訊：選擇一個 audio-only 格式。
- 字幕：選擇一個字幕。作者上傳的字幕會全部顯示；自動產生字幕只顯示英文（`en` 與 `en-*`）。輸出格式可以是原始格式、`srt` 或 `vtt`。

檔案會儲存到：

```text
%USERPROFILE%\Downloads\TubePocket
```

固定檔名模板為：

```text
%(uploader)s - %(title)s [%(id)s].%(ext)s
```

## Cookies

應用程式支援三種 cookies 模式：

- 不使用 cookies
- `yt-dlp --cookies-from-browser <browser>`
- `yt-dlp --cookies <cookies.txt>`

Cookie 設定會儲存在使用者本機應用程式資料目錄下的一個小型 JSON 設定檔。

## 法律與授權

TubePocket 採用 `GPL-3.0-only` 授權。它是用來呼叫使用者自行安裝工具的本機介面。使用者需自行確認有權下載相關內容，並自行遵守 YouTube 條款、第三方工具授權與所在地法律。

本專案不散佈 `yt-dlp` 或 `ffmpeg`。
