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
sendBtn.onclick = () => {
    const msg = messageInput.value;
    if (msg.trim() !== "") {
        // 发送消息给后端
        socket.emit('send_message', {
            room: ROOM_ID,
            username: USERNAME,
            message: msg
        });
        messageInput.value = ""; // 清空输入框
    }
};

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