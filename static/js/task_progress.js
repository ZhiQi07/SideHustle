// 监听来自后端的进度条实时更新
window.addEventListener('load', function() {
    if (typeof globalSocket !== 'undefined') {
        globalSocket.on('progress_updated', function(data) {
            const taskId = data.task_id;
            const progress = parseInt(data.progress || 0);

            // 1. 更新 Created Tasks 里面的项目总进度
            const createdText = document.getElementById('created-progress-text-' + taskId);
            const createdFill = document.getElementById('created-progress-fill-' + taskId);
            if (createdText) createdText.innerText = progress + '%';
            if (createdFill) createdFill.style.width = progress + '%';

            // 2. 更新 Applied Tasks 里面的项目总进度
            const appliedText = document.getElementById('applied-progress-text-' + taskId);
            const appliedFill = document.getElementById('applied-progress-fill-' + taskId);
            if (appliedText) appliedText.innerText = progress + '%';
            if (appliedFill) appliedFill.style.width = progress + '%';

            // 3. 更新 Range Slider 进度条组件的限制边界和当前值，防止 Tasker 冲突覆盖
            const slider = document.getElementById('slider-' + taskId);
            const valDisplay = document.getElementById('val-' + taskId);
            if (slider) {
                slider.value = progress;
                slider.dataset.currentProgress = progress;
            }
            if (valDisplay) {
                valDisplay.innerText = progress + '%';
            }
        });
    }
});
