# Heartopia Piano MIDI Tool

把 YouTube 或本地音樂轉成 MIDI，並把 MIDI 音符轉成 37 鍵音樂遊戲可用的鍵盤輸入。

## 功能

- 支援 YouTube URL 轉 MIDI
- 支援本地音樂檔轉 MIDI：`mp3`、`wav`、`m4a`、`flac`、`ogg`、`webm`、`aac`
- 使用 Demucs 拆分 `vocals` / `accompaniment`
- 預設只把 `no_vocals.wav` / `accompaniment` 用 Basic Pitch 轉成 MIDI
- `vocals` MIDI 轉換是可選功能，預設關閉
- Basic Pitch 後會依序產生 `clean_37key.mid`、`ai_optimized_37key.mid`、`pitch_corrected_37key.mid`、`final_37key.mid`
- 支援 37 鍵遊戲鍵位 mapping
- 支援 MIDI 清理：
  - 過濾太短的音
  - 過濾低 velocity 的音
  - 合併很接近的重複音
  - 限制同一時間最多按幾個音
  - 可選擇丟掉、智慧保留，或用八度平移處理超出 37 鍵範圍的音
  - 可用 `Melody only` 把複雜伴奏簡化成比較像主旋律的按鍵事件
- 支援 transpose 升降 key
- 支援 GPU 跑 Demucs
- 支援快取，已轉過的歌曲不需要重轉
- 播放時使用一般 OS keyboard events，不包含注入、繞過偵測或 driver-level 模擬

## 安裝

先進入專案資料夾：

```powershell
cd C:\Users\PC\Desktop\python_script\youtube_to_midi
```

如果 `.venv` 已經存在且依賴已安裝，可以直接跳到「啟動」。

第一次安裝或重建環境：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

如果手動安裝：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

需要另外確認 `ffmpeg` 可用。若未安裝：

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

## 啟動

UI 版：

```powershell
cd C:\Users\PC\Desktop\python_script\youtube_to_midi
.\.venv\Scripts\python.exe .\youtube_to_midi.py
```

CLI 版：

```powershell
.\.venv\Scripts\python.exe .\cli_app.py
```

CLI 調性移調：

```powershell
.\.venv\Scripts\python.exe .\cli_app.py --target-key D
.\.venv\Scripts\python.exe .\cli_app.py --original-key G --target-key C
```

沒有指定 `--target-key` 時，流程不會做調性移調。指定後會自動偵測原調，將非鼓組音符移調，並另存為 `transposed_37key.mid`。

## 基本使用

### YouTube 轉 MIDI

1. 開啟 UI
2. 貼上 YouTube URL
3. 按 `Convert URL`
4. 等待下載、拆音軌、轉 `Accompaniment MIDI`
5. 預設會選 `Accompaniment MIDI`
6. `MIDI source` 預設選 `Final 37-Key MIDI`；需要比較中間結果時可切到 `Clean 37-Key MIDI` 或 `Raw MIDI`
7. 按 `Preview` 查看會送出的鍵盤事件
8. 需要再整理旋律時，可選 `Optimizer = Rule` 或 `OpenAI`，再按 `Optimize MIDI`
9. 按 `Play to Game`
10. 倒數期間切回遊戲
11. 播放中按 `F8` 停止

預設不會轉 `Vocals MIDI`，因為目前遊戲播放通常以 `no_vocals.wav` 轉出的 accompaniment 更接近可用旋律，也能節省轉換時間。需要 vocals MIDI 時，先勾選 `Convert vocals MIDI` 再開始轉換。

### 本地音樂轉 MIDI

1. 按 `Open Audio`
2. 選本地音樂檔
3. 等待轉換
4. 後續流程同上

### 使用已轉換結果

轉換完成後會輸出到：

```text
output\歌曲名稱或檔名
```

下次同一首歌會自動使用快取。

也可以用：

- `Open Converted`：手動選已轉換資料夾
- `Converted` 下拉選單：載入已完成轉換的資料夾
- `Open MIDI`：直接選任意 `.mid` 檔播放

每個 MIDI 輸出資料夾會保留兩種 MIDI：

- Raw MIDI：Basic Pitch 直接產生的原始 `.mid`
- Clean 37-Key MIDI：規則引擎整理後的 `clean_37key.mid`
- AI Optimized MIDI：AI/rule optimizer 產生的 `ai_optimized_37key.mid`
- Pitch Corrected MIDI：依偵測到的調性校正後的 `pitch_corrected_37key.mid`
- Final 37-Key MIDI：最後 smoothing 後的 `final_37key.mid`，預設用於 preview 和遊戲播放

預設只會在 `midi\accompaniment\` 產生 raw MIDI、`clean_37key.mid`、`ai_optimized_37key.mid`、`pitch_corrected_37key.mid`、`final_37key.mid`。如果有勾選 `Convert vocals MIDI`，才會另外在 `midi\vocals\` 產生 vocals 的同一組輸出。

## UI 參數

### Playback

- `Speed`：播放速度，`1.0` 是原速
- `Focus delay`：按 Play 後幾秒開始，給你時間切回遊戲
- `Demucs`：
  - `cuda:0`：使用 NVIDIA GPU
  - `cpu`：使用 CPU
  - `auto`：讓 Demucs 自己判斷
- `Convert vocals MIDI`：預設關閉。開啟後會額外把 `vocals.wav` 轉成 MIDI，並產生 vocals 的 `clean_37key.mid`
- `Optimizer`：
  - `None`：不做額外優化
  - `Rule`：預設模式，使用本地規則優化，不需要網路或 API key
  - `OpenAI`：把 MIDI note JSON 分段送給 LLM 優化，輸出會驗證，失敗會回退到 `Rule`
- `Optimize MIDI`：將目前選中的 MIDI 重新跑 optimizer 和 smoothing，產生同資料夾內的 `ai_optimized_37key.mid` 和 `final_37key.mid`，完成後自動選取 `final_37key.mid`

### Timing

- `Transpose`：升降 key，單位是半音
  - `-1`：降半音
  - `-2`：降全音
  - `-12`：降一個八度
  - `+12`：升一個八度
- `Chord gap ms`：同一時間多鍵時，每個鍵錯開幾毫秒
- `Min hold ms`：每個鍵至少按住多久，避免遊戲漏接太短的音

### MIDI Cleanup

轉換完成後，工具會在 Basic Pitch raw MIDI 旁邊依序產生三個後處理檔案：

```text
raw MIDI
-> clean_37key.mid
-> ai_optimized_37key.mid
-> pitch_corrected_37key.mid
-> final_37key.mid
```

UI 預設用 `final_37key.mid` 做 Preview 和 Play。UI 的 `MIDI source` 可以切換 `Final 37-Key MIDI`、`Clean 37-Key MIDI` 或 `Raw MIDI`。

產生 `clean_37key.mid` 時的主要邏輯：

1. 讀取 raw MIDI 的所有 `note_on` / `note_off` 配對
2. 計算每個音的開始時間、結束時間、長度和 velocity
3. 移除太短、velocity 太低的音
4. 用 `smart` 模式把合理的範圍外音折回 37 鍵；離可玩範圍超過 24 半音的音會丟掉
5. 以約 `30ms` 的小時間窗分組
6. 依照 velocity、音長、pitch stability、旋律偏好計分
7. 每組只保留分數最高的幾個音

分數大致是：

```text
score = velocity * 1.0 + duration_ms * 0.2 + pitch_stability_bonus + pitch_bonus
```

`pitch_stability_bonus` 會偏好原本就在 37 鍵範圍內，或只需要少量八度平移的音。`pitch_bonus` 會在偏好旋律時稍微偏向較高的音，讓伴奏 MIDI 比較容易留下主旋律線。

### AI Optimizer

AI Optimizer 是在鍵盤播放前額外處理 MIDI note 的步驟。它不會控制鍵盤、不會注入遊戲、不會使用隱藏 driver，也不會做偵測規避；它只讀取 MIDI、修改 note events，然後寫出新的 MIDI 檔。

輸入 note 格式大致是：

```json
{
  "start_ms": 0,
  "duration_ms": 120,
  "note": 64,
  "velocity": 90
}
```

`Rule` 模式會：

1. 以 `50ms` 視窗分組
2. 每組保留最多 `1` 到 `3` 個音
3. 偏好 velocity 高、duration 長的音
4. 偏好平滑的 pitch movement
5. 避免突然八度跳躍
6. 避免孤立的極短音

`OpenAI` 模式會把 MIDI 分成小段，例如約每 `8` 秒一段，避免一次送整首歌。Prompt 會要求模型只回傳 JSON、保留主旋律和重要和聲、不要創作新歌、不要輸出 37 鍵範圍外的音。

OpenAI 回傳結果會驗證：

- 必須是合法 JSON
- `note` 必須在 37 鍵範圍內
- `duration_ms` 必須大於 `0`
- `start_ms` 不能小於 `0`
- `velocity` 必須是 `1` 到 `127`

如果 OpenAI 回傳無效，該段會自動回退到 `Rule` 模式。若要使用 OpenAI 模式，需要設定環境變數：

```powershell
$env:OPENAI_API_KEY="你的 API key"
```

無論 OpenAI 是否啟用或是否成功，工具都會產生 `ai_optimized_37key.mid`。接著會做 pitch correction 和 MIDI smoothing，輸出最終播放用的 `final_37key.mid`。

### Pitch Correction

Pitch correction 會在 AI/rule optimizer 後、final smoothing 前執行：

```text
ai_optimized_37key.mid
-> pitch_corrected_37key.mid
-> final_37key.mid
```

它會根據 note 的總音長和 velocity 權重，測試 12 個大調與 12 個小調，選出最可能的調性，例如：

```text
Detected key: C major
```

校正規則：

- 音符在偵測到的音階內：保留
- 音符不在音階內：嘗試往 ±1 或 ±2 半音移到最近的音階內音
- 校正方向會偏好讓旋律移動更平滑
- 太短且離調的音會丟掉
- velocity 低且離調的音會丟掉
- 如果音符造成大於 12 半音的突兀跳躍，並且馬上回到原旋律附近，會丟掉或校正
- 找不到合理校正時會丟掉

- `Min note ms`：移除短於此時間的音符
- `Velocity`：移除力度低於此值的音符
- `Max notes`：同一時間最多保留幾個音，`0` 表示不限制
- `Range mode`：
  - `smart`：預設模式。先清掉太短、太小聲、太接近的雜音，再嘗試把合理的範圍外音用八度平移放回 37 鍵。離可玩範圍超過 24 個半音、太短、或 velocity 太低的範圍外音會被丟掉
  - `drop`：直接丟掉超出範圍的音
  - `octave_shift`：超出範圍的音用八度平移塞回 37 鍵範圍；低於範圍就持續加 12，高於範圍就持續減 12。這個模式會保留更多音，但也比較容易把雜音折回可玩範圍
- `Melody only`：只保留每個小時間窗中最像主旋律的音，適合 `Accompaniment MIDI` 太亂、或遊戲短時間多 key 容易漏音時使用
- `Melody notes`：開啟 `Melody only` 後，每個時間窗最多保留幾個音，範圍是 `1` 到 `3`
  - `1`：最像單音主旋律，最穩、最不容易少音
  - `2`：保留一點和聲或雙音
  - `3`：保留更多和聲，但遊戲內漏音機率也會提高
- `Window ms`：`Melody only` 的時間窗大小
  - `50`：比較細，旋律細節保留較多
  - `80`：預設值，通常比較平衡
  - `100` 到 `120`：更強力簡化，適合 MIDI 很亂或遊戲漏音嚴重

目前不會把超出範圍的音自動替換成和弦。之後如果需要，可以另外加 `harmonic_fill`，但預設會保持關閉。

Cleanup 的順序大致是：

1. 先丟掉太短的音，也就是短於 `Min note ms` 的音
2. 再丟掉 velocity 低於 `Velocity` 的音
3. 丟掉太接近上一個同音高的重複音
4. 再依照 `Range mode` 處理超出 37 鍵範圍的音
5. 如果有開 `Melody only`，每個 `Window ms` 只保留最強的 `Melody notes` 個音
6. 最後套用 `Max notes` 限制同一時間最多幾個音

## 鍵位 Mapping

37 鍵 mapping 在：

```text
midi_to_keyboard.py
```

主要設定是：

```python
DEFAULT_NOTE_MAP = {
    ...
}
```

如果遊戲鍵位不同，直接修改這個 dict。

## GPU 說明

目前 GPU 主要用在 Demucs 拆音軌。Basic Pitch 的準確率不會因為 GPU 變高，GPU 主要是加速。

確認 CUDA 是否可用：

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

如果輸出類似：

```text
True
NVIDIA GeForce RTX 4060 Laptop GPU
```

代表 Demucs 可以用 `cuda:0`。

## 常見問題

### `ffprobe and ffmpeg not found`

安裝 ffmpeg：

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

安裝後重新開終端機再跑。

### 遊戲內少音

通常是短時間太多 key 或 note 太短。可以嘗試：

- 增加 `Chord gap ms`，例如 `25` 或 `35`
- 增加 `Min hold ms`，例如 `100`
- 設定 `Max notes`，例如 `3` 或 `4`
- 增加 `Min note ms`，過濾碎音
- 開啟 `Melody only`，先試 `Melody notes = 1`、`Window ms = 80`
- 把 `Range mode` 設成 `smart` 或 `drop`，避免範圍外雜音被折回遊戲鍵位

### MuseScore 播得比較順，但遊戲少音

MuseScore 是 MIDI 播放器，可以同時播很多音。遊戲鍵盤輸入可能會被幀率、輸入輪詢、同時按鍵限制影響，所以需要 cleanup 和 timing 設定。

### 轉出來的 MIDI 太亂

可以優先試 `Accompaniment MIDI`，有時會比 `Vocals MIDI` 更適合遊戲鍵盤。

也可以調整：

- `Velocity`
- `Min note ms`
- `Max notes`
- `Range mode`
- `Melody only`
- `Transpose`

如果是 `Accompaniment MIDI` 很接近旋律但音太滿，建議先試：

- `Range mode = smart`
- `Melody only = on`
- `Melody notes = 1`
- `Window ms = 80`
- `Max notes = 3`

如果聽起來太空，可以把 `Melody notes` 改成 `2`。如果還是太亂，可以把 `Window ms` 加到 `100` 或 `120`。

## 檔案結構

```text
youtube_to_midi.py      UI 入口
ui_app.py               Tkinter 圖形介面
cli_app.py              命令列入口
converter.py            YouTube/本地音訊轉 MIDI
midi_rule_engine.py     MIDI 規則引擎，產生 clean_37key.mid
midi_ai_optimizer.py    AI/Rule MIDI optimizer、pitch correction 與 smoothing
midi_to_keyboard.py     MIDI preview、mapping、鍵盤播放
tools.py                外部工具尋找、subprocess、取消邏輯
requirements.txt        Python 依賴
setup.ps1               Windows 安裝/重建環境腳本
output\                 轉換輸出與快取
```

## 停止播放或轉換

- 鍵盤播放中：按 `F8`
- UI 可見時：按 `Stop`
- 轉換中：按 `Stop` 會取消目前 `yt-dlp` / `ffmpeg` / `demucs` / `basic-pitch` 程序
