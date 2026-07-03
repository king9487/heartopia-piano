# Heartopia Piano Studio

Heartopia Piano Studio 是一套為《心動小鎮》（Heartopia）37 鍵鋼琴設計的 MIDI 最佳化、分析、編輯與播放工具。它支援 YouTube、音訊檔與現有 MIDI，不再只是一個 YouTube to MIDI converter。

> English summary: A Windows tool for converting, analyzing, optimizing, editing, previewing, and playing MIDI on Heartopia's 37-key piano (`C2`–`C5`).

## 專案用途

本專案的核心目標，是把不同來源的音樂整理成適合 Heartopia 37 鍵鋼琴的版本，並協助使用者理解每個處理階段造成的變化。

主要用途包括：

- 將 YouTube 或本機音訊分離音軌（Demucs），再轉錄為 MIDI（Basic Pitch）。
- 匯入現有 MIDI，分析 Track、Channel、音域與可播放比例。
- 將音符限制或調整至 `C2`–`C5`，清除過短、過弱或過密的音符。
- 製作偏向鋼琴演奏的編曲（Piano Arranger），並執行規則或 OpenAI 最佳化。
- 比較、預覽、編輯各階段 MIDI，最後以鍵盤事件播放到遊戲（Play to Game）。

## 支援的輸入來源

### 1. YouTube Video

輸入 YouTube 網址後，程式會使用 `yt-dlp` 取得音訊，經 Demucs 分離，再由 Basic Pitch 轉成 MIDI。此流程需要網路、FFmpeg 與相關模型。

### 2. Audio File

選擇本機音訊檔後，會直接進入與 YouTube 相同的 Demucs 與 Basic Pitch 流程，不執行下載。

### 3. MIDI File

可匯入 `.mid` 或 `.midi` 檔案。匯入後有兩種用法：

- 直接播放（Direct Play）：使用匯入的 MIDI，不必先跑完整最佳化流程。
- 為 Heartopia 處理（Optimize for Heartopia）：選取需要的音樂聲部，再產生 37 鍵版本。

MIDI Track 不一定等於人耳理解的「一個樂器」或「一個聲部」。同一個 Track 內可能包含多個 Channel，因此實際聲部可能是 `Track + Channel` 的組合。Import 分頁會同時分析兩者，並讓 Direct Play 與 Optimization 各自選取要使用的 Track/Channel 聲部。

## MIDI Track / Channel 說明

假設匯入檔案的分析結果如下：

```text
Track 0 Channel 0: 618 notes, many out of range
Track 0 Channel 1: 517 notes, playable
Track 1 Channel 0: 312 notes, playable
```

- Track 是 MIDI 檔案中的容器或層（container/layer），用來收納事件。
- Channel 是 Track 內實際標記樂器或聲部的通道。檔案內使用 `0`–`15`，一般 MIDI 介面常顯示為 `1`–`16`。
- 同一 Track 可同時包含多個 Channel；不同 Track 也可能使用同一 Channel。
- 有些 MIDI 編輯器按 Channel 顯示聲部，而不是按 Track 顯示，所以它顯示的「軌數」可能與本程式不同。

以上範例中，不能因 Track 0 總音符很多就整軌捨棄：`Track 0 / Channel 0` 有大量超出 37 鍵的音，但 `Track 0 / Channel 1` 是可播放聲部。因此程式以 `Track + Channel` 分析與篩選，避免把可用聲部一起刪掉。

## 處理流程 Pipeline

```text
Input
  ↓
Clean 37-Key MIDI
  ↓
Piano Arranged MIDI
  ↓
AI Optimized MIDI
  ↓
Pitch Corrected MIDI
  ↓
Final 37-Key MIDI
  ↓
Edited MIDI
  ↓
Play to Game
```

YouTube 與 Audio 在進入上圖前，會先經過 `Demucs → Basic Pitch`。匯入 MIDI 則從 MIDI 分析與處理直接開始。Imported MIDI 的處理階段可個別略過；略過時仍會建立對應的傳遞副本（pass-through copy），以保持後續檔名與版本選擇一致。Edited MIDI 是使用編輯器後才會產生的選用階段。

各輸出用途如下：

| 輸出 | 常見檔名 | 說明 |
|---|---|---|
| Imported MIDI | `imported.mid` | 匯入 MIDI 的工作副本；可直接預覽、開啟或播放。若選取部分 Track/Channel，處理流程另會建立 `selected_parts.mid`。 |
| Clean 37-Key MIDI | `clean_37key.mid` | 移除過短／過弱音符、處理超出音域的音，並依設定限制過密音符。 |
| Piano Arranged MIDI | `piano_arranged_37key.mid` | 依 `original`、`melody_only` 或 `piano_cover` 編曲風格整理旋律、和聲與低音。 |
| AI Optimized MIDI | `ai_optimized_37key.mid` | 依 `None`、`Rule` 或 `OpenAI` 模式最佳化；OpenAI 無法使用時會回退至本機規則。 |
| Pitch Corrected MIDI | `pitch_corrected_37key.mid` | 依偵測到的調性，修正不穩定音高並維持 37 鍵音域。 |
| Final 37-Key MIDI | `final_37key.mid` | 完成最終平滑、最短音長處理與時間量化，作為主要遊戲版本。 |
| Edited MIDI | `edited_37key.mid` | 在 Studio 的 MIDI Editor 刪除選取、重複或可疑音符後儲存的版本。 |

## UI Tabs 說明

### Main

主要輸入與目前 MIDI 控制。可選擇 YouTube Video、Audio File 或 MIDI File；也可開啟、預覽目前 MIDI、播放到遊戲或停止工作。YouTube／Audio 的 Demucs 裝置與是否轉錄 vocals 也在此設定。

### Import

用於匯入 MIDI 的分析與直接播放。顯示檔名、時間、速度、調性、Track、PPQ、音符數、可播放比例，以及各 `Track + Channel` 的樂器、音域與超界音符。可分別勾選 Direct Play／Optimization 要使用的聲部，並選擇保留、移調或丟棄超界音符。

### Optimization

用於 Cleanup、Piano Arranger、AI Optimizer、Pitch Correction 與調性移調（Key Transpose）。可套用 Preset，也可重建 Clean、Piano Arranged 或 Final 階段。

### Playback

用於版本選擇與遊戲播放。可控制 Speed、Focus delay、Transpose、Chord gap、Min hold，選擇過去的 `output/` 資料夾，並用 A/B Compare 比較兩個 MIDI 版本。按 `F8` 可停止 Play to Game。

### Studio

提供可定位的 MIDI 播放、時間軸（Timeline）、Piano Roll、五線譜檢視（Staff View）、範圍播放／匯出，以及 MIDI Editor。Editor 可標記可疑音符並刪除選取、重複或可疑音符。AI Repair 尚未實作，列於 Roadmap。

Studio 播放需要 `python-rtmidi` 可使用的 MIDI output（硬體或軟體合成器）；它與向 Heartopia 傳送電腦鍵盤事件的 Play to Game 不同。

### Analysis

顯示 `report.json` 中的音符數、歌曲時間、速度、偵測調性、各轉換階段統計、Piano Arranger 統計與除錯資訊。若選擇的資料夾沒有報告，面板不會自行猜測缺少的流程資料。

## 重要設定說明

下表的「建議值」以目前預設的 Balanced 工作方式為起點，不是所有歌曲的唯一正解。先用建議值試聽，再小幅調整，通常比一次改很多參數更容易找出原因。

| Setting | 中文名稱 | 用途 | 建議值 | 什麼時候要調整 |
|---|---|---|---|---|
| Preset | 處理預設 | 一次套用 Cleanup、Arranger 與 Optimizer 的一組設定。 | `Balanced`；高品質 MIDI 可試 `Safe`。 | 想快速切換保守、平衡、強力清理或 Piano Cover 時。 |
| Min note ms | 最短音符長度 | 移除短於指定毫秒數的音符。 | `35 ms` | 雜碎短音多就提高；裝飾音被吃掉就降低。 |
| Velocity threshold | 力度門檻 | 移除 velocity 低於門檻的弱音。 | `12` | 幽靈音／雜音多就提高；弱奏消失就降低。 |
| Range mode | 音域處理模式 | 決定 37 鍵外的音符如何處理。 | `smart` | 旋律被刪、低音錯位或八度移動太多時，改用 `drop` 或 `octave_shift` 比較。 |
| Melody only | 僅保留旋律 | Cleanup 時依時間窗保留較高音，捨棄大部分伴奏。 | 關閉（Off） | 只想演奏主旋律，或來源和聲過度複雜時開啟。 |
| Melody notes | 旋律音符數 | Piano Arranger 每個時間窗最多保留的重點音符數。 | `3`；Piano Cover 可用 `2` | 和弦太密就降低；旋律／和聲太薄就提高。 |
| Melody window ms | 旋律時間窗 | 將時間相近的音符視為同一組來挑選與編排。 | `80 ms` | 快歌誤合併可降低；輕微不同步的和弦沒被視為一組可提高。 |
| Arrangement style | 編曲風格 | `original` 保留清理後內容；`melody_only` 抽取高音旋律；`piano_cover` 產生旋律主導、簡化和聲與低音的版本。 | `piano_cover` | 高品質成品 MIDI 用 `original`；只要主旋律用 `melody_only`。 |
| Optimizer mode | 最佳化模式 | `None` 不做額外最佳化；`Rule` 使用本機規則；`OpenAI` 使用 API，失敗時回退至 Rule。 | `Rule` | 已整理好的 MIDI 可用 `None`；想試模型判斷且已設定 `OPENAI_API_KEY` 時用 `OpenAI`。 |
| Original Key | 原始調性 | 指定來源大調，或讓程式自動偵測。 | `Auto Detect` | 自動偵測結果明顯錯誤時手動指定。 |
| Target Key | 目標調性 | 將 MIDI 轉至指定大調；`Original` 不做調性移調。 | `Original` | 想配合其他樂器／人聲，或某調在 37 鍵上更好配置時。 |
| Speed | 播放速度 | 控制 Play to Game 的播放倍率。 | `1.0` | 遊戲漏音、電腦較慢或練習時降低；確認穩定後再提高。 |
| Focus delay | 聚焦倒數 | 開始播放前等待幾秒，讓你切回並聚焦遊戲視窗。 | `3 秒` | 來不及切回遊戲就提高。 |
| Transpose | 即時移調 | Play to Game 時以半音為單位移調，不改寫 MIDI 檔。 | `0` | 想臨時換調或修正鍵位，但不想產生新檔時。 |
| Chord gap ms | 和弦按鍵間隔 | 將同時音符稍微錯開送出，降低遊戲漏掉和弦按鍵的機率。 | `18 ms` | 和弦漏音就提高；琶音感太明顯就降低。 |
| Min hold ms | 最短按鍵時間 | 每個遊戲按鍵至少按住多久。 | `75 ms` | 短音無法觸發就提高；音符黏住或快速段落不清楚就降低。 |
| Skip Cleanup | 略過清理 | 匯入 MIDI 時不執行 Cleanup，建立傳遞副本供下一階段使用。 | 關閉（Off） | MIDI 已經乾淨且完全符合 37 鍵時可開啟。 |
| Skip Piano Arranger | 略過鋼琴編曲 | 匯入 MIDI 時不重新整理旋律、和聲與低音。 | 高品質編曲可開；複雜來源保持關閉。 | 原檔已是理想鋼琴譜，或 Arranger 反而刪掉重要聲部時。 |
| Skip AI Optimizer | 略過 AI 最佳化 | 匯入 MIDI 時不執行所選 Optimizer。 | 想保守保留原編排時開啟。 | 已滿意 Clean／Arranged 結果，或不需要額外規則處理時。 |
| Skip Pitch Correction | 略過音高修正 | 匯入 MIDI 時不依調性修正音符。 | 調性正確的商業 MIDI 可開啟。 | 原曲含轉調、借用和弦或刻意半音，避免被誤修時。 |
| Direct Preview after processing | 處理後立即預覽 | Process Imported MIDI 完成後自動預覽結果。 | 依個人習慣；預設關閉。 | 想每次完成後立即聽結果時開啟。 |

`Range mode` 詳細差異：

- `smart`：只將距離 37 鍵範圍不超過兩個八度的超界音移入範圍；太遠的音會丟棄，較能避免極端音高被硬塞進來。
- `drop`：直接刪除所有超出 `C2`–`C5` 的音符，音高最忠實，但可能失去低音或旋律。
- `octave_shift`：將超界音以八度移入範圍，通常保留最多音符，但可能造成音域擁擠或聲部交錯。

## Direct Play vs Optimize

| 模式 | 使用內容 | 適合情況 |
|---|---|---|
| Direct Play | 直接使用匯入 MIDI 中勾選的 Track/Channel 聲部；可選擇保留、八度移調或丟棄超界音。 | MuseScore 匯出、商業 MIDI、已整理好的 37 鍵譜，或只想快速試播。 |
| Optimize for Heartopia | 將勾選聲部寫入工作檔，依序產生 37 鍵最佳化階段。 | 音符過密、超界音多、聲部複雜或需要 Piano Arranger 的 MIDI。 |

高品質 MIDI 不一定需要最佳化。若原檔已經是清楚的鋼琴編曲，先 Preview Original 與 Play Original；反之，Basic Pitch 產生或來源複雜的 MIDI，通常需要 Cleanup 或 Piano Arranger。最佳判斷方式是 A/B Compare，而不是把所有階段一律打開。

## 常見問題 FAQ

### 1. 為什麼匯入 MIDI 後音符數量和其他軟體看到的不一樣？

不同軟體可能只計算特定 Track、Channel、可見聲部或有效 note-on 事件。本程式會分別統計總音符、37 鍵內音符與超界音符；若選取部分 Track/Channel，播放或處理數量也會再改變。

### 2. 為什麼 Track 數量不一樣？

MIDI 檔案的實體 Track 與編輯器畫面上的聲部不一定一對一。有些軟體會按 Channel、樂器或五線譜拆分顯示，所以畫面看到的軌數不等於檔案內 Track 數。

### 3. 為什麼有些音會不見？

常見原因是音符低於 Min note ms／Velocity threshold、超出 37 鍵後被 `drop` 或 `smart` 丟棄、密度限制、Melody Only、Piano Arranger 簡化，或該 Track/Channel 沒有被勾選。可依序比較 Imported、Clean、Arranged 與 Final 找出發生階段。

### 4. 為什麼 Play Original 和 Final 聽起來不一樣？

Play Original 使用匯入聲部與直接播放音域設定；Final 則可能經過 Cleanup、Piano Arranger、Optimizer、Pitch Correction、最短音長與時間量化。它們代表「來源」與「遊戲最佳化結果」，本來就可能不同。

### 5. 什麼時候要用 Piano Cover？

當來源是多樂器、和弦密集或不是專為鋼琴編寫，想保留主旋律並簡化和聲與低音時使用。若原檔已是成熟鋼琴編曲，先試 `original`。

### 6. 什麼時候要用 Melody Only？

只想演奏主旋律、伴奏太複雜，或 37 鍵無法容納完整編曲時使用。它會主動犧牲和聲，因此不適合需要完整鋼琴質感的歌曲。

### 7. Range mode 的 smart／drop／octave_shift 差在哪？

`smart` 只搬移距離合理的超界音並丟棄極端音；`drop` 完全刪除超界音；`octave_shift` 儘量把所有超界音用八度移回。一般先用 `smart`，再依漏音或音域擁擠情況比較另外兩種。

### 8. 為什麼 Basic Pitch 轉出來會有雜音？

Basic Pitch 是從音訊估計音高。鼓聲、殘響、人聲洩漏、失真、多樂器重疊與 Demucs 分離殘留，都可能被判定成短音或弱音。可提高 Min note ms／Velocity threshold、使用 Piano Cover，並在 Editor 刪除可疑音符。

### 9. 為什麼要看 Track + Channel？

因為同一 Track 可能同時包含可播放與不可播放的 Channel。只看 Track 會把不同樂器混在一起，可能錯刪好聲部或把噪音聲部一起送進最佳化。

### 10. 為什麼 Timing Fix 很重要？

MIDI 的節奏不只是一串毫秒數，還包含 PPQ、tempo map 與 tick 位置。處理時若遺失這些關係，變速、轉換或重建後就可能出現拍點漂移。現有流程會保留來源 tick／tempo 資訊，並只在最終階段記錄與執行必要的時間量化，讓 A/B 比較與遊戲播放更可靠。

## 建議使用流程

### 高品質 MIDI

```text
Import MIDI
→ Preview Original
→ Play Original
→ Editor if needed
```

先確認 Track/Channel 勾選與超界音處理。若原檔已適合 37 鍵，不必為了「跑完整流程」而強制最佳化。

### 普通 MIDI

```text
Import MIDI
→ Analyze Track/Channel
→ Process Imported MIDI
→ A/B Compare
→ Editor
→ Play to Game
```

先排除不需要的聲部，再從 Balanced 開始。若結果損失太多，可改 Safe、`original`，或略過個別階段。

### YouTube / Audio

```text
YouTube or Audio
→ Demucs
→ Basic Pitch
→ Piano Arranger
→ Final
→ Editor
→ Play
```

音訊轉錄通常比現成 MIDI 更容易出現雜音，建議查看 Analysis 並比較 Clean、Piano Arranged 與 Final。

## 安裝與執行 Installation

需求：Windows、64-bit Python 3.11、內建於 Python 安裝程式的 Tcl/Tk（Tkinter）、FFmpeg／FFprobe，以及 `requirements.txt` 中的套件。Python 3.11 是目前 Basic Pitch 0.4.0、TensorFlow 2.15.0 與 GPU 套件組合的支援版本。

`requirements.txt` 預設以 NVIDIA CUDA 12.1 安裝相容且版本配對的 PyTorch／torchaudio，並使用 `onnxruntime-gpu`（不與 `onnxruntime` CPU 套件並裝）。CPU-only 系統需將 CUDA 版 `torch`／`torchaudio` 改為 PyTorch 官方相容的 CPU 版本。Pillow、pygame 與 `ffmpeg-python` 目前未被程式使用，因此不列入依賴；FFmpeg 是獨立的系統工具。

安裝 FFmpeg：

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

自動建立環境（會重建 `.venv`）：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

或手動建立乾淨環境：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

啟動桌面 UI：

```powershell
.\.venv\Scripts\python.exe .\youtube_to_midi.py
```

或執行 `start_ui.bat`。CLI 可使用 `start_cli.bat`，但外部 MIDI 匯入目前由桌面 UI 提供。輸出會儲存在 `output/`。

OpenAI Optimizer 需要設定 `OPENAI_API_KEY`；未設定或請求失敗時會回退至本機 Rule 模式。

## Roadmap

以下為規劃項目，不代表目前已完整實作：

- 更完整的 Track/Channel part selection，包括更直覺的聲部預聽、命名與選取流程。
- Better Piano Arranger：改善旋律、和聲與低音判斷。
- AI Repair：在 Studio／Editor 中提供可控的 AI 修復建議。
- Better Staff View：改善排版、記譜資訊與編輯互動。
- Multiple transcription engines：加入多種音訊轉錄引擎供比較與選擇。
- Dataset builder：建立未來機器學習（ML）所需的資料集整理工具。

## License

目前專案未包含授權檔（license file）。
