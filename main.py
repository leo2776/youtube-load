import os
import json
import time
import threading
from flask import Flask, render_template_string, jsonify, request

CONFIG_FILE = "stream_master_db.json"
DELETION_LOG = "user_deletion.log"

# 預設線上音樂清單 (輕量化串流連結)
DEFAULT_MUSIC_LIST = [
    {"name": "☕ Lofi 輕鬆輕音樂 (預設)", "url": "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3?filename=lofi-study-112191.mp3"},
    {"name": "🎮 遊戲電子輕快風格", "url": "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a7321f.mp3?filename=chiptune-groove-110025.mp3"},
    {"name": "🌧️ 舒適雨天放鬆背景音", "url": "https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3?filename=relaxing-mountains-141317.mp3"}
]

# 經典預設主題場面 (無 AI 罐頭感、無誇張表情符號)
CLASSIC_SCENES = {
    "scene_start_default": {
        "id": "scene_start_default",
        "name": "開播準備畫面中",
        "title": "直播馬上開始，先找個舒服的位置坐下吧",
        "subtitle": "趁現在去拿杯飲料或小零食，準備好就可以開看囉",
        "game_name": "Roblox",
        "primary_color": "#1e1b4b",
        "secondary_color": "#0f172a",
        "accent_color": "#38bdf8",
        "timer_minutes": 5,
        "enable_timer": True,
        "enable_music": True,
        "music_url": DEFAULT_MUSIC_LIST[0]["url"],
        "status": "idle",
        "early_end_title": "設定完成，準備開播",
        "early_end_subtitle": "大家久等了，直接切換進遊戲",
        "timer_end_title": "倒數結束，準備開播",
        "timer_end_subtitle": "畫面切換中，馬上開始"
    },
    "scene_rest_default": {
        "id": "scene_rest_default",
        "name": "中場休息畫面",
        "title": "主播暫時離開一下",
        "subtitle": "去伸展一下、喝個水，大家也可以休息眼睛，很快就回來",
        "game_name": "Roblox",
        "primary_color": "#0f172a",
        "secondary_color": "#1e293b",
        "accent_color": "#a855f7",
        "timer_minutes": 5,
        "enable_timer": True,
        "enable_music": True,
        "music_url": DEFAULT_MUSIC_LIST[0]["url"],
        "status": "idle",
        "early_end_title": "提前返回",
        "early_end_subtitle": "水喝完了，繼續下一階段的遊戲",
        "timer_end_title": "休息時間結束",
        "timer_end_subtitle": "主播已回到座位，馬上繼續"
    },
    "scene_tech_issue": {
        "id": "scene_tech_issue",
        "name": "網路與設備微調畫面",
        "title": "稍微調整一下設備與網路",
        "subtitle": "遇到了一點小狀況，正在緊急排除聲音和畫面，大家稍等我一下下",
        "game_name": "Roblox",
        "primary_color": "#18181b",
        "secondary_color": "#09090b",
        "accent_color": "#f43f5e",
        "timer_minutes": 3,
        "enable_timer": True,
        "enable_music": True,
        "music_url": DEFAULT_MUSIC_LIST[0]["url"],
        "status": "idle",
        "early_end_title": "問題順利排除",
        "early_end_subtitle": "感謝大家的耐心等待，馬上恢復直播",
        "timer_end_title": "調整完畢",
        "timer_end_subtitle": "設備已正常，準備重回遊戲"
    },
    "scene_ending": {
        "id": "scene_ending",
        "name": "關播準備畫面",
        "title": "今天的直播就到這裡囉",
        "subtitle": "謝謝大家今天的陪伴與聊天，辛苦了，大家晚安",
        "game_name": "Roblox",
        "primary_color": "#022c22",
        "secondary_color": "#064e3b",
        "accent_color": "#34d399",
        "timer_minutes": 3,
        "enable_timer": True,
        "enable_music": True,
        "music_url": DEFAULT_MUSIC_LIST[0]["url"],
        "status": "idle",
        "early_end_title": "直播正式結束",
        "early_end_subtitle": "感謝大家，我們下次見",
        "timer_end_title": "直播結束",
        "timer_end_subtitle": "祝大家有個美好的一天，下次見"
    }
}

# ----------------------------------------------------
# 🛡️ 檔案資料庫讀寫與自動修復邏輯
# ----------------------------------------------------
def check_and_restore_db():
    user_deleted = os.path.exists(DELETION_LOG)
    if not os.path.exists(CONFIG_FILE):
        if user_deleted:
            init_data = {"active_scene": "", "global_timer_seconds": 0, "scenes": {}}
        else:
            init_data = {
                "active_scene": "scene_start_default",
                "global_timer_seconds": 0,
                "scenes": CLASSIC_SCENES
            }
        save_db(init_data)

def load_db():
    check_and_restore_db()
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def log_user_deletion():
    with open(DELETION_LOG, 'a', encoding='utf-8') as f:
        f.write(f"使用者手動清空資料庫時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# ----------------------------------------------------
# 🖥️ 前台 OBS Overlay 頁面 (支援動態 Audio 串流播放，不預先下載整檔)
# ----------------------------------------------------
DISPLAY_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>Stream Overlay</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@700;900&family=Orbitron:wght@900&display=swap');
        
        html, body {
            width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
            background: #05070f; color: #fff; font-family: 'Noto Sans TC', sans-serif;
        }

        .bg-canvas {
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 1;
            background: radial-gradient(circle at 50% 50%, var(--primary-color, #1e1b4b), var(--secondary-color, #0f172a));
            transition: background 0.8s ease;
        }

        .viewport-container {
            position: relative; z-index: 10; width: 100vw; height: 100vh;
            display: flex; flex-direction: column; justify-content: center; align-items: center;
            padding: 40px; box-sizing: border-box; text-align: center;
        }

        .glass-card {
            background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(20px);
            border: 2px solid rgba(255, 255, 255, 0.15); border-radius: 32px;
            padding: 60px 80px; max-width: 1200px; width: 90%;
            box-shadow: 0 20px 50px rgba(0,0,0,0.6);
            display: flex; flex-direction: column; align-items: center; gap: 20px;
        }

        .game-tag {
            font-size: 24px; font-weight: 700; color: var(--accent-color, #38bdf8);
            background: rgba(255,255,255,0.08); padding: 8px 22px; border-radius: 50px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .main-title { font-size: 58px; font-weight: 900; margin: 10px 0; line-height: 1.2; }
        .sub-title { font-size: 26px; color: #cbd5e1; font-weight: 700; line-height: 1.4; }

        .timer-box {
            margin-top: 20px; background: rgba(0, 0, 0, 0.5);
            border: 2px solid var(--accent-color, #38bdf8); border-radius: 20px;
            padding: 15px 40px; display: flex; align-items: center; gap: 15px;
            box-shadow: 0 0 20px var(--accent-color, #38bdf8);
        }

        .timer-digits {
            font-family: 'Orbitron', monospace; font-size: 52px; font-weight: 900;
            color: #fff; letter-spacing: 2px;
        }
    </style>
</head>
<body>
    <div class="bg-canvas" id="bg"></div>

    <div class="viewport-container">
        <div class="glass-card">
            <div class="game-tag" id="game-tag"><span id="game-text"></span></div>
            <div class="main-title" id="main-title">載入中...</div>
            <div class="sub-title" id="sub-title"></div>

            <div class="timer-box" id="timer-box" style="display:none;">
                <i class="fa-regular fa-clock" style="font-size:36px; color:var(--accent-color);"></i>
                <div class="timer-digits" id="timer-digits">00:00</div>
            </div>
        </div>
    </div>

    <!-- 動態串流音訊標籤 (不啟用 preload 防止笨重載入) -->
    <audio id="bgm" loop preload="none"></audio>

    <script>
        let currentAudioUrl = "";

        function updateOverlay() {
            fetch('/api/state')
                .then(res => res.json())
                .then(data => {
                    const sc = data.scene;
                    if (!sc) return;

                    const status = data.status;
                    const timerSec = data.timer_seconds;

                    document.documentElement.style.setProperty('--primary-color', sc.primary_color || '#1e1b4b');
                    document.documentElement.style.setProperty('--secondary-color', sc.secondary_color || '#0f172a');
                    document.documentElement.style.setProperty('--accent-color', sc.accent_color || '#38bdf8');

                    document.getElementById('game-text').innerText = sc.game_name || 'Roblox';

                    if (status === 'early_ended') {
                        document.getElementById('main-title').innerText = sc.early_end_title || "提前結束";
                        document.getElementById('sub-title').innerText = sc.early_end_subtitle || "請稍候...";
                        document.getElementById('timer-box').style.display = 'none';
                    } else if (status === 'ended') {
                        document.getElementById('main-title').innerText = sc.timer_end_title || "計時結束";
                        document.getElementById('sub-title').innerText = sc.timer_end_subtitle || "準備開播！";
                        document.getElementById('timer-box').style.display = 'none';
                    } else {
                        document.getElementById('main-title').innerText = sc.title;
                        document.getElementById('sub-title').innerText = sc.subtitle;

                        if (sc.enable_timer && status === 'counting') {
                            document.getElementById('timer-box').style.display = 'flex';
                            const m = String(Math.floor(timerSec / 60)).padStart(2, '0');
                            const s = String(timerSec % 60).padStart(2, '0');
                            document.getElementById('timer-digits').innerText = `${m}:${s}`;
                        } else {
                            document.getElementById('timer-box').style.display = 'none';
                        }
                    }

                    // 動態音訊串流管理 (只有當音樂 URL 改變或需要開啟時才進行串流載入)
                    const bgm = document.getElementById('bgm');
                    if (sc.enable_music && sc.music_url) {
                        if (currentAudioUrl !== sc.music_url) {
                            currentAudioUrl = sc.music_url;
                            bgm.src = sc.music_url;
                            bgm.load(); // 啟動動態串流
                        }
                        if (bgm.paused) {
                            bgm.play().catch(()=>{});
                        }
                    } else {
                        bgm.pause();
                    }
                });
        }
        setInterval(updateOverlay, 400);
    </script>
</body>
</html>
"""

# ----------------------------------------------------
# 🎛️ 後台管理頁面 (完整頂部控制條 + 色調選取器 + 音量 + 完整積木庫)
# ----------------------------------------------------
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>OBS 直播中控台</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <script src="https://unpkg.com/blockly/blockly_compressed.js"></script>
    <script src="https://unpkg.com/blockly/blocks_compressed.js"></script>
    <script src="https://unpkg.com/blockly/javascript_compressed.js"></script>
    <script src="https://unpkg.com/blockly/msg/zh-hant.js"></script>
    
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; background: #0c0a09; color: #f5f5f4; margin: 0; padding: 20px; }
        
        /* 頂部全功能控制列 (色調 + 音量 + 背景音樂) */
        .top-bar {
            background: #1c1917; border: 1px solid #292524; border-radius: 12px; padding: 15px 25px;
            display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4); flex-wrap: wrap; gap: 15px;
        }
        .top-bar-title { font-size: 20px; font-weight: bold; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
        .top-controls { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
        .control-item { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; }

        .grid { display: grid; grid-template-columns: 340px 1fr; gap: 20px; max-width: 1400px; margin: 0 auto; }
        .card { background: #1c1917; border: 1px solid #292524; padding: 20px; border-radius: 12px; margin-bottom: 20px; }
        .btn { background: #2563eb; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-bottom: 10px; transition: 0.2s; }
        .btn:hover { opacity: 0.9; }
        .btn-danger { background: #dc2626; }
        .btn-success { background: #16a34a; }
        .scene-item { padding: 12px; background: #0c0a09; border: 1px solid #292524; border-radius: 8px; margin-bottom: 8px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .scene-item.active { border-color: #38bdf8; background: #1e293b; font-weight: bold; }
        
        input[type="text"], input[type="number"], select {
            width: 100%; padding: 10px; margin-bottom: 12px; background: #0c0a09; border: 1px solid #292524; color: #fff; border-radius: 6px; box-sizing: border-box;
        }
        
        .color-group { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .color-picker-wrapper { display: flex; flex-direction: column; gap: 5px; font-size: 12px; }
        .color-picker-wrapper input[type="color"] { width: 100%; height: 38px; border: none; cursor: pointer; background: transparent; }

        #blocklyDiv { width: 100%; height: 320px; border-radius: 8px; border: 1px solid #292524; }
    </style>
</head>
<body>

    <!-- 頂部全功能設定條 (含畫面色調、音樂動態選擇) -->
    <div class="top-bar">
        <div class="top-bar-title"><i class="fa-solid fa-palette"></i> OBS 直播中控台 (包含主題色調與音樂串流設定)</div>
        <div class="top-controls">
            <!-- 音樂選擇器 -->
            <div class="control-item">
                <i class="fa-solid fa-music" style="color:#a855f7;"></i>
                <span>背景音樂:</span>
                <select id="top-music-select" style="width: 240px; margin: 0;" onchange="updateTopControls()">
                    <option value="https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3?filename=lofi-study-112191.mp3">☕ Lofi 輕鬆輕音樂</option>
                    <option value="https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c8a7321f.mp3?filename=chiptune-groove-110025.mp3">🎮 遊戲電子輕快風格</option>
                    <option value="https://cdn.pixabay.com/download/audio/2022/01/18/audio_d0a13f69d2.mp3?filename=relaxing-mountains-141317.mp3">🌧️ 舒適雨天放鬆背景音</option>
                </select>
            </div>
            
            <!-- 色調調整條 -->
            <div class="control-item">
                <i class="fa-solid fa-droplet" style="color:#38bdf8;"></i>
                <span>主背景色:</span>
                <input type="color" id="top-primary-color" style="width:40px; height:30px; border:none; cursor:pointer;" onchange="updateTopControls()">
            </div>
            <div class="control-item">
                <span>次背景色:</span>
                <input type="color" id="top-secondary-color" style="width:40px; height:30px; border:none; cursor:pointer;" onchange="updateTopControls()">
            </div>
            <div class="control-item">
                <span>強調文字色:</span>
                <input type="color" id="top-accent-color" style="width:40px; height:30px; border:none; cursor:pointer;" onchange="updateTopControls()">
            </div>
        </div>
    </div>

    <div class="grid">
        <!-- 左側面板 -->
        <div>
            <div class="card">
                <h3>主題場面專案</h3>
                <div id="scene-list"></div>
                <button class="btn btn-success" onclick="createNewScene()">➕ 建立新主題專案</button>
                <button class="btn btn-danger" onclick="clearAllData()">🗑️ 清空專案 (記錄日誌)</button>
            </div>

            <div class="card">
                <h3>即時動作控制</h3>
                <button class="btn btn-success" onclick="triggerAction('start_timer')">▶️ 開始倒數計時</button>
                <button class="btn btn-danger" onclick="triggerAction('early_end')">⏹️ 提前結束</button>
                <button class="btn" style="background:#52525b" onclick="triggerAction('reset')">🔄 重置預設畫面</button>
            </div>
        </div>

        <!-- 右側面板 -->
        <div>
            <div class="card">
                <h3>場面詳細內容與色調調整</h3>
                <label>場面名稱</label><input type="text" id="edit-name">
                <label>遊戲名稱</label><input type="text" id="edit-game">
                <label>主標語</label><input type="text" id="edit-title">
                <label>副標語</label><input type="text" id="edit-subtitle">
                
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <div><label>倒數時間 (分鐘)</label><input type="number" id="edit-timer"></div>
                    <div>
                        <label>音樂啟用</label>
                        <select id="edit-enable-music">
                            <option value="true">開啟背景音樂</option>
                            <option value="false">靜音關閉</option>
                        </select>
                    </div>
                </div>

                <!-- 色彩選取區 -->
                <label>場面顏色配色設定</label>
                <div class="color-group">
                    <div class="color-picker-wrapper">
                        <span>主要背景色</span>
                        <input type="color" id="edit-primary-color" onchange="syncColorsToTop()">
                    </div>
                    <div class="color-picker-wrapper">
                        <span>次要背景色</span>
                        <input type="color" id="edit-secondary-color" onchange="syncColorsToTop()">
                    </div>
                    <div class="color-picker-wrapper">
                        <span>強調文字色</span>
                        <input type="color" id="edit-accent-color" onchange="syncColorsToTop()">
                    </div>
                </div>

                <br>
                <h3>🧩 完整積木編輯器 (音樂串流與狀態控制)</h3>
                <div id="blocklyDiv"></div>

                <br>
                <button class="btn btn-success" onclick="saveConfig()">💾 儲存並同步至 OBS</button>
            </div>
        </div>
    </div>

    <!-- 完整工具箱 -->
    <xml id="toolbox" style="display: none">
        <category name="🎵 背景音樂控制" colour="#a855f7">
            <block type="set_bg_music"></block>
            <block type="play_default_music"></block>
            <block type="play_original_music"></block>
            <block type="toggle_music_state"></block>
        </category>
        <category name="🌐 網頁狀態邏輯" colour="#5b80a5">
            <block type="event_web_started"></block>
            <block type="check_web_is_first"></block>
        </category>
        <category name="🔀 條件判斷" colour="#5b9fa5">
            <block type="controls_if"></block>
        </category>
    </xml>

    <script>
        let workspace = null;
        let currentSceneId = "";

        // 積木定義
        Blockly.Blocks['set_bg_music'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField("設定背景音樂網址")
                    .appendField(new Blockly.FieldTextInput("https://..."), "MUSIC_URL");
                this.setPreviousStatement(true, null);
                this.setNextStatement(true, null);
                this.setColour('#a855f7');
            }
        };

        Blockly.Blocks['play_default_music'] = {
            init: function() {
                this.appendDummyInput().appendField("播放預設背景音樂");
                this.setPreviousStatement(true, null);
                this.setNextStatement(true, null);
                this.setColour('#a855f7');
            }
        };

        Blockly.Blocks['play_original_music'] = {
            init: function() {
                this.appendDummyInput().appendField("播放原本的背景音樂");
                this.setPreviousStatement(true, null);
                this.setNextStatement(true, null);
                this.setColour('#a855f7');
            }
        };

        Blockly.Blocks['toggle_music_state'] = {
            init: function() {
                this.appendDummyInput()
                    .appendField("背景音樂開關")
                    .appendField(new Blockly.FieldDropdown([["開啟", "TRUE"], ["關閉", "FALSE"]]), "STATE");
                this.setPreviousStatement(true, null);
                this.setNextStatement(true, null);
                this.setColour('#a855f7');
            }
        };

        Blockly.Blocks['event_web_started'] = {
            init: function() {
                this.appendDummyInput().appendField("當網頁服務被開啟時");
                this.appendStatementInput("DO").setCheck(null).appendField("那麼");
                this.setColour(120);
            }
        };

        Blockly.Blocks['check_web_is_first'] = {
            init: function() {
                this.appendDummyInput().appendField("網頁已開啟 (檢查重複開啟)");
                this.setOutput(true, "Boolean");
                this.setColour(210);
            }
        };

        function initBlockly() {
            workspace = Blockly.inject('blocklyDiv', {
                toolbox: document.getElementById('toolbox'),
                scrollbars: true
            });
        }

        function loadAdmin() {
            fetch('/api/config')
                .then(res => res.json())
                .then(data => {
                    currentSceneId = data.active_scene;
                    const list = document.getElementById('scene-list');
                    list.innerHTML = '';

                    for (let id in data.scenes) {
                        const sc = data.scenes[id];
                        const div = document.createElement('div');
                        div.className = `scene-item ${id === currentSceneId ? 'active' : ''}`;
                        div.innerHTML = `<span>${sc.name}</span> <i class="fa-solid fa-chevron-right"></i>`;
                        div.onclick = () => switchScene(id);
                        list.appendChild(div);
                    }

                    if (data.scenes[currentSceneId]) {
                        const cur = data.scenes[currentSceneId];
                        document.getElementById('edit-name').value = cur.name;
                        document.getElementById('edit-game').value = cur.game_name;
                        document.getElementById('edit-title').value = cur.title;
                        document.getElementById('edit-subtitle').value = cur.subtitle;
                        document.getElementById('edit-timer').value = cur.timer_minutes;
                        document.getElementById('edit-enable-music').value = cur.enable_music ? "true" : "false";

                        // 色彩同步
                        document.getElementById('edit-primary-color').value = cur.primary_color || '#1e1b4b';
                        document.getElementById('edit-secondary-color').value = cur.secondary_color || '#0f172a';
                        document.getElementById('edit-accent-color').value = cur.accent_color || '#38bdf8';

                        document.getElementById('top-primary-color').value = cur.primary_color || '#1e1b4b';
                        document.getElementById('top-secondary-color').value = cur.secondary_color || '#0f172a';
                        document.getElementById('top-accent-color').value = cur.accent_color || '#38bdf8';

                        document.getElementById('top-music-select').value = cur.music_url || '';
                    }
                });
        }

        function syncColorsToTop() {
            document.getElementById('top-primary-color').value = document.getElementById('edit-primary-color').value;
            document.getElementById('top-secondary-color').value = document.getElementById('edit-secondary-color').value;
            document.getElementById('top-accent-color').value = document.getElementById('edit-accent-color').value;
        }

        function updateTopControls() {
            document.getElementById('edit-primary-color').value = document.getElementById('top-primary-color').value;
            document.getElementById('edit-secondary-color').value = document.getElementById('top-secondary-color').value;
            document.getElementById('edit-accent-color').value = document.getElementById('top-accent-color').value;
            saveConfig();
        }

        function switchScene(id) {
            fetch('/api/switch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({scene_id: id})
            }).then(() => loadAdmin());
        }

        function saveConfig() {
            const payload = {
                id: currentSceneId,
                name: document.getElementById('edit-name').value,
                game_name: document.getElementById('edit-game').value,
                title: document.getElementById('edit-title').value,
                subtitle: document.getElementById('edit-subtitle').value,
                timer_minutes: parseInt(document.getElementById('edit-timer').value),
                enable_music: document.getElementById('edit-enable-music').value === "true",
                primary_color: document.getElementById('edit-primary-color').value,
                secondary_color: document.getElementById('edit-secondary-color').value,
                accent_color: document.getElementById('edit-accent-color').value,
                music_url: document.getElementById('top-music-select').value
            };

            fetch('/api/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
        }

        function triggerAction(act) {
            fetch('/api/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: act})
            });
        }

        function clearAllData() {
            if (confirm("確定要清空專案嗎？清空後系統將手動新建！")) {
                fetch('/api/clear_all', { method: 'POST' }).then(() => loadAdmin());
            }
        }

        function createNewScene() {
            const name = prompt("請輸入新主題名稱：");
            if (name) {
                fetch('/api/create', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name})
                }).then(() => loadAdmin());
            }
        }

        window.onload = () => { initBlockly(); loadAdmin(); };
    </script>
</body>
</html>
"""

# ----------------------------------------------------
# 🚀 Flask 後端 API 邏輯
# ----------------------------------------------------
app = Flask(__name__)

web_active_flag = False

@app.route('/')
def route_index():
    return "<h1>OBS 直播中控台已啟動</h1><p>前台：<a href='/display'>/display</a></p><p>後台：<a href='/admin'>/admin</a></p>"

@app.route('/display')
def route_display():
    global web_active_flag
    if not web_active_flag:
        web_active_flag = True
    return render_template_string(DISPLAY_HTML)

@app.route('/admin')
def route_admin():
    return render_template_string(ADMIN_HTML)

@app.route('/api/config')
def api_config():
    return jsonify(load_db())

@app.route('/api/state')
def api_state():
    db = load_db()
    active_id = db.get('active_scene', '')
    scene = db['scenes'].get(active_id, {})
    return jsonify({
        "status": scene.get('status', 'idle'),
        "timer_seconds": db.get('global_timer_seconds', 0),
        "scene": scene,
        "is_first_web": web_active_flag
    })

@app.route('/api/switch', methods=['POST'])
def api_switch():
    db = load_db()
    req = request.get_json()
    db['active_scene'] = req['scene_id']
    if req['scene_id'] in db['scenes']:
        db['scenes'][req['scene_id']]['status'] = 'idle'
    db['global_timer_seconds'] = 0
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/update', methods=['POST'])
def api_update():
    db = load_db()
    req = request.get_json()
    sc_id = req['id']
    if sc_id in db['scenes']:
        db['scenes'][sc_id].update(req)
        save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/action', methods=['POST'])
def api_action():
    db = load_db()
    act = request.get_json()['action']
    active_id = db['active_scene']
    if active_id in db['scenes']:
        sc = db['scenes'][active_id]
        if act == 'start_timer':
            sc['status'] = 'counting'
            db['global_timer_seconds'] = sc['timer_minutes'] * 60
        elif act == 'early_end':
            sc['status'] = 'early_ended'
            db['global_timer_seconds'] = 0
        elif act == 'reset':
            sc['status'] = 'idle'
            db['global_timer_seconds'] = 0
        save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/create', methods=['POST'])
def api_create():
    db = load_db()
    req = request.get_json()
    new_id = f"scene_{int(time.time())}"
    db['scenes'][new_id] = {
        "id": new_id,
        "name": req['name'],
        "title": req['name'],
        "subtitle": "準備中，請稍候",
        "game_name": "Roblox",
        "primary_color": "#1e1b4b",
        "secondary_color": "#0f172a",
        "accent_color": "#38bdf8",
        "timer_minutes": 5,
        "enable_timer": True,
        "enable_music": True,
        "music_url": DEFAULT_MUSIC_LIST[0]["url"],
        "status": "idle"
    }
    db['active_scene'] = new_id
    save_db(db)
    return jsonify({"status": "ok"})

@app.route('/api/clear_all', methods=['POST'])
def api_clear_all():
    log_user_deletion()
    db = {"active_scene": "", "global_timer_seconds": 0, "scenes": {}}
    save_db(db)
    return jsonify({"status": "ok"})

def timer_loop():
    while True:
        time.sleep(1)
        try:
            db = load_db()
            active_id = db.get('active_scene')
            if active_id and active_id in db['scenes']:
                sc = db['scenes'][active_id]
                if sc.get('status') == 'counting':
                    sec = db.get('global_timer_seconds', 0)
                    if sec > 0:
                        db['global_timer_seconds'] = sec - 1
                        save_db(db)
                    else:
                        sc['status'] = 'ended'
                        save_db(db)
        except Exception:
            pass

if __name__ == '__main__':
    t = threading.Thread(target=timer_loop, daemon=True)
    t.start()

    print("=" * 60)
    print(" Stream Master 系統已啟動")
    print("👉 OBS 擷取前台 : http://localhost:8080/display")
    print("👉 後台中控台   : http://localhost:8080/admin")
    print("=" * 60)

    app.run(host='0.0.0.0', port=8080, debug=False)
