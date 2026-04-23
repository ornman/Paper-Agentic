/**
 * WPS 宿主桥接层 — V1 论文助手
 *
 * 职责：Ribbon 回调 + 打开右侧 TaskPane
 * 业务逻辑全在 taskpane.html（Vue 应用）中
 */

function OnAddinLoad() {
  console.log('[WPS Plugin V1] 宿主桥接层已加载');
  return true;
}

function GetUrlPath() {
  var e = document.location.toString();
  return -1 != (e = decodeURI(e)).indexOf('/') && (e = e.substring(0, e.lastIndexOf('/'))), e;
}

function OnOpenPane() {
  console.log('[WPS Plugin V1] 开始打开 TaskPane');

  try {
    var taskPane = Application.CreateTaskPane(GetUrlPath() + '/taskpane.html');
    taskPane.Title = 'AIForScience';
    taskPane.Visible = true;
    taskPane.DockPosition = 2;
    taskPane.Width = 400;

    console.log('[WPS Plugin V1] TaskPane 已打开');
    return true;
  } catch (error) {
    var message = error && error.message ? error.message : String(error);
    console.error('[WPS Plugin V1] 打开 TaskPane 失败:', message);
    alert('打开 TaskPane 失败: ' + message);
    return false;
  }
}

window.OnAddinLoad = OnAddinLoad;
window.OnOpenPane = OnOpenPane;
window.GetUrlPath = GetUrlPath;
