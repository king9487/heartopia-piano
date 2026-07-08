# Heartopia Piano Studio 使用者指南

Heartopia Piano Studio 是一套 Windows 桌面工具，可將 YouTube、音訊檔或既有 MIDI 轉換、整理、分析、編輯並播放到《心動小鎮》（Heartopia）的鋼琴。預設 `Heartopia` 鍵盤設定是 37 鍵、MIDI note `48–84`，即 `C3–C6`。

本指南以目前 Tkinter UI 的實際功能為準。介面文字保留 English，說明使用繁體中文。

## 目錄

- [安裝與啟動](#安裝與啟動)
- [第一次使用](#第一次使用)
- [完整處理流程](#完整處理流程)
- [Playback Workflow](#playback-workflow)
- [Main 分頁](#main-分頁)
- [Import 分頁](#import-分頁)
- [Optimization 分頁](#optimization-分頁)
- [Playback 分頁](#playback-分頁)
- [Studio 分頁](#studio-分頁)
- [Analysis 分頁](#analysis-分頁)
- [所有輸出檔案](#所有輸出檔案)
- [建議設定](#建議設定)
- [FAQ](#faq)
- [Roadmap](#roadmap)

## 安裝與啟動

### 系統需求

- Windows
- 64-bit Python；目前 dependency 組合以 Python 3.11 最合適
- Python 安裝中的 Tcl/Tk（Tkinter）
- FFmpeg 與 FFprobe，且能從 `PATH` 執行
- YouTube 轉換需要網路
- 預設 `requirements.txt` 使用 NVIDIA CUDA 12.1 的 PyTorch；CPU-only 電腦需自行改裝相容的 PyTorch CPU build
- Studio 聲音預聽需要可用的 MIDI output（硬體 MIDI port 或 software synthesizer）

安裝 FFmpeg：

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

建立環境並安裝 dependency。注意：`setup.ps1` 會刪除並重建現有 `.venv`：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

啟動桌面 UI：

```powershell
.\.venv\Scripts\python.exe .\youtube_to_midi.py
```

也可雙擊 `start_ui.bat`。`start_cli.bat` 是 CLI 入口；本指南聚焦桌面 UI。

若要使用 **Experimental — OpenAI Optimizer**，啟動前設定：

```powershell
$env:OPENAI_API_KEY="你的 API key"
```

這個模式會把每個音符的時間、長度、音高與 velocity 送到 OpenAI API；API 不可用、回傳無效或未設定 key 時，程式會自動改用本機 Rule optimizer。

## 第一次使用

最穩妥的入門流程：

1. 保持頂端的 `Studio Mode`，以便看見完整介面。
2. 到 `Main` 選 `MIDI File`，按 `Import MIDI...` 匯入一個 `.mid` 或 `.midi`。
3. 到 `Import` 查看可播放比例；在 `Use Direct` 與 `Use Optimization` 欄選擇要保留的 Track/Channel 聲部。
4. 到 `Optimization` 選 `Balanced`。
5. 回到 `Import` 按 `Process Imported MIDI`。
6. 到 `Playback` 的 `MIDI source` 選 `Final MIDI`，再回 `Main` 按 `Play to Game`。
7. 倒數期間切回遊戲並把焦點放在鋼琴視窗；播放中按 `F8` 可停止。

若來源是 YouTube 或音訊，使用 `Demucs vocals only`、`no_vocals`、`Balanced` 作為起點即可。

## 完整處理流程

### YouTube / Audio 流程

```text
YouTube URL ──yt-dlp──┐
                     ├→ song.wav
Local Audio ─FFmpeg──┘
  → 可選的 Demucs source separation
  → 選定 stem
  → Basic Pitch transcription（Raw MIDI）
  → Clean 37-Key
  → Piano Arranger
  → AI Optimizer（Rule 或 Experimental OpenAI）
  → Pitch Correction
  → Final smoothing
  → Preview / Studio / Editor / Play to Game
```

1. YouTube 由 `yt-dlp` 取得音訊；本機音訊由 FFmpeg 轉為工作用 `song.wav`。
2. `Separation Mode` 決定是否以 Demucs 拆分音軌。
3. `Stem to Convert` 決定送入 Basic Pitch 的音軌。
4. Basic Pitch 將音訊轉錄為 Raw MIDI。
5. Cleanup、Arranger、Optimizer、Pitch Correction 與 Final smoothing 依序建立不同版本。
6. 若開啟 `Convert vocals MIDI` 且 separation 有產生 `vocals.wav`，vocals 也會另外跑一套相同 MIDI pipeline。

### External MIDI 流程

```text
原始 .mid/.midi
  → imported.mid（工作副本）
  → Track/Channel 選取與越界處理
  → selected_parts.mid
  → clean_37key.mid
  → piano_arranged_37key.mid
  → ai_optimized_37key.mid
  → pitch_corrected_37key.mid
  → final_37key.mid
  → 可選：transposed / chorus / edited
```

External MIDI 可先 Direct Play，不必處理完整 pipeline。勾選 Skip 時，程式仍會建立該階段的 pass-through copy，讓後續檔名與版本選單保持完整；`final_37key.mid` 一律會建立。

### Timing 與 MIDI 資訊保留

核心處理使用 MIDI ticks、原 PPQ 與 tempo map 計時，再重建 delta time。部分轉換階段會把內容整理成單一 note track，因此原始 Track、Channel、program、sustain/control change 等演奏資訊不保證全部保留。需要原始事件時請使用 `Full Imported MIDI` 或 Import 的 `Play Original`。

## Playback Workflow

視窗最上方有兩個 radio button；它們只改變 UI 顯示方式，不改寫 MIDI。

| 選項 | 實際效果 | 適合情境 |
|---|---|---|
| `Quick Play` | 只顯示 Main、Import、Playback，並隱藏來源選擇、進階 conversion/import/compare/log 設定；切換時回到 Main | 已經選好來源與設定，只想快速 `Play to Game` |
| `Studio Mode` | 顯示全部六個分頁與所有控制項；預設模式 | 第一次使用、轉換、分析、編輯與除錯 |

`Quick Play` 不會重設先前設定。若要換來源、查看 Import 分析或調整完整參數，切回 `Studio Mode`。

## Main 分頁

![Main 分頁截圖（待補）](docs/screenshots/main.png)

Main 用來選輸入、開始轉換、查看目前 MIDI，以及執行最常用動作。

### Input Source

| 選項 | 說明 |
|---|---|
| `YouTube Video` | 顯示 URL 欄與 `Convert URL`；下載並轉換單一 YouTube 影片，不處理 playlist |
| `Audio File` | 顯示 `Open Audio...`；選取本機音訊後立即開始轉換 |
| `MIDI File` | 顯示 `Import MIDI...`；先分析 MIDI，再由 Import 分頁決定 direct play 或 optimization |

### Convert：按鈕與欄位

| 控制項 | 功能 |
|---|---|
| `YouTube URL` | 貼上影片網址 |
| `Convert URL` | 下載 YouTube 音訊並執行目前 conversion/processing 設定 |
| `Open Audio...` | 選取音訊檔並開始轉換 |
| `Import MIDI...` | 選取 `.mid`/`.midi`，讀取 metadata、Track、Channel、program 與可播放比例；不會立刻跑 optimization |

### Conversion options

這些設定只適用於 YouTube / Audio。

| 類型 | 設定 | 值與作用 |
|---|---|---|
| Dropdown | `Demucs device` | `cuda:0` 使用第一張 CUDA GPU；`auto` 交由 Demucs 選擇；`cpu` 強制 CPU。預設會依環境偵測，否則為 `auto` |
| Checkbox | `Convert vocals MIDI` | 若 separation 提供 vocals，額外把 `vocals.wav` 轉成一套 vocals MIDI；預設 Off，會增加時間與輸出 |
| Dropdown | `Separation Mode` | 見下表 |
| Dropdown | `Stem to Convert` | `no_vocals`、`other`、`bass`、`drums`、`vocals`；選擇送往 Basic Pitch 的音軌 |

`Separation Mode`：

| 值 | 行為 | 可用 stem |
|---|---|---|
| `No separation` | 不執行 Demucs，原始 `song.wav` 直接視為所選 stem | 任一名稱都可選，但實際內容仍是完整原音訊 |
| `Demucs vocals only` | 產生 `vocals` 與 `no_vocals`；預設 | 僅 `vocals`、`no_vocals` |
| `Demucs 4-stem` | 產生 `vocals`、`drums`、`bass`、`other`；需要時混合後三者建立 `no_vocals` | 全部五種 |
| `Existing no_vocals` | 不重跑 Demucs，讀取既有 `separated/htdemucs/song/no_vocals.wav` | 只可選 `no_vocals`；檔案不存在會失敗 |

### Current MIDI / MIDI Actions

| 按鈕 | 功能 |
|---|---|
| `Open MIDI` | 直接開啟任意 MIDI 作為目前來源，不執行 Import 分析或 processing |
| `Open Converted` | 選取既有 `output/` 工作資料夾，載入其版本與報告 |
| `Preview` | 在 Main 的 log 列出目前 MIDI 最多前 80 個 mapped note on/off event；不播放聲音 |
| `Play to Game` | 依 Playback 設定，把 MIDI note 轉成電腦鍵盤事件送到目前有焦點的遊戲 |
| `Stop` | 停止正在進行的 conversion 或 game playback；播放也可按 `F8` |

Main 底部 log 顯示進度、路徑、Preview event 與錯誤摘要；status 顯示目前工作狀態。`Current MIDI` 路徑是 Main、Playback、Studio、Analysis 共用的目前版本。

## Import 分頁

![Import 分頁截圖（待補）](docs/screenshots/import.png)

Import 只在先用 `Import MIDI...` 選檔後有內容。

### Original MIDI 按鈕

| 按鈕 | 功能 |
|---|---|
| `Preview Original` | 對完整原始 MIDI 套用目前 Preview/Cleanup mapping，將最多前 80 個 event 列到 log；不播放聲音 |
| `Play Original` | 把完整原始 MIDI event 直接送到遊戲；使用 Speed 與 Focus delay，但不套用 Track/Channel selection、Cleanup、Transpose、Chord gap 或 Min hold |
| `Open Original` | 用 Windows 預設應用程式開啟匯入的原始 MIDI 檔 |

### 檔案資訊

| 欄位 | 意義 |
|---|---|
| `Filename` | 原始檔名 |
| `Duration` | MIDI 計算出的總長度 |
| `Tempo` | 第一個 tempo event 的 BPM；沒有 event 時顯示未知 |
| `Key` | 依所有 note 推測的 major/minor key |
| `Tracks` | 實體 MIDI track 數 |
| `PPQ` | pulses per quarter note |
| `Total Notes` | 完整 note-on/note-off 配對數 |
| `Playable Notes` | 位於預設 Heartopia `C3–C6` map 內的音符數 |
| `Out-of-range Notes` | 位於該 map 外的音符數 |
| `Playable Percentage` | 可播放音符占比 |
| `Recommended` | UI 依可播放比例給出的處理建議 |

### Source Tracks 與 Channel 表

每個真正可選聲部是 `Track + Channel`，不是只看 Track。Channel 在檔案內為 `0–15`，一般介面顯示為 MIDI `1–16`。

| 欄位 | 說明 |
|---|---|
| `Track / Channel` | 實體 Track 與 Channel 組合 |
| `Use Direct` | 點該欄切換臨時 `selected_direct.mid` 的內容；此版本會在 Playback 顯示為 `Imported MIDI`，可設為 Current 或用 A/B 播放。Import 上方的 `Preview/Play Original` 仍使用完整原檔 |
| `Use Optimization` | 點該欄切換是否寫入 `selected_parts.mid` 並進入 processing pipeline |
| `Program / Instrument` | General MIDI program number 與樂器名稱；無明示 program 時可能顯示 default |
| `Notes` | 該聲部音符數 |
| `Playable` / `Out of range` | Heartopia map 內／外數量 |
| `Min` / `Max` | 最低／最高 MIDI note |
| `Track Events` | 該 track 是否包含 tempo、meta、control 或 program 等事件摘要 |

右側 `Global Notes by Channel` 是跨 Track 的 Channel 統計，只供參考，不能在這裡選取。

### Selected-part out-of-range handling

這組 radio button 同時影響 Direct selection 的臨時檔，以及 `Process Imported MIDI` 建立的 `selected_parts.mid`。

| 選項 | 行為 |
|---|---|
| `Keep original (direct play)` | 保留原音高；超出 game map 的音符可能無法送出。預設 |
| `Octave shift into playable range` | 以八度移動到可播放範圍 |
| `Drop out-of-range notes` | 移除越界音符 |

### Optimize for Heartopia

| 類型 | 控制項 | 功能 |
|---|---|---|
| Button | `Process Imported MIDI` | 以 `Use Optimization` 選取結果和 Optimization 分頁設定執行完整 external MIDI pipeline |
| Checkbox | `Skip Cleanup` | 不轉換 Cleanup，直接複製 `selected_parts.mid` 成 `clean_37key.mid` |
| Checkbox | `Skip Piano Arranger` | 不重新編曲，直接複製上一階段 |
| Checkbox | `Skip AI Optimizer` | 不執行 optimizer，直接複製上一階段 |
| Checkbox | `Skip Pitch Correction` | 不校音，直接複製上一階段 |
| Checkbox | `Direct Preview after processing` | 完成後立即以 game-keyboard playback 播放 Final；先準備好切回遊戲 |

所有 checkbox 預設 Off。至少要選一個 `Use Optimization` 聲部才能處理。

## Optimization 分頁

![Optimization 分頁截圖（待補）](docs/screenshots/optimization.png)

### Preset dropdown

選 Preset 會立即覆寫 Cleanup、Arranger 與 Optimizer 控制值。

| Preset | Min note | Velocity | Max simultaneous | Range | Melody notes / window | Style | Optimizer |
|---|---:|---:|---:|---|---|---|---|
| `Safe` | 10 ms | 3 | 0 | `octave_shift` | 3 / 100 ms | `original` | `None` |
| `Balanced` | 35 ms | 12 | 0 | `smart` | 3 / 80 ms | `piano_cover` | `Rule` |
| `Aggressive` | 70 ms | 24 | 2 | `smart` | 2 / 50 ms | `piano_cover` | `Rule` |
| `Piano Cover` | 35 ms | 12 | 2 | `smart` | 2 / 80 ms | `piano_cover` | `Rule` |

`Max simultaneous notes = 0` 表示不設此上限，不是零音符。

### MIDI Cleanup

| 類型 | 設定 | 範圍 | 說明 |
|---|---|---:|---|
| Spinbox | `Min note ms` | 0–500，step 5 | 移除短於門檻的音符 |
| Spinbox | `Velocity threshold` | 0–127 | 移除 velocity 低於門檻的弱音 |
| Spinbox | `Max simultaneous notes` | 0–12 | 限制同一時間窗可留的音符；`0` 不限制 |
| Dropdown | `Range mode` | `smart`, `drop`, `octave_shift` | `drop` 移除越界音；`octave_shift` 以八度塞入範圍；`smart` 依旋律區域與候選位置處理 |
| Checkbox | `Melody only` | Off/On | Cleanup 階段以時間窗偏向保留高音旋律，捨棄大部分伴奏 |
| Button | `Rebuild Clean` | — | 從可用 Raw MIDI 重建 Clean，並連帶重建下游 Arranged、Optimizer、Pitch、Final |

### Piano Arranger / Arrangement Style

| 類型 | 設定 | 值 | 說明 |
|---|---|---|---|
| Spinbox | `Melody notes` | 1–3 | 每個時間群組最多保留的重點音符數 |
| Spinbox | `Melody window ms` | 20–250，step 10 | 相近 onset 被視為同一組的時間寬度 |
| Dropdown | `Arrangement style` | `original` | 以 Cleanup 結果為主，不做 melody/piano-cover 重編 |
|  |  | `melody_only` | 抽取持續的最高旋律線，結果接近單音旋律 |
|  |  | `piano_cover` | 保留主旋律，加入受限的 bass/harmony，最多三音 |
| Button | `Rebuild Piano Arranged` | — | 重建 Arranger 與其後所有階段，不先強制重建已有 Clean |

Cleanup 的 `Melody only` 與 `Arrangement style = melody_only` 是不同階段；通常只需選其中一種。

### AI Optimizer

| Dropdown 值 | 實際行為 |
|---|---|
| `Rule` | 使用本機規則依 duration、velocity、音程連續性與每窗上限挑選音符 |
| `OpenAI` | **Experimental**。以 8 秒 chunk 呼叫 OpenAI Responses API；任何錯誤會無提示地回退至 Rule |
| `None` | 不呼叫 OpenAI。依目前實作，pipeline 仍會經過本機 rules 並產生 `ai_optimized_37key.mid`，不是完全 bypass；external MIDI 要真正原樣傳遞此階段請用 `Skip AI Optimizer` |

`Optimize MIDI` 從目前可用的 Clean/Raw 來源執行 Arranger、Optimizer、Pitch Correction 與 Final。若同時選 `original + None`，按鈕會提示需改用 Rule/OpenAI 或簡化編曲風格。

### Pitch Correction

Pitch Correction 沒有獨立參數。它會偵測 major/minor scale，對短、弱、離調或突跳音符做移除／鄰近音修正，再交給 Final smoothing。

`Rebuild Final` 優先重用現有 `pitch_corrected_37key.mid`，只重建 Final；缺 prerequisite 時才補建上游。

### Key Transpose

| 類型 | 設定 | 說明 |
|---|---|---|
| Dropdown | `Original Key` | `Auto Detect` 或 12 個 major key 名稱；指定來源大調 |
| Dropdown | `Target Key` | `Original` 或 12 個 major key；選取後立即產生 `transposed_37key.mid` |
| Status | `Detected Key` | 顯示使用／偵測到的原調 |
| Status | `Transpose` | 顯示實際半音位移 |

Key Transpose 作用於目前 MIDI 並寫新檔；若目前已選 `transposed_37key.mid`，程式會要求先選非 transposed 版本。它不同於 Playback 的即時 `Transpose`。

## Playback 分頁

![Playback 分頁截圖（待補）](docs/screenshots/playback.png)

### Current MIDI source / version

| 類型 | 控制項 | 功能 |
|---|---|---|
| Radio | `Vocals MIDI` | 顯示 vocals pipeline 的版本；只有開啟 vocals conversion 且成功產生時可用 |
| Radio | `Accompaniment MIDI` | 顯示主要 selected stem pipeline；預設 |
| Dropdown | `Converted` | 列出 `output/` 下可辨識的既有 conversion folder |
| Button | `Refresh` | 重新掃描 conversion folder 清單 |
| Button | `Load` | 載入 dropdown 所選資料夾 |
| Dropdown | `MIDI source` | 選目前要 Preview、Studio、編輯或 Play 的版本；只列出實際存在的檔案 |

External MIDI 常見版本是 Full Imported、Imported/Direct selection、Selected Parts、Clean、Piano Arranged、AI Optimized、Pitch Corrected、Final、Edited。Audio 常見版本另有 Raw、Piano Cover、Transposed。

### A/B Compare

| 控制項 | 功能 |
|---|---|
| `A source` / `B source` dropdown | 分別選兩個已存在版本 |
| `Play A` / `Play B` | 以 game-keyboard playback 播放該版本 |
| `Set A as Current` / `Set B as Current` | 把該版本設為全 UI 的 Current MIDI |
| `Stop` | 停止 A/B game playback |

Imported/Selected Parts 在 A/B playback 會走 original-event 模式，因此不套用 Cleanup、Chord gap 與 Min hold；其他 processing 版本使用一般 playback 設定。

### Playback Settings

| 類型 | 設定 | 範圍／預設 | 說明 |
|---|---|---|---|
| Checkbox | `Always on top` | On | 讓 UI 視窗保持最上層；立即生效 |
| Spinbox | `Speed` | 0.25–3.0 / `1.0` | game playback 倍速；不改檔案 |
| Spinbox | `Focus delay` | 1–10 秒 / `3` | 送出第一鍵前的倒數時間 |
| Spinbox | `Transpose` | -36–36 / `0` | game playback 即時半音位移；不寫 MIDI |
| Spinbox | `Chord gap ms` | 0–80 / `18` | 把同時音符錯開送出，降低遊戲漏和弦機率 |
| Spinbox | `Min hold ms` | 20–250 / `75` | 每個電腦鍵至少按住多久 |
| Dropdown | `Keyboard Profile` | 見下表 / `Heartopia` | 決定 processing 與 playback 的 note map；更換後不會自動重建既有檔案 |

| Keyboard Profile | 音域 | 用途 |
|---|---|---|
| `Heartopia` | `C3–C6`，MIDI 48–84，37 鍵 | 遊戲預設 |
| `Standard 37-Key` | `C2–C5`，MIDI 36–72，37 鍵 | 一般 37-key layout |
| `Full Piano` | `A0–C8`，MIDI 21–108，88 鍵 | 分析／處理完整鋼琴範圍；不代表 Heartopia 可播放全部音符 |

`F8` 是全域停止 hotkey。game playback 使用 `keyboard` 套件送出電腦鍵盤事件，與 Studio 的 MIDI output playback 是兩套不同機制。

## Studio 分頁

![Studio 分頁截圖（待補）](docs/screenshots/studio.png)

### MIDI transport

| 控制項 | 功能 |
|---|---|
| `Play` | 從目前 seek 位置透過預設 MIDI output 播放 Current MIDI |
| `Pause` | 暫停並送出 All Notes Off；再次按 Play 從暫停位置續播 |
| `Stop` | 停止、關閉 MIDI output、回到 0 秒 |
| 時間 slider | 拖曳定位；播放或暫停中移動會先送 All Notes Off |
| current / total time | 顯示 `mm:ss.mmm` 位置與總長 |

Studio `Play` 不會把按鍵送到 Heartopia。若顯示 `No MIDI output`，需安裝 `python-rtmidi` 並啟用一個 MIDI synthesizer/output port。

### Range Export

| 類型 | 控制項 | 功能 |
|---|---|---|
| Spinbox | `Start seconds` | 範圍開始，預設 `0.0` |
| Spinbox | `End seconds` | 範圍結束，預設 `30.0`，必須大於 Start |
| Button | `Play Range` | 用 game-keyboard playback 播放該秒數範圍，不是 Studio MIDI output |
| Button | `Export Range` | 匯出 `chorus_37key.mid`；重疊邊界的音符會裁切，範圍起點平移到 0 |

### Editor

| 按鈕 | 功能 |
|---|---|
| `Open Selected MIDI` | 把 Current MIDI 載入表格，分析 suspicious notes |
| `Delete selected notes` | 刪除表格中多選的音符 |
| `Delete same pitch` | 以所選第一個音符為準，刪除所有相同 MIDI pitch |
| `Delete suspicious notes` | 刪除所有被規則標紅並附原因的音符 |
| `Save as edited_37key.mid` | 在來源同資料夾寫入 edited 版本；不能以已載入的 `edited_37key.mid` 再覆寫自身 |

Editor 欄位：`start_ms`、`duration_ms`、`note`、`note_name`、`velocity`、`suspicious_reason`。刪除只先改記憶體內清單，按 Save 才寫檔。

### Timeline

| 類型 | 控制項 | 功能 |
|---|---|---|
| Dropdown | `View Mode` | `Piano Roll` 顯示音高／時間方塊；`Staff View` 顯示五線譜 |
| Button | `Zoom -` | 時間軸縮小 |
| Button | `Zoom +` | 時間軸放大 |
| Horizontal scrollbar | — | 左右瀏覽時間軸 |

Staff View 點選音符會顯示音名、開始時間、長度與 velocity，並同步選取 Editor 對應列。

### Future AI Repair

這一區只有保留文字，**目前沒有 AI Repair 功能或按鈕**，不是可操作功能；見 Roadmap。

## Analysis 分頁

![Analysis 分頁截圖（待補）](docs/screenshots/analysis.png)

Analysis 沒有按鈕、dropdown 或 checkbox。切換 Current MIDI 時，程式會載入同工作資料夾的 `report.json`；若沒有報告則顯示 `--`，不會自行重跑完整 pipeline。

| 區塊 | 欄位 |
|---|---|
| `Song Information` | Keyboard Profile、Song Duration、Tempo、Detected Key |
| `MIDI Statistics` | Total Notes、Raw Notes、Selected Notes、Selected Tracks、Selected Channels |
| `Conversion Report` | Clean Notes、Piano Arranged Notes、Final Notes |
| `Note Statistics` | Removed Notes、Merged Notes、Octave Shifted、Bass Removed、Harmony Simplified、Melody Selected |

統計反映建立 report 當時的 pipeline；之後只切換版本或手動編輯，不會自動改寫舊 report。

## 所有輸出檔案

### 命名與資料夾

- YouTube：`output/<影片標題>_<video-id>/`
- Audio：`output/<原檔名>_local/`
- External MIDI：`output/<原檔名>_midi/`
- 預設 audio pipeline 的 MIDI 位於 `midi/accompaniment/`，vocals 位於 `midi/vocals/`
- 非預設 separation/stem 組合位於 `midi/selected_<mode>_<stem>/`

### MIDI 檔案

| 檔案 | 何時產生 | 內容與用途 |
|---|---|---|
| Basic Pitch Raw MIDI（檔名由 Basic Pitch 決定） | Audio/YouTube transcription | 最接近音訊辨識結果；通常仍有越界、短音與雜音 |
| `imported.mid` | External MIDI processing | 原檔工作副本；Type 2 會在副本中正規化為 Type 1 |
| `selected_parts.mid` | External MIDI processing | 只含 `Use Optimization` 聲部，並套用 selected-part 越界模式 |
| `selected_direct.mid` | Direct Preview/Play 時 | 暫存資料夾中的 Direct selection 工作檔；關閉程式後不保證保留 |
| `clean_37key.mid` | Cleanup | 移除短／弱音、處理音域、旋律模式與同時音上限；Skip 時是 pass-through copy |
| `piano_arranged_37key.mid` | Arranger | `piano_cover`／`melody_only` 結果；targeted rebuild 的 `original` 可建立 pass-through；某些 original audio run 可能不產生此檔 |
| `piano_cover_37key.mid` | Audio/YouTube post-processing 使用簡化 arrangement 時 | `piano_arranged_37key.mid` 的 legacy 相容副本 |
| `ai_optimized_37key.mid` | Optimizer | Rule 或 Experimental OpenAI 的輸出；Skip 時為 pass-through |
| `pitch_corrected_37key.mid` | Pitch Correction | 偵測 key 後移除／修正可疑離調與跳音；Skip 時為 pass-through |
| `final_37key.mid` | Final smoothing | 將時間量化、保證最短音長、避開同 pitch 重疊；通常是 Play to Game 首選 |
| `transposed_37key.mid` | 改變 Optimization 的 Target Key | 實際寫入新調的版本 |
| `chorus_37key.mid` | Studio `Export Range` | 所選秒數範圍，平移至 0 秒 |
| `edited_37key.mid` | Editor Save | 手動刪除後的版本；版本選擇時優先度最高 |

### 其他產物

| 檔案／資料夾 | 說明 |
|---|---|
| `download/song.wav` | YouTube 下載或本機音訊正規化後的工作音訊 |
| `separated/htdemucs/song/*.wav` | Demucs stems：vocals、no_vocals，或 drums/bass/other |
| `report.json` | Analysis 面板使用的 pipeline 統計 |
| `piano_arranged_37key_report.json` | Piano Arranger 詳細統計；Skip Arranger 時會移除舊報告 |

## 建議設定

### 初學者

| 情境 | 建議 |
|---|---|
| 高品質現成 MIDI | `Safe`，先 A/B 比較 Raw/Imported 與 Final；若原檔已完全符合範圍，可 Skip Piano Arranger |
| 一般現成 MIDI | `Balanced`、`Use Optimization` 只選主旋律／鋼琴聲部、selected-part range 用 `octave_shift` |
| YouTube / Audio | `Demucs vocals only` + `no_vocals` + `Balanced`；先不要勾 vocals |
| 遊戲播放 | `Speed 1.0`、`Focus delay 3`、`Transpose 0`、`Chord gap 18 ms`、`Min hold 75 ms`、`Heartopia` |
| 和弦漏音 | 先把 Speed 降到 `0.75`，再把 Chord gap 小幅提高到 `24–30 ms` |

第一次不要同時大改多個門檻。先比較 `Clean → Piano Arranged → Final`，找出問題在哪一階段。

### 進階使用者

| 目標 | 建議做法 |
|---|---|
| 最大限度保留原譜 | 由 `Safe` 起步，`original`、低 Min note/Velocity、`Max simultaneous = 0`，用 A/B 驗證 |
| 去除 transcription 雜音 | 由 `Aggressive` 起步；逐步調整 Min note、Velocity、window，避免一次過度刪音 |
| 只保留主旋律 | 優先試 `Arrangement style = melody_only`；若仍太密，再開 Cleanup `Melody only` |
| 簡化鋼琴 cover | `Piano Cover` preset，Melody notes `2–3`，window `50–100 ms` |
| 精準挑聲部 | 在 Import 分開設定 `Use Direct` 與 `Use Optimization`，以 Track+Channel 而非整 Track 判斷 |
| 測 OpenAI | **Experimental**；先保存 Rule 版本、確認 API 費用與資料傳送，再用 A/B 比較；失敗會回退 Rule |
| 建立片段 | Studio 定好 Start/End，Export Range，再把 `chorus_37key.mid` 設為 Current |
| 保留演奏事件 | Direct Play `Full Imported MIDI`；避免把需要 sustain、program 或多 channel identity 的需求交給 note-only processing stages |

## FAQ

### 為什麼按 Play to Game 沒有聲音？

它不是音訊播放器，而是向目前焦點視窗送電腦鍵盤事件。倒數時切回 Heartopia、打開鋼琴並確保遊戲視窗有焦點。若要在電腦上聽 MIDI，使用 Studio Play 並先準備 MIDI synthesizer。

### Studio Play 為什麼顯示 No MIDI output？

`python-rtmidi` 只提供連線能力，仍需 Windows 上有可開啟的 hardware/software MIDI output。啟動 synthesizer 後重開程式再試。

### 如何立即停止？

game playback 按 `F8`，或按 Main / A/B 的 `Stop`。Studio playback 使用 Studio 的 `Stop`。

### 為什麼 Heartopia 顯示 C3–C6，不是 C2–C5？

目前 `Heartopia` profile 的實作是 MIDI `48–84`，依標準 MIDI 命名為 `C3–C6`。`Standard 37-Key` 才是 `C2–C5`。

### 為什麼 MIDI editor 顯示的軌數和 Import 不同？

Track 是檔案容器，Channel 才常代表樂器聲部。同一 Track 可有多個 Channel，不同軟體也可能按 Channel 顯示「軌」。本程式以實體 `Track + Channel` 分析可選聲部。

### `Keep original` 為什麼仍有音符沒播放？

超出所選 Keyboard Profile map 的音符沒有對應遊戲按鍵。改用 `Octave shift into playable range` 或 `Drop out-of-range notes`。

### `None` 為什麼仍有 `ai_optimized_37key.mid`？

pipeline 固定建立各階段檔案，而且目前 `None` 仍走本機 rules。External MIDI 若要讓此階段完全傳遞上一版本，勾 `Skip AI Optimizer`。

### OpenAI 失敗時會怎樣？

**Experimental OpenAI Optimizer** 會自動回退到 Rule，因此 conversion 仍可能成功，但 UI 不會為每個 chunk 顯示回退原因。

### 為什麼 `Existing no_vocals` 失敗？

它只讀取既有 `separated/htdemucs/song/no_vocals.wav`，不會自行建立，而且 `Stem to Convert` 必須是 `no_vocals`。

### 為什麼選 `other` 或 `drums` 後失敗？

`Demucs vocals only` 只提供 vocals/no_vocals。請改成 `Demucs 4-stem`。

### 為什麼 Analysis 全是 `--`？

目前 MIDI 的資料夾沒有 `report.json`，或只是用 `Open MIDI` 載入單檔。Analysis 不會為任意單檔自動執行 pipeline。

### Skip 之後為什麼還有對應檔案？

Skip 代表略過該演算法，不是略過檔名。程式建立 pass-through copy，讓下游和版本選單有一致的 stage artifact。

### 可以停止 conversion 嗎？

可以按 Main 的 `Stop`。外部 process 會收到取消要求；已經完整寫出的舊檔或 cache 可能仍留在 `output/`。

### 為什麼轉同一來源像是直接載入舊結果？

預設 separation/stem 組合會重用可辨識的 cached conversion。若要以新 processing 參數更新，可用 Optimization 的 rebuild 按鈕；非預設 separation/stem 會使用不同 MIDI 子資料夾。

## Roadmap

以下皆為規劃方向，**目前不存在或尚未完成，不應視為可用功能**：

- AI Repair：Studio 已保留說明區，但沒有修復按鈕或模型流程。
- 更直覺的 Track/Channel 聲部命名、獨立 audition 與選取流程。
- 改善 Piano Arranger 的旋律、和聲與低音判斷。
- 改善 Piano Roll / Staff View 排版、記譜資訊與編輯互動。
- 支援多種 transcription engine 並可比較結果。
- 建立供未來 machine learning 使用的 dataset builder。

## License

目前 repository 未包含 license file。
