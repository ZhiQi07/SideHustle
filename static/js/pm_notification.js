// static/js/pm_notification.js
document.addEventListener('DOMContentLoaded', () => {
    // 建立一个专门给私聊通知用的 socket 连接，不污染任务栏聊天
    if (typeof pmSocket === 'undefined') {
        window.pmSocket = io();
    }

    // 从全局变量拿当前登录的用户名
    const myUsername = window.currentUsername || "";

    if (window.pmSocket && myUsername) {
        // 专门听后端发来的私聊通知事件 → 点亮红点
        window.pmSocket.on('new_private_notification', function (data) {
            if (data.receiver === myUsername) {
                // 1. 顶部导航栏红点瞬间亮起
                const globalDot = document.getElementById('global-nav-red-dot');
                if (globalDot) {
                    globalDot.style.setProperty('display', 'block', 'important');
                }

                // 2. 如果此时人刚好在 Inbox 页面，顺手把列表对应的人的数字无刷新 +1
                const badge = document.getElementById('badge-partner-' + data.sender);
                if (badge) {
                    if (badge.style.display.includes('none') || badge.style.cssText.includes('display: none')) {
                        badge.style.setProperty('display', 'flex', 'important');
                        badge.innerText = "1";
                    } else {
                        let currentNum = parseInt(badge.innerText.trim()) || 0;
                        badge.innerText = currentNum + 1;
                    }
                }
            }
        });

        // 🆕 监听已读清除事件 → 熄灭红点
        window.pmSocket.on('clear_private_notification', function (data) {
            if (data.receiver === myUsername) {
                const globalDot = document.getElementById('global-nav-red-dot');
                if (globalDot) {
                    globalDot.style.setProperty('display', 'none', 'important');
                }
            }
        });
    }
});