# Heartopia Piano MIDI Tool

把 YouTube 或本地音樂轉成 MIDI，並把 MIDI 音符轉成 37 鍵音樂遊戲可用的鍵盤輸入。

## 功能

- 支援 YouTube URL 轉 MIDI
- 支援本地音樂檔轉 MIDI：`mp3`、`wav`、`m4a`、`flac`、`ogg`、`webm`、`aac`
- 使用 Demucs 拆分 `vocals` / `accompaniment`
- 使用 Basic Pitch 產生 MIDI
- 支援 37 鍵遊戲鍵位 mapping
- 支援 MIDI 清理：
  - 過濾太短的音
  - 過濾低 velocity 的音
  - 合併很接近的重複音
  - 限制同一時間最多按幾個音
  - 超出範圍音符可用八度平移塞回可玩範圍
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
4. 等待下載、拆音軌、轉 MIDI
5. 選 `Vocals MIDI` 或 `Accompaniment MIDI`
6. 按 `Preview` 查看會送出的鍵盤事件
7. 按 `Play to Game`
8. 倒數期間切回遊戲
9. 播放中按 `F8` 停止

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

## UI 參數

### Playback

- `Speed`：播放速度，`1.0` 是原速
- `Focus delay`：按 Play 後幾秒開始，給你時間切回遊戲
- `Demucs`：
  - `cuda:0`：使用 NVIDIA GPU
  - `cpu`：使用 CPU
  - `auto`：讓 Demucs 自己判斷

### Timing

- `Transpose`：升降 key，單位是半音
  - `-1`：降半音
  - `-2`：降全音
  - `-12`：降一個八度
  - `+12`：升一個八度
- `Chord gap ms`：同一時間多鍵時，每個鍵錯開幾毫秒
- `Min hold ms`：每個鍵至少按住多久，避免遊戲漏接太短的音

### MIDI Cleanup

- `Min note ms`：移除短於此時間的音符
- `Velocity`：移除力度低於此值的音符
- `Max notes`：同一時間最多保留幾個音，`0` 表示不限制
- `Octave fit`：
  - `off`：只播放 mapping 範圍內的音
  - `octave_shift`：超出範圍的音用八度平移塞回 37 鍵範圍；低於範圍就持續加 12，高於範圍就持續減 12
  - `drop`：直接丟掉超出範圍的音

目前不會把超出範圍的音自動替換成和弦。之後如果需要，可以另外加 `harmonic_fill`，但預設會保持關閉。

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

### MuseScore 播得比較順，但遊戲少音

MuseScore 是 MIDI 播放器，可以同時播很多音。遊戲鍵盤輸入可能會被幀率、輸入輪詢、同時按鍵限制影響，所以需要 cleanup 和 timing 設定。

### 轉出來的 MIDI 太亂

可以優先試 `Accompaniment MIDI`，有時會比 `Vocals MIDI` 更適合遊戲鍵盤。

也可以調整：

- `Velocity`
- `Min note ms`
- `Max notes`
- `Octave fit`
- `Transpose`

## 檔案結構

```text
youtube_to_midi.py      UI 入口
ui_app.py               Tkinter 圖形介面
cli_app.py              命令列入口
converter.py            YouTube/本地音訊轉 MIDI
midi_to_keyboard.py     MIDI 清理、mapping、鍵盤播放
tools.py                外部工具尋找、subprocess、取消邏輯
requirements.txt        Python 依賴
setup.ps1               Windows 安裝/重建環境腳本
output\                 轉換輸出與快取
```

## 停止播放或轉換

- 鍵盤播放中：按 `F8`
- UI 可見時：按 `Stop`
- 轉換中：按 `Stop` 會取消目前 `yt-dlp` / `ffmpeg` / `demucs` / `basic-pitch` 程序
