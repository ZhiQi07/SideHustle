// ==========================================
// 💡 保持原汁原味：你原本的群聊 (chat.html) 核心逻辑
// ==========================================

// 建立连接
const socket = io();

const chatBox = document.getElementById('chat-box');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');

// 一进页面就告诉后端：我要加入这个 Task 的房间
socket.emit('join', {
    room: ROOM_ID,
    username: USERNAME
});

// 点击发送按钮
// --- 原有的逻辑 ---
sendBtn.onclick = () => {
    const msg = messageInput.value;
    if (msg.trim() !== "") {
        socket.emit('send_message', {
            room: ROOM_ID,
            username: USERNAME,
            message: msg
        });
        messageInput.value = ""; 
    }
};

// --- 把这段移到外面 (就在 onclick 下面就行) ---
messageInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault(); 
        sendBtn.click(); // 触发上面的 onclick 逻辑
    }
});

// 监听后端传回来的消息
socket.on('receive_message', (data) => {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    
    // 判断是不是自己发的，应用不同颜色
    if (data.username === USERNAME) {
        msgDiv.classList.add('my-msg');
        msgDiv.innerHTML = `<strong>Me:</strong> ${data.message}`;
    } else {
        msgDiv.classList.add('others-msg');
        msgDiv.innerHTML = `<strong>${data.username}:</strong> ${data.message}`;
    }
    
    chatBox.appendChild(msgDiv);
    // 自动滚动到底部
    chatBox.scrollTop = chatBox.scrollHeight;
});


// ==========================================
// 💡 全站免刷新黑科技：通知状态实时接收管道
// ==========================================

// 监听来自全局后端的实时未读通知（配合你的 notification.js 全站红点功能）
// 这样当你在聊天时，如果别人在私聊里戳你，你在这个群聊页面也能瞬间看到顶部的红点闪烁！
socket.on('new_private_notification', function(data) {
    // 只有当这条私聊的接收者是我自己时，才在全站顶栏点亮红点
    if (data.receiver === USERNAME) {
        const globalDot = document.getElementById('global-nav-red-dot');
        if (globalDot) {
            globalDot.style.setProperty('display', 'block', 'important');
        }
    }
});