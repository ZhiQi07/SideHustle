// 监听来自后端的通知更新
globalSocket.on('new_notification', function(data) {
    // 1. 获取角标元素
    const badge = document.getElementById('bell-badge');
    
    if (badge) {
        // 2. data.count 是后端传来的未读总数
        const count = parseInt(data.count || 0); 
        
        // 3. 根据数量更新显示
        if (count > 0) {
            badge.innerText = count > 99 ? '99+' : count;
            badge.style.display = 'flex'; // 显示数字角标 (flex for centering text)
        } else {
            badge.style.display = 'none'; // 没通知就隐藏
        }
    }
    
    // 4. 动态在下拉列表中插入新的通知 (Live 实时更新)
    const popupBody = document.querySelector('#notification-popup .popup-body');
    if (popupBody && data.message) {
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
    }
    
    // 触发你原本的提示框 (保持一致性)
    launchToastAlert('New system notification!');
});