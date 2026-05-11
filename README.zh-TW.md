# TubePocket

[English](README.md)

TubePocket 是一個採用 `GPL-3.0-only` 授權的 Windows 桌面工具，用來透過 `yt-dlp` 視覺化選擇並下載 YouTube 影片、音訊或字幕。

一般使用者的入口是打包後的 `TubePocket.exe`。原始碼僅供審閱、開發與自行建置使用。從原始碼執行時，程式會刻意停用 `tubepocket://` URL Scheme 註冊功能。

## 需求

- Windows
- `yt-dlp` 已加入 `PATH`
- `ffmpeg` 已加入 `PATH`，用於影片合併與字幕轉換
- 建議將 `deno` 加入 `PATH`，用於 YouTube JavaScript challenge 解題
- Chrome 或 Edge，並安裝 Tampermonkey
- 開發或自行建置時需要 Python 3.13 與 `uv`

TubePocket 不會內建或隨附 `yt-dlp`、`ffmpeg`。

如果你使用 `uv tool` 安裝 `yt-dlp`，建議使用：

```powershell
uv tool install --force "yt-dlp[default]"
```

單純執行 `uv tool install yt-dlp` 只會安裝 PyPI 基礎套件。依照 yt-dlp 的 EJS 文件，YouTube challenge 解題需要 `default` dependency group，因為它包含配套的 `yt-dlp-ejs` 套件。TubePocket 只做本機工具偵測；它不會自動安裝 JS runtime、下載 EJS 元件，也不會自動修改代理設定。

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
- 字幕：選擇一個字幕。作者上傳的字幕會全部顯示；自動產生字幕只顯示英文（`en` 與 `en-*`）。輸出格式可以是原始格式、`srt`、`vtt` 或純文字 `text`。純文字選項會在下載後移除時間軸與字幕標記。

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
- `yt-dlp --cookies-from-browser <browser>`，在 GUI 中從瀏覽器清單選擇
- `yt-dlp --cookies <cookies.txt>`

Cookie 設定會儲存在使用者本機應用程式資料目錄下的一個小型 JSON 設定檔。

當 TubePocket 從瀏覽器被 URL Scheme 拉起，且已儲存的 cookie 設定不完整時，應用程式會先停止，不會直接呼叫 `yt-dlp`。它會切到狀態頁並顯示明確警告，例如 `cookies.txt` 路徑不存在時會被提示為設定問題，而不是只顯示下載失敗。

## 代理與 YouTube JS Challenge

部分影片或使用 cookies 的請求可能需要解 YouTube JavaScript challenge。如果下載失敗，並出現 EJS、remote components、JavaScript challenge，或「Only images are available」相關警告，請先檢查 `yt-dlp` 安裝方式：

```powershell
uv tool install --force "yt-dlp[default]"
deno --version
yt-dlp -v --cookies-from-browser firefox --dump-single-json --no-playlist "URL"
```

如果你的網路需要代理，請在 shell 或 yt-dlp 設定檔中自行設定。TubePocket 不會自動修改代理設定。

PowerShell 範例：

```powershell
$env:HTTP_PROXY='http://127.0.0.1:7890'
$env:HTTPS_PROXY='http://127.0.0.1:7890'
```

yt-dlp 設定檔範例：

```text
--proxy http://127.0.0.1:7890
```

TubePocket 的狀態頁只做本機條件偵測。它會檢查 `yt-dlp`、`ffmpeg`、`deno` 是否能從 `PATH` 找到。對於 EJS 支援，如果你的 `yt-dlp` 是由 `uv tool` 管理，TubePocket 可以確認該環境中是否安裝 `yt-dlp-ejs`。如果你使用 GitHub releases 的獨立 `yt-dlp.exe` 或其他安裝方式，EJS 狀態可能顯示為 unknown，因為官方執行檔可能已經將必要元件內建。

TubePocket 啟動 `yt-dlp` 與 `ffmpeg` 時不會另外開啟控制台視窗。讀取影片資訊與下載期間，GUI 會顯示處理中的狀態提示。

## 法律與授權

TubePocket 採用 `GPL-3.0-only` 授權。它是用來呼叫使用者自行安裝工具的本機介面。使用者需自行確認有權下載相關內容，並自行遵守 YouTube 條款、第三方工具授權與所在地法律。

本專案不散佈 `yt-dlp` 或 `ffmpeg`。
