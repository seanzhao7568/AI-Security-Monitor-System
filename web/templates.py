INDEX_HTML = """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 個人安全輔助系統</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #081225;
      color: #e2e8f0;
      margin: 0;
    }
    .wrap {
      max-width: 1380px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      margin: 0 0 16px;
      font-size: 28px;
      font-weight: 800;
    }
    .grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
    }
    .card {
      background: #0b162d;
      border: 1px solid #1f3250;
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 10px 30px rgba(0,0,0,.25);
    }
    .video {
      width: 100%;
      border-radius: 14px;
      border: 1px solid #334155;
      background: #000;
      display: block;
    }
    .row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 16px;
    }
    button {
      border: none;
      border-radius: 12px;
      padding: 10px 16px;
      cursor: pointer;
      font-weight: 700;
      font-size: 16px;
    }
    .primary { background: #2563eb; color: white; }
    .danger { background: #ef2b2b; color: white; }
    .ghost { background: #334155; color: white; }
    .badge {
      display: inline-block;
      padding: 8px 14px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 16px;
      margin-bottom: 14px;
    }
    .safe { background: #0d7b59; color: white; }
    .warn { background: #a25d09; color: white; }
    .danger-badge { background: #a61b1b; color: white; }
    .kv {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px 16px;
      margin-top: 8px;
    }
    .kv div {
      padding: 12px 0;
      border-bottom: 1px solid #1f3250;
      font-size: 15px;
    }
    .small {
      font-size: 13px;
      color: #94a3b8;
      line-height: 1.5;
    }
    input {
      width: 100%;
      box-sizing: border-box;
      background: #081225;
      color: #e2e8f0;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 11px 12px;
      font-size: 16px;
    }
    .input-wrap {
      position: relative;
      margin-top: 10px;
    }
    .input-wrap input {
      margin-top: 0;
      padding-right: 48px;
    }
    .eye-btn {
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      border: none;
      background: transparent;
      color: #94a3b8;
      cursor: pointer;
      font-size: 18px;
      padding: 4px 6px;
    }
    .section-title {
      margin-top: 24px;
      margin-bottom: 10px;
      font-size: 18px;
      font-weight: 800;
    }
    .module-box {
      margin-top: 12px;
      border: 1px solid #334155;
      border-radius: 14px;
      overflow: hidden;
      background: #081225;
    }
    .module-header {
      padding: 14px 14px;
      cursor: pointer;
      font-weight: 800;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
    }
    .module-menu {
      display: none;
      padding: 10px 12px 14px;
      border-top: 1px solid #1f3250;
    }
    .toggle-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 10px 12px;
      margin-top: 8px;
      background: #0b1220;
      border: 1px solid #334155;
      border-radius: 12px;
      font-size: 16px;
    }
    .toggle-item input[type="checkbox"] {
      width: 18px;
      height: 18px;
      margin: 0;
      flex: 0 0 auto;
    }
    .reason-list {
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .chip {
      background: #16243c;
      border: 1px solid #334155;
      color: #e2e8f0;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      font-weight: 700;
    }
    @media (max-width: 900px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>AI 個人安全輔助系統</h1>
    <div class="grid">
      <div class="card">
        <img class="video" src="/video_feed" alt="video">
        <div class="row">
          <button class="primary" onclick="postJson('/start')">開始監控</button>
          <button class="danger" onclick="postJson('/stop')">停止監控</button>
          <button class="ghost" onclick="testTelegram()">測試 Telegram</button>
        </div>
      </div>
      <div class="card">
        <div id="levelBadge" class="badge safe">SAFE</div>
        <div class="kv">
          <div>系統狀態</div><div id="running">-</div>
          <div>主原因</div><div id="reason">-</div>
          <div>風險分數</div><div id="risk_score">0</div>
          <div>人物面積比</div><div id="ratio">-</div>
          <div>武器命中</div><div id="weapon">0 / 8</div>
          <div>武器類別</div><div id="weapon_name">-</div>
          <div>武器信心值</div><div id="weapon_conf">-</div>
          <div>攻擊動作分數</div><div id="aggro_motion">-</div>
          <div>噪音分貝</div><div id="noise_dbfs">-</div>
          <div>背景噪音</div><div id="noise_floor">-</div>
          <div>即時 FPS</div><div id="fps">-</div>
          <div>最近更新</div><div id="time">-</div>
        </div>
        <div class="section-title">觸發原因</div>
        <div id="reasonList" class="reason-list"></div>
        <div class="section-title">Telegram 設定</div>
        <div class="small">直接在頁面更新</div>
        <div class="input-wrap">
          <input id="token" type="password" placeholder="Bot Token">
          <button type="button" class="eye-btn" onclick="toggleSecret('token', this)">👁</button>
        </div>
        <div class="input-wrap">
          <input id="chat_id" type="password" placeholder="Chat ID">
          <button type="button" class="eye-btn" onclick="toggleSecret('chat_id', this)">👁</button>
        </div>
        <div class="row">
          <button class="primary" onclick="saveTelegram()">儲存設定</button>
        </div>
        <div class="section-title">功能開關</div>
        <div class="small">點一下標題才會展開下面的功能列表。</div>
        <div class="module-box">
          <div class="module-header" onclick="toggleModuleMenu()">
            <span>功能開關</span>
            <span id="moduleArrow">▼</span>
          </div>
          <div id="moduleMenu" class="module-menu">
            <label class="toggle-item"><span>1. 人靠近偵測</span><input type="checkbox" id="tg_person_close"></label>
            <label class="toggle-item"><span>2. 武器偵測</span><input type="checkbox" id="tg_weapon_detection"></label>
            <label class="toggle-item"><span>3. 攻擊動作偵測</span><input type="checkbox" id="tg_aggro_detection"></label>
            <label class="toggle-item"><span>4. 巨響偵測</span><input type="checkbox" id="tg_noise_detection"></label>
            <label class="toggle-item"><span>5. 風險融合</span><input type="checkbox" id="tg_risk_fusion"></label>
            <label class="toggle-item"><span>6. 警報系統</span><input type="checkbox" id="tg_alert_system"></label>
            <div class="row"><button class="primary" onclick="saveToggles()">儲存功能開關</button></div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <script>
    async function postJson(url, body = {}) {
      const r = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
      });
      return await r.json();
    }
    function toggleSecret(id, btn) {
      const el = document.getElementById(id);
      if (el.type === 'password') {
        el.type = 'text';
        btn.textContent = '🙈';
      } else {
        el.type = 'password';
        btn.textContent = '👁';
      }
    }
    function toggleModuleMenu() {
      const menu = document.getElementById('moduleMenu');
      const arrow = document.getElementById('moduleArrow');
      if (menu.style.display === 'block') {
        menu.style.display = 'none';
        arrow.textContent = '▼';
      } else {
        menu.style.display = 'block';
        arrow.textContent = '▲';
      }
    }
    async function saveTelegram() {
      const res = await postJson('/api/config/telegram', {
        token: document.getElementById('token').value,
        chat_id: document.getElementById('chat_id').value
      });
      alert(res.message || 'Telegram 設定已更新');
    }
    async function saveToggles() {
      const res = await postJson('/api/config/toggles', {
        person_close: document.getElementById('tg_person_close').checked,
        weapon_detection: document.getElementById('tg_weapon_detection').checked,
        aggro_detection: document.getElementById('tg_aggro_detection').checked,
        noise_detection: document.getElementById('tg_noise_detection').checked,
        risk_fusion: document.getElementById('tg_risk_fusion').checked,
        alert_system: document.getElementById('tg_alert_system').checked
      });
      alert(res.message || '功能開關已更新');
    }
    async function testTelegram() {
      const res = await postJson('/api/test_telegram');
      alert(res.message || '已送出');
    }
    function renderReasonList(reasons) {
      const box = document.getElementById('reasonList');
      box.innerHTML = '';
      if (!reasons || reasons.length === 0) {
        box.innerHTML = '<span class="chip">無</span>';
        return;
      }
      reasons.forEach(r => {
        const el = document.createElement('span');
        el.className = 'chip';
        el.textContent = r;
        box.appendChild(el);
      });
    }
    async function refreshStatus() {
      const r = await fetch('/api/status');
      const s = await r.json();
      const badge = document.getElementById('levelBadge');
      if (s.level === 2) {
        badge.textContent = 'DANGER';
        badge.className = 'badge danger-badge';
      } else if (s.level === 1) {
        badge.textContent = 'WARNING';
        badge.className = 'badge warn';
      } else {
        badge.textContent = 'SAFE';
        badge.className = 'badge safe';
      }
      document.getElementById('running').textContent = s.running ? '執行中' : '已停止';
      document.getElementById('reason').textContent = s.reason || '-';
      document.getElementById('risk_score').textContent = s.risk_score ?? 0;
      document.getElementById('ratio').textContent = s.close_area_ratio == null ? '-' : Number(s.close_area_ratio).toFixed(3);
      document.getElementById('weapon').textContent = `${s.weapon_hits || 0} / ${s.weapon_window || 0}`;
      document.getElementById('weapon_name').textContent = s.weapon_best_name || '-';
      document.getElementById('weapon_conf').textContent = s.weapon_best_conf == null ? '-' : Number(s.weapon_best_conf).toFixed(2);
      document.getElementById('aggro_motion').textContent = s.aggro_motion == null ? '-' : Number(s.aggro_motion).toFixed(2);
      document.getElementById('noise_dbfs').textContent = s.noise_dbfs == null ? '-' : Number(s.noise_dbfs).toFixed(1);
      document.getElementById('noise_floor').textContent = s.noise_floor == null ? '-' : Number(s.noise_floor).toFixed(1);
      document.getElementById('fps').textContent = s.fps == null ? '-' : Number(s.fps).toFixed(1);
      document.getElementById('time').textContent = new Date((s.timestamp || 0) * 1000).toLocaleString();
      renderReasonList(s.risk_reasons || []);
      if (!window.telegramInit) {
        document.getElementById('token').value = s.telegram_token || '';
        document.getElementById('chat_id').value = s.telegram_chat_id || '';
        window.telegramInit = true;
      }
      if (!window.togglesInit) {
        const t = s.toggles || {};
        document.getElementById('tg_person_close').checked = !!t.person_close;
        document.getElementById('tg_weapon_detection').checked = !!t.weapon_detection;
        document.getElementById('tg_aggro_detection').checked = !!t.aggro_detection;
        document.getElementById('tg_noise_detection').checked = !!t.noise_detection;
        document.getElementById('tg_risk_fusion').checked = !!t.risk_fusion;
        document.getElementById('tg_alert_system').checked = !!t.alert_system;
        window.togglesInit = true;
      }
    }
    refreshStatus();
    setInterval(refreshStatus, 1000);
  </script>
</body>
</html>
"""
