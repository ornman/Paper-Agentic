/**
 * WPS 宿主桥接层 — V1 论文助手
 *
 * 职责：Ribbon 回调 + 打开右侧 TaskPane
 * 业务逻辑全在 taskpane.html（Vue 应用）中
 */

var LOG_SERVER = 'http://127.0.0.1:3895';

function sendLog(module, level, message) {
  try {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', LOG_SERVER + '/log', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.send(JSON.stringify({
      module: module,
      level: level,
      message: message,
      timestamp: new Date().toISOString()
    }));
  } catch (e) { /* 静默 */ }
}

function OnAddinLoad() {
  sendLog('wps', 'info', 'OnAddinLoad 插件已加载');
  console.log('[WPS Plugin V1] 宿主桥接层已加载');
  return true;
}

function GetUrlPath() {
  var e = document.location.toString();
  return -1 != (e = decodeURI(e)).indexOf('/') && (e = e.substring(0, e.lastIndexOf('/'))), e;
}

function OnOpenPane() {
  sendLog('wps', 'info', 'OnOpenPane 被调用');
  console.log('[WPS Plugin V1] 开始打开 TaskPane');

  try {
    // 检查 Application 对象
    if (typeof Application === 'undefined') {
      sendLog('wps', 'error', 'Application 对象不存在（非 WPS 宿主环境）');
      throw new Error('Application 对象不存在');
    }
    sendLog('wps', 'info', 'Application 对象可用: ' + typeof Application);

    var urlPath = GetUrlPath();
    var taskpaneUrl = urlPath + '/wps-plugin/taskpane.html';
    sendLog('wps', 'info', 'TaskPane URL: ' + taskpaneUrl);
    sendLog('wps', 'info', 'GetUrlPath 返回: ' + urlPath);
    sendLog('wps', 'info', 'document.location: ' + document.location.toString());

    // 检查 CreateTaskPane 方法
    if (typeof Application.CreateTaskPane !== 'function') {
      sendLog('wps', 'error', 'Application.CreateTaskPane 不是函数: ' + typeof Application.CreateTaskPane);
      throw new Error('CreateTaskPane 方法不可用');
    }

    var taskPane = Application.CreateTaskPane(taskpaneUrl);
    sendLog('wps', 'info', 'CreateTaskPane 返回: ' + JSON.stringify({
      type: typeof taskPane,
      keys: taskPane ? Object.keys(taskPane).join(',') : 'null'
    }));

    taskPane.Title = 'AIForScience';
    taskPane.Visible = true;
    taskPane.DockPosition = 2;
    taskPane.Width = 400;

    sendLog('wps', 'info', 'TaskPane 已打开成功');
    console.log('[WPS Plugin V1] TaskPane 已打开');
    return true;
  } catch (error) {
    var message = error && error.message ? error.message : String(error);
    var stack = error && error.stack ? error.stack : '';
    sendLog('wps', 'error', 'OnOpenPane 失败: ' + message + (stack ? '\n' + stack : ''));
    console.error('[WPS Plugin V1] 打开 TaskPane 失败:', message);
    alert('打开 TaskPane 失败: ' + message);
    return false;
  }
}

window.OnAddinLoad = OnAddinLoad;
window.OnOpenPane = OnOpenPane;
window.GetUrlPath = GetUrlPath;
