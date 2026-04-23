/**
 * WPS 插件桥接层 - V1 项目
 *
 * 负责处理 Ribbon 回调和 TaskPane 打开
 */

function OnAddinLoad() {
  console.log('[WPS Plugin V1] 插件已加载');
  return true;
}

function GetUrlPath() {
  const e = document.location.toString();
  return -1 != (e = decodeURI(e)).indexOf('/') && (e = e.substring(0, e.lastIndexOf('/'))), e;
}

function OnOpenPane() {
  console.log('[WPS Plugin V1] 打开 TaskPane');

  try {
    const taskPane = Application.CreateTaskPane(GetUrlPath() + '/taskpane.html');
    taskPane.Title = '论文写作助手 V1';
    taskPane.Visible = true;
    taskPane.DockPosition = 2; // 右侧停靠
    taskPane.Width = 450;

    console.log('[WPS Plugin V1] TaskPane 已创建');
    return true;
  } catch (error) {
    const message = error?.message ?? String(error);
    console.error('[WPS Plugin V1] 打开失败:', message);
    alert('打开助手失败: ' + message);
    return false;
  }
}

// 挂载到全局
window.OnAddinLoad = OnAddinLoad;
window.OnOpenPane = OnOpenPane;
window.GetUrlPath = GetUrlPath;
