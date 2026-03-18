
// 页面导航函数
function navigateTo(pageId) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    // 显示目标页面
    document.getElementById(pageId).classList.add('active');
}

// 显示弹窗
function showModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

// 隐藏弹窗
function hideModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// 点击弹窗背景关闭
document.querySelectorAll('.modal-overlay').forEach(modal => {
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.remove('active');
        }
    });
});

// 切换选项状态
document.querySelectorAll('.modal-option').forEach(option => {
    option.addEventListener('click', function() {
        this.classList.toggle('selected');
    });
});

// 切换开关状态
document.querySelectorAll('.toggle-switch').forEach(toggle => {
    toggle.addEventListener('click', function() {
        this.classList.toggle('off');
    });
});
