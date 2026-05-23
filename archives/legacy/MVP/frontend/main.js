/**
 * 论文写作助手 - UI 演示版
 * Ribbon 回调函数
 */

// 插件加载时调用
function OnAddinLoad() {
    console.log('[UI演示版] 插件已加载');
    return true;
}

// 获取当前插件路径
function GetUrlPath() {
    var e = document.location.toString();
    return -1 != (e = decodeURI(e)).indexOf("/") && (e = e.substring(0, e.lastIndexOf("/"))), e;
}

// 打开 TaskPane
function OnOpenPane() {
    console.log('[UI演示版] 打开 TaskPane');
    try {
        var taskPane = Application.CreateTaskPane(GetUrlPath() + "/dist/app.html");
        taskPane.Title = '论文写作助手';
        taskPane.Visible = true;
        taskPane.DockPosition = 2; // 右侧
        taskPane.Width = 400;
        console.log('[UI演示版] TaskPane 已打开');
        return true;
    } catch (e) {
        console.error('[UI演示版] 打开失败:', e.message);
        alert('打开失败: ' + e.message);
        return false;
    }
}

console.log('[UI演示版] main.js 已加载');
