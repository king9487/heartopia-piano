# Heartopia Piano MIDI Tool

把 YouTube 或本地音樂轉成 MIDI，並把 MIDI 音符轉成 37 鍵音樂遊戲可用的鍵盤輸入。

## 功能

- 支援 YouTube URL 轉 MIDI
- 支援本地音樂檔轉 MIDI：`mp3`、`wav`、`m4a`、`flac`、`ogg`、`webm`、`aac`
- 使用 Demucs 拆分 `vocals` / `accompaniment`
- 預設只把 `no_vocals.wav` / `accompaniment` 用 Basic Pitch 轉成 MIDI
- `vocals` MIDI 轉換是可選功能，預設關閉
- Basic Pitch 後會另外產生 `clean_37key.mid`，先整理成適合 37 鍵遊戲的 MIDI
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

## 基本使用

### YouTube 轉 MIDI

1. 開啟 UI
2. 貼上 YouTube URL
3. 按 `Convert URL`
4. 等待下載、拆音軌、轉 `Accompaniment MIDI`
5. 預設會選 `Accompaniment MIDI`
6. `MIDI source` 預設選 `Clean 37-Key MIDI`；需要比較原始結果時可切到 `Raw MIDI`
7. 按 `Preview` 查看會送出的鍵盤事件
8. 按 `Play to Game`
9. 倒數期間切回遊戲
10. 播放中按 `F8` 停止

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
- Clean 37-Key MIDI：工具整理後的 `clean_37key.mid`，預設用於遊戲播放

預設只會在 `midi\accompaniment\` 產生 raw MIDI 和 `clean_37key.mid`。如果有勾選 `Convert vocals MIDI`，才會另外在 `midi\vocals\` 產生 vocals 的 raw MIDI 和 clean MIDI。

## UI 參數

### Playback

- `Speed`：播放速度，`1.0` 是原速
- `Focus delay`：按 Play 後幾秒開始，給你時間切回遊戲
- `Demucs`：
  - `cuda:0`：使用 NVIDIA GPU
  - `cpu`：使用 CPU
  - `auto`：讓 Demucs 自己判斷
- `Convert vocals MIDI`：預設關閉。開啟後會額外把 `vocals.wav` 轉成 MIDI，並產生 vocals 的 `clean_37key.mid`

### Timing

- `Transpose`：升降 key，單位是半音
  - `-1`：降半音
  - `-2`：降全音
  - `-12`：降一個八度
  - `+12`：升一個八度
- `Chord gap ms`：同一時間多鍵時，每個鍵錯開幾毫秒
- `Min hold ms`：每個鍵至少按住多久，避免遊戲漏接太短的音

### MIDI Cleanup

轉換完成後，工具會在 Basic Pitch raw MIDI 旁邊產生一份 `clean_37key.mid`。這個檔案會先把 MIDI 整理成 37 鍵可播放範圍，再讓 UI 預設拿它播放。UI 的 `MIDI source` 可以在 `Clean 37-Key MIDI` 和 `Raw MIDI` 之間切換。

產生 `clean_37key.mid` 時的主要邏輯：

1. 讀取 raw MIDI 的所有 `note_on` / `note_off` 配對
2. 計算每個音的開始時間、結束時間、長度和 velocity
3. 移除太短、velocity 太低的音
4. 用 `smart` 模式把合理的範圍外音折回 37 鍵；離可玩範圍超過 24 半音的音會丟掉
5. 以約 `30ms` 的小時間窗分組
6. 每組只保留分數最高的幾個音

分數大致是：

```text
score = velocity * 1.0 + duration_ms * 0.2 + pitch_bonus
```

`pitch_bonus` 會在偏好旋律時稍微偏向較高的音，讓伴奏 MIDI 比較容易留下主旋律線。

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
midi_to_keyboard.py     MIDI 清理、clean_37key.mid 產生、mapping、鍵盤播放
tools.py                外部工具尋找、subprocess、取消邏輯
requirements.txt        Python 依賴
setup.ps1               Windows 安裝/重建環境腳本
output\                 轉換輸出與快取
```

## 停止播放或轉換

- 鍵盤播放中：按 `F8`
- UI 可見時：按 `Stop`
- 轉換中：按 `Stop` 會取消目前 `yt-dlp` / `ffmpeg` / `demucs` / `basic-pitch` 程序
