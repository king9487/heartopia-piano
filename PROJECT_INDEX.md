核心檔案功能概要
| 檔案名稱 | 核心功能 | 依賴關係 | 重要變數 / 類別 / 函式 | | :--- | :--- | :--- | :--- | 
| youtube_to_midi.py | GUI 程式啟動入口，腳本直接呼叫主程式 UI。 | ui_app | main() | 
| ui_app.py | 圖形化應用主體 (GUI)，處理視窗介面構建、參數設定、下載與轉換進度追蹤、狀態輪詢及全局快捷鍵控制。 | tkinter, mido, keyboard, threading, queue, converter, midi_* 系列內部模組 | YoutubeMidiApp (Class)MIDI_SOURCE_PRIORITYMIDI_SOURCE_FILENAMES | 
| ui/midi_studio_tab.py | 負責建構 UI 中的**「MIDI Studio」分頁**，包含播放、暫停、停止按鈕及時間進度條。 | tkinter, ui.midi_editor_panel | build_midi_studio_ui() | 
| ui/midi_editor_panel.py | 負責建構 UI 中的**「MIDI Editor」面板**，包含樹狀視圖 (Treeview) 與各類音符編輯、刪除按鈕。 | tkinter | build_midi_editor_panel() | 
| cli_app.py | 命令列介面 (CLI) 啟動入口，提供無 GUI 環境下的音訊轉換管線及 MIDI 實體鍵盤播放測試。 | argparse, converter, midi_to_keyboard, tools, transpose | parse_args()main() | 
| converter.py | 核心轉換管線 (Pipeline)，負責統整 yt-dlp 下載、demucs 音軌分離、basic-pitch 轉 MIDI 以及後續檔案產生的流程。 | pathlib, json, re, tools, midi_ai_optimizer, midi_rule_engine | GENERATED_MIDI_NAMESyoutube_to_midi()audio_file_to_midi() | 
| tools.py | 系統與命令列工具，負責尋找外部執行檔 (ffmpeg 等)、執行子程序 (Subprocess) 及支援任務取消功能。 | os, shutil, subprocess, threading, winreg | REQUIRED_TOOLSCancellationToken (Class)CancelledError (Class) | 
| transpose.py | 調性分析與移調，分析 MIDI 大小調與權重，並支援將音符依照目標調性進行偏移。 | mido, collections, pathlib | KEY_NAMESKEY_TO_PITCH_CLASSMAJOR_SCALE | 
| playable_range.py | 音域處理演算法，提供將任意音符範圍透過「八度摺疊 (Octave Folding)」及和弦處理，限制在遊戲可彈奏的音域內。 | math, typing | note_to_midi()fold_note_into_range()apply_playable_range_mapping() | 
| midi_to_keyboard.py | 模擬實體鍵盤輸出，將 MIDI 時間軸事件與虛擬鍵盤按鍵映射，透過 keyboard 控制按壓時機與長度。 | keyboard, mido, time, dataclasses, midi_rule_engine | DEFAULT_NOTE_MAPCleanNoteEvent (Class)play_midi_as_keyboard() | 
| midi_rule_engine.py | 基礎 MIDI 清理引擎，基於規則過濾雜訊 (過短或過輕的音符)、處理量化及 37 鍵音域自動適應。 | mido, dataclasses, pathlib, midi_to_keyboard | RuleNote (Class)CLEAN_37KEY_MIDI_NAMEDEFAULT_37KEY_CLEAN_OPTIONS | 
| midi_range.py | 範圍匯出工具，根據使用者指定的開始與結束時間，裁切出對應的 MIDI 區段並重新對齊時間軸。 | pathlib, midi_rule_engine | CHORUS_MIDI_NAMEexport_midi_range() | 
| midi_editor.py | 異常音符偵測與編輯，掃描連續相同音高、極短音符或極低力度音符，給予標籤並提供清理儲存機制。 | collections, pathlib, midi_rule_engine | EDITED_37KEY_MIDI_NAMEfind_suspicious_notes() | 
| midi_ai_optimizer.py | 智慧 MIDI 優化與音高修正，支援利用 OpenAI 提示詞或增強規則去除不協和音，維持主旋律順暢度。 | json, urllib, midi_rule_engine, midi_to_keyboard | AI_OPTIMIZED_MIDI_NAMEPITCH_CORRECTED_MIDI_NAMEOPENAI_OPTIMIZER_PROMPT |