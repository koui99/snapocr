#!/bin/bash

cat > /home/ubuntu/snipaste-ocr/design/redesign/redesign_A_light.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SnapOCR 风格 A - 浅色版</title>
<style>
:root {
  --primary: #2D7FF9;
  --primary-hover: #1B68DC;
  --primary-active-bg: #EEF4FF;
  --bg-main: #F5F6F8;
  --bg-card: #FFFFFF;
  --text-main: #333333;
  --text-secondary: #666666;
  --text-muted: #999999;
  --border: #E2E4E8;
  --danger: #EF4444;
  --success: #10B981;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --shadow: 0 4px 16px rgba(0,0,0,0.08);
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.06);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: var(--bg-main); padding: 40px; color: var(--text-main); line-height: 1.6; }
h1 { text-align: center; margin-bottom: 40px; font-size: 32px; font-weight: 600; }
.section { background: var(--bg-card); border-radius: var(--radius-lg); padding: 30px; margin-bottom: 40px; box-shadow: var(--shadow); }
.section-title { font-size: 18px; font-weight: 600; margin-bottom: 20px; color: var(--primary); }
.demo-container { position: relative; min-height: 300px; }
.capture-area { position: relative; width: 100%; height: 500px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: var(--radius-md); overflow: visible; }
.capture-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.4); pointer-events: none; }
.selection-box { position: absolute; left: 20%; top: 20%; width: 60%; height: 60%; border: 2px solid var(--primary); }
.selection-handle { position: absolute; width: 8px; height: 8px; background: var(--primary); border: 1px solid #fff; border-radius: 50%; }
.handle-tl { top: -4px; left: -4px; } .handle-tr { top: -4px; right: -4px; } .handle-bl { bottom: -4px; left: -4px; } .handle-br { bottom: -4px; right: -4px; }
.handle-t { top: -4px; left: 50%; transform: translateX(-50%); } .handle-b { bottom: -4px; left: 50%; transform: translateX(-50%); }
.handle-l { top: 50%; left: -4px; transform: translateY(-50%); } .handle-r { top: 50%; right: -4px; transform: translateY(-50%); }
.size-label { position: absolute; top: -30px; left: 0; background: rgba(45,127,249,0.95); color: #fff; padding: 4px 10px; border-radius: var(--radius-sm); font-size: 12px; font-weight: 500; }
.toolbar { position: absolute; right: -10px; bottom: -10px; display: flex; flex-direction: column; gap: 8px; }
.toolbar-row { display: flex; gap: 6px; background: var(--bg-card); padding: 6px; border-radius: var(--radius-md); box-shadow: var(--shadow); }
.tool-btn { width: 32px; height: 32px; border: none; background: transparent; border-radius: var(--radius-sm); cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--text-main); transition: all 0.2s; font-size: 14px; }
.tool-btn:hover { background: var(--primary-active-bg); color: var(--primary); }
.tool-btn.active { background: var(--primary); color: #fff; }
.tool-btn.ocr { background: var(--primary); color: #fff; font-weight: 600; }
.tool-btn.danger:hover { background: #FEE2E2; color: var(--danger); }
.tool-btn.success:hover { background: #D1FAE5; color: var(--success); }
.divider { width: 1px; height: 24px; background: var(--border); align-self: center; margin: 0 2px; }
.prop-bar { display: flex; gap: 8px; background: var(--bg-card); padding: 8px 12px; border-radius: var(--radius-md); box-shadow: var(--shadow); position: absolute; right: -10px; bottom: -60px; align-items: center; }
.stroke-btn { width: 28px; height: 28px; border: 1px solid var(--border); background: var(--bg-card); border-radius: var(--radius-sm); cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.stroke-btn:hover { border-color: var(--primary); }
.stroke-btn.active { border-color: var(--primary); background: var(--primary-active-bg); }
.stroke-line { width: 16px; height: 2px; background: var(--text-main); }
.stroke-line.medium { height: 3px; }
.stroke-line.thick { height: 4px; }
.color-palette { display: flex; gap: 6px; padding-left: 8px; border-left: 1px solid var(--border); }
.color-item { width: 24px; height: 24px; border-radius: 4px; cursor: pointer; border: 2px solid transparent; transition: all 0.2s; }
.color-item:hover { transform: scale(1.1); }
.color-item.active { border-color: var(--primary); box-shadow: 0 0 0 2px var(--bg-card); }
.magnifier { position: absolute; bottom: 30%; right: 15%; width: 140px; height: 140px; background: var(--bg-card); border: 2px solid var(--border); border-radius: var(--radius-md); box-shadow: var(--shadow); padding: 8px; }
.magnifier-grid { width: 100%; height: 100px; background: repeating-linear-gradient(0deg, var(--border) 0, var(--border) 1px, transparent 1px, transparent 10px), repeating-linear-gradient(90deg, var(--border) 0, var(--border) 1px, transparent 1px, transparent 10px); position: relative; }
.magnifier-crosshair { position: absolute; top: 50%; left: 50%; width: 10px; height: 10px; border: 2px solid var(--primary); transform: translate(-50%, -50%); }
.magnifier-info { margin-top: 6px; font-size: 11px; color: var(--text-secondary); text-align: center; }
