// notification.js - 负责全站红点逻辑

// 1. 初始化 Socket 连接
// 注意：如果其他 JS 文件（如 server.js）已经定义了 socket，请确保页面只引入一个 socket 初始化
if (typeof socket === 'undefined') {
    var socket = io();
}

// 2. 【核心】监听：新消息到达信号 (让红点亮起来)
socket.on('new_unread', function(data) {
    console.log("🔔 收到红点信号通知:", data);

    // A. 让侧边栏的 "My Task" 出现红点
    const globalDot = document.getElementById('global-unread-dot');
    if (globalDot) {
        globalDot.style.display = 'inline-block';
        console.log("-> 已点亮侧边栏红点");
    }

    // B. 根据角色 (data.role) 精准点亮选项卡 (Created 或 Applied)
    if (data.role === 'created') {
        const createdDot = document.getElementById('created-unread-dot');
        if (createdDot) createdDot.style.display = 'inline-block';
        console.log("-> 已点亮 Created Tasks 选项卡红点");
    } else if (data.role === 'applied') {
        const appliedDot = document.getElementById('applied-unread-dot');
        if (appliedDot) appliedDot.style.display = 'inline-block';
        console.log("-> 已点亮 Applied Tasks 选项卡红点");
    }

    // C. 更新具体任务卡片上的消息数字气泡 (Badge)
    // 自动寻找包含该任务聊天链接的按钮
    const msgBtn = document.querySelector(`a[href*="chat/${data.task_id}"], a[href*="group_chat/${data.task_id}"]`);
    if (msgBtn) {
        let badge = msgBtn.querySelector('.unread-badge');
        if (!badge) {
            badge = document.createElement('span');
            badge.className = 'unread-badge';
            badge.innerText = '1';
            msgBtn.appendChild(badge);
        } else {
            badge.innerText = parseInt(badge.innerText) + 1;
        }
        console.log(`-> 已更新任务 ${data.task_id} 的气泡数字`);
    }
});

// 3. 监听：清除信号 (当你进入聊天室后，让红点消失)
socket.on('clear_unread', function(data) {
    console.log("仅当前用户清除红点:", data.task_id);
    
    // 1. 隐藏具体任务的数字
    const badge = document.querySelector(`a[href*="${data.task_id}"] .unread-badge`);
    if (badge) badge.remove(); // 直接移除，更干净

    // 2. 检查是否还有其他任务有红点，如果没有了，才隐藏侧边栏大红点
    const remainingBadges = document.querySelectorAll('.unread-badge');
    if (remainingBadges.length === 0) {
        const globalDot = document.getElementById('global-unread-dot');
        const appliedDot = document.getElementById('applied-unread-dot');
        const createdDot = document.getElementById('created-unread-dot');
        if (globalDot) globalDot.style.display = 'none';
        if (appliedDot) appliedDot.style.display = 'none';
        if (createdDot) createdDot.style.display = 'none';
    }
});