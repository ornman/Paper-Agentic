/**
 * WPS 正式工程宿主桥接层。
 *
 * 这个文件只负责 Ribbon 回调与 TaskPane 打开动作，
 * 不负责真实业务逻辑，也不直接接入 Vue store、后端 API 或 SSE。
 * 原因很简单：Task 4 的目标是先把“宿主外壳”迁移进正式工程，
 * 让后续任务在稳定壳层上继续演进。
 */

/**
 * 插件加载时的回调。
 *
 * Ribbon 的 onLoad 需要是同步函数，
 * 返回 true 代表当前插件壳已经成功初始化。
 */
function OnAddinLoad() {
  console.log('[WPS Plugin] 宿主桥接层已加载');
  return true;
}

/**
 * 获取当前插件页面所在目录。
 *
 * 这里直接沿用已经在 `.tools/wps-debug` 验证过的写法，
 * 因为 WPS 本地插件环境的路径解析有其特殊性，
 * 不值得在正式工程里重新发明一套未经验证的实现。
 */
function GetUrlPath() {
  var e = document.location.toString();
  return -1 != (e = decodeURI(e)).indexOf('/') && (e = e.substring(0, e.lastIndexOf('/'))), e;
}

/**
 * 打开右侧 TaskPane。
 *
 * 这里故意只做最小动作：
 * 1. 创建面板
 * 2. 指向正式工程内的静态 TaskPane 壳
 * 3. 固定停靠在右侧
 *
 * 不在这里读取文档内容，不在这里做轮询，
 * 因为那是 Task 5 的职责。
 */
function OnOpenPane() {
  console.log('[WPS Plugin] 开始打开 TaskPane');

  try {
    var taskPane = Application.CreateTaskPane(GetUrlPath() + '/taskpane.html');
    taskPane.Title = '论文写作助手';
    taskPane.Visible = true;
    taskPane.DockPosition = 2;
    taskPane.Width = 400;

    console.log('[WPS Plugin] TaskPane 已打开');
    return true;
  } catch (error) {
    var message = error && error.message ? error.message : String(error);
    console.error('[WPS Plugin] 打开 TaskPane 失败:', message);
    alert('打开 TaskPane 失败: ' + message);
    return false;
  }
}

// 显式挂到全局，确保 WPS Ribbon 能稳定找到这些回调。
window.OnAddinLoad = OnAddinLoad;
window.OnOpenPane = OnOpenPane;
window.GetUrlPath = GetUrlPath;
