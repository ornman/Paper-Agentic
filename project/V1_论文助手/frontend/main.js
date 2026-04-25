/**
 * 历史 WPS 宿主桥接文件。
 * 正式桥接入口使用 frontend/wps-plugin/main.js，构建后复制到 dist/main.js。
 */

function OnAddinLoad() {
  return false;
}

function OnOpenPane() {
  alert('旧调试插件入口已停用，请删除它并只保留 dist/manifest.xml 对应的正式插件。');
  return false;
}

window.OnAddinLoad = OnAddinLoad;
window.OnOpenPane = OnOpenPane;
