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

// 在你的发送消息逻辑里，除了发给聊天室，追加一个全局未读通知广播
// 假设这是你的 Socket 发送逻辑：
socket.to(room_name).emit('receive_private_message', data);

// 💡 【新增】：广播一个全局未读通知事件，把接收者和发送者带上
// 这样全站任何页面都能通过接收者（receiver）判定自己需不需要亮红点
socket.broadcast.emit('new_private_notification', {
    sender: data.sender,
    receiver: target_username // 接收这条消息的人的用户名
});