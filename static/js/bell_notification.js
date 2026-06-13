// 监听来自后端的通知更新
document.addEventListener('DOMContentLoaded', () => {
    // 获取全局 Socket 连接
    const socket = window.globalSocket || (typeof globalSocket !== 'undefined' ? globalSocket : null);
    
    if (!socket) {
        console.warn("🔔 [Socket Client] globalSocket not ready yet. Retrying in 500ms...");
        setTimeout(() => {
            const retrySocket = window.globalSocket || (typeof globalSocket !== 'undefined' ? globalSocket : null);
            if (retrySocket) {
                setupBellSocket(retrySocket);
            } else {
                console.error("🔔 [Socket Client] Failed to find globalSocket even after retry!");
            }
        }, 500);
        return;
    }

    setupBellSocket(socket);
});

function setupBellSocket(socket) {
    console.log("🔔 [Socket Client] bell_notification.js active and listening on globalSocket.");
    
    socket.on('new_notification', function(data) {
        console.log("🔔 [Socket Client] 'new_notification' received:", data);
        
        // 1. 获取角标元素
        const badge = document.getElementById('bell-badge');
        
        if (badge) {
            // 2. data.count 是后端传来的未读总数
            const count = parseInt(data.count || 0); 
            console.log("🔔 [Socket Client] Updating bell badge count to:", count);
            
            // 3. 根据数量更新显示
            if (count > 0) {
                badge.innerText = count > 99 ? '99+' : count;
                badge.style.display = 'flex'; // 显示数字角标 (flex for centering text)
            } else {
                badge.style.display = 'none'; // 没通知就隐藏
            }
        } else {
            console.error("🔔 [Socket Client] Could not find #bell-badge element!");
        }
        
        // 4. 动态在下拉列表中插入新的通知 (Live 实时更新)
        const popupBody = document.querySelector('#notification-popup .popup-body');
        if (popupBody && data.message) {
            console.log("🔔 [Socket Client] Prepending new notification to popup list:", data.message);
            
            // 如果原本是空状态的提示，先清除
            const emptyNotif = popupBody.querySelector('.empty-notif');
            if (emptyNotif) {
                emptyNotif.remove();
            }
            
            // 创建新的通知项
            let newElement;
            if (data.task_id) {
                newElement = document.createElement('a');
                newElement.href = `/task/${data.task_id}`; // Align with base.html link structure
                newElement.className = 'notification-item';
                newElement.innerHTML = `
                    <span class="note-title"><span>✨</span> Job Update</span>
                    <span class="note-msg">${data.message}</span>
                    <span class="note-time">Just Now</span>
                `;
            } else {
                newElement = document.createElement('div');
                newElement.className = 'notification-item';
                newElement.style.cursor = 'default';
                newElement.innerHTML = `
                    <span class="note-title" style="color: #d32f2f;"><span>⚠️</span> System Alert</span>
                    <span class="note-msg">${data.message}</span>
                    <span class="note-time">Just Now</span>
                `;
            }
            
            // 插入在最前面，并限制列表最多只保留 5 个
            popupBody.insertBefore(newElement, popupBody.firstChild);
            const items = popupBody.querySelectorAll('.notification-item, a.notification-item');
            if (items.length > 5) {
                items[items.length - 1].remove();
            }
        } else {
            console.log("🔔 [Socket Client] popupBody or data.message not present, skipping prepend.");
        }
        
        // 触发你原本的提示框 (保持一致性)
        if (typeof window.launchToastAlert === 'function') {
            window.launchToastAlert('New system notification!');
        } else if (typeof launchToastAlert === 'function') {
            launchToastAlert('New system notification!');
        } else {
            console.warn("🔔 [Socket Client] launchToastAlert is not defined.");
        }
    });
}