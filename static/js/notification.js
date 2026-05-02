socket.on('clear_unread', function(data) {
    // 1. 清除任务按钮上的数字红点[cite: 1]
    const badge = document.getElementById('badge-' + data.task_id);
    if (badge) badge.style.display = 'none';

    // 2. 实时尝试隐藏 Tab 和侧边栏的小红点
    // 注意：因为逻辑较复杂（一个 Tab 下可能有多个任务），
    // 最稳妥的 Live 做法是直接隐藏它们，或者等下次刷新页面重新计算精准数值。
    const createdDot = document.getElementById('created-unread-dot');
    const appliedDot = document.getElementById('applied-unread-dot');
    const globalDot = document.getElementById('global-unread-dot');

    // 如果你进入的是 Created 视图的任务，尝试隐藏 Created Tab 的红点
    // 这里简单处理：只要有清除动作，我们就让这些全局小红点先消失，
    // 这样用户感官上会觉得系统非常灵敏
    if (createdDot) createdDot.style.display = 'none';
    if (appliedDot) appliedDot.style.display = 'none';
    if (globalDot) globalDot.style.display = 'none';
});