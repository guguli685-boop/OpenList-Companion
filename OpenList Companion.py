import sys
import os
import subprocess
import socket
import psutil
import ctypes
import time
import requests
import shutil
import zipfile
import webbrowser
import re
import json
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QTextEdit, QFrame, QFileDialog, 
                             QLineEdit, QMessageBox, QSizePolicy, QSystemTrayIcon, QMenu, QAction, QInputDialog)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal, QRect, QPoint, QSize
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage, QPainter, QPainterPath, QIcon, QPen, QCursor

# --- 核心配置 ---
CONFIG_FILE = ".openlist_path"
GEOMETRY_FILE = ".openlist_geo"
DEFAULT_PORT = 5244
BILIBILI_UID = "3493268808620216"
GITHUB_URL = "https://github.com/guguli685-boop/OpenList-Companion/tree/main"
HELP_DOC_URL = "https://gemini.google.com/app/6a8d06b29e498881"
AUTHOR_DISPLAY_NAME = "余宣灵."

# --- 路径感应 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_APP = os.path.join(BASE_DIR, "openlist.png")
ICON_RUNNING = os.path.join(BASE_DIR, "正在运行图标-01.png")
ICON_STOPPED = os.path.join(BASE_DIR, "停止运行图标-01.png")

def hide_file(path):
    try:
        if os.path.exists(path):
            ctypes.windll.kernel32.SetFileAttributesW(path, 2)
    except: pass

class AvatarDownloader(QThread):
    finished = pyqtSignal(QPixmap)
    def run(self):
        try:
            api_url = f"https://api.bilibili.com/x/space/wbi/acc/info?mid={BILIBILI_UID}"
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com/'}
            resp = requests.get(api_url, headers=headers, timeout=5).json()
            face_url = resp.get("data", {}).get("face", "https://i0.hdslb.com/bfs/face/e4eed8017871c0117b725ace44529f184fbb641f.webp")
            img_data = requests.get(face_url, headers=headers, timeout=5).content
            image = QImage.fromData(img_data)
            if not image.isNull(): self.finished.emit(QPixmap.fromImage(image))
        except: pass

class OpenListManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StaticContents) 
        self.app_path = self.auto_find_path() 
        self.raw_username = "admin"
        self.raw_password = ""
        self.initUI()
        self.load_geometry()
        self.initTray() 
        self.load_author_info()
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(1000)

    def auto_find_path(self):
        local_alist = os.path.join(BASE_DIR, "alist.exe")
        if os.path.exists(local_alist): return os.path.normpath(local_alist)
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    p = f.read().strip().replace('"', '')
                    if os.path.isfile(p): return os.path.normpath(p)
            except: pass
        return ""

    def load_geometry(self):
        if os.path.exists(GEOMETRY_FILE):
            try:
                with open(GEOMETRY_FILE, "r") as f:
                    geo = json.load(f)
                    self.move(geo.get("x", 100), geo.get("y", 100))
                    if "w" in geo and "h" in geo: self.resize(geo["w"], geo["h"])
            except: pass

    def save_geometry(self):
        try:
            with open(GEOMETRY_FILE, "w") as f:
                json.dump({"x": self.pos().x(), "y": self.pos().y(), "w": self.width(), "h": self.height()}, f)
            hide_file(GEOMETRY_FILE)
        except: pass

    def load_author_info(self):
        self.downloader = AvatarDownloader()
        self.downloader.finished.connect(self.update_avatar_with_mask)
        self.downloader.start()

    def update_avatar_with_mask(self, pixmap):
        size = 64
        target = QPixmap(size, size); target.fill(Qt.transparent)
        painter = QPainter(target); painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath(); path.addEllipse(0, 0, size, size)
        painter.setClipPath(path); painter.drawPixmap(0, 0, pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        painter.end(); self.lbl_avatar.setPixmap(target)

    def initUI(self):
        self.setWindowTitle('OpenList Companion v2.6')
        if os.path.exists(ICON_APP): self.setWindowIcon(QIcon(ICON_APP))
        self.setMinimumSize(1000, 800) 
        self.setStyleSheet("background-color: #F7F8FA; font-family: 'Microsoft YaHei UI';")
        
        main_v_layout = QVBoxLayout(self); main_v_layout.setContentsMargins(0, 0, 0, 0); main_v_layout.setSpacing(0)

        self.tips_bar = QFrame(); self.tips_bar.setFixedHeight(65); self.tips_bar.setStyleSheet("background-color: #FFF9DB; border: none;")
        tips_layout = QHBoxLayout(self.tips_bar)
        self.lbl_tips_msg = QLabel("✨ 凭证已捕捉，密码已自动复制！")
        self.lbl_tips_msg.setStyleSheet("color: #E67E22; font-weight: bold;")
        self.btn_copy_u = self.create_btn("👤 复制账号", "#FAB005", "white", height=34, width=120)
        self.btn_copy_u.clicked.connect(lambda: self.quick_copy("user"))
        self.btn_copy_p = self.create_btn("🔑 复制密码", "#FD7E14", "white", height=34, width=120)
        self.btn_copy_p.clicked.connect(lambda: self.quick_copy("pwd"))
        self.btn_close_tips = QPushButton("✕")
        self.btn_close_tips.setFixedSize(30, 30); self.btn_close_tips.setCursor(Qt.PointingHandCursor)
        self.btn_close_tips.setStyleSheet("QPushButton { border:none; color: #ADB5BD; font-weight:bold; } QPushButton:hover { color: #FA5252; }")
        self.btn_close_tips.clicked.connect(lambda: self.tips_bar.hide())
        tips_layout.addWidget(self.lbl_tips_msg); tips_layout.addWidget(self.btn_copy_u); tips_layout.addWidget(self.btn_copy_p); tips_layout.addStretch(); tips_layout.addWidget(self.btn_close_tips)
        self.tips_bar.hide(); main_v_layout.addWidget(self.tips_bar)

        content_hbox = QHBoxLayout(); content_hbox.setSpacing(0); main_v_layout.addLayout(content_hbox)

        sidebar = QFrame(); sidebar.setFixedWidth(320); sidebar.setStyleSheet("background-color: #FFFFFF; border: none;")
        side_layout = QVBoxLayout(sidebar); side_layout.setContentsMargins(25, 40, 25, 40); side_layout.setSpacing(18)
        
        profile_hbox = QHBoxLayout()
        self.lbl_avatar = QLabel(); self.lbl_avatar.setFixedSize(64, 64); self.lbl_avatar.setStyleSheet("background-color: #F1F3F5; border-radius: 32px;")
        self.lbl_title = QLabel(AUTHOR_DISPLAY_NAME); self.lbl_title.setFont(QFont("Microsoft YaHei UI", 18, QFont.Bold))
        profile_hbox.addWidget(self.lbl_avatar); profile_hbox.addSpacing(15); profile_hbox.addWidget(self.lbl_title); side_layout.addLayout(profile_hbox)
        
        self.status_box = QFrame(); self.status_box.setFixedHeight(100); self.status_box.setStyleSheet("background-color: #F8F9FA; border-radius: 15px; border: none;")
        status_layout = QVBoxLayout(self.status_box); status_layout.setSpacing(5)
        self.lbl_status = QLabel("🔴 未运行"); self.lbl_status.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        self.lbl_address = QLabel(f"💻 http://127.0.0.1:{DEFAULT_PORT}"); self.lbl_address.setStyleSheet("border: none;")
        status_layout.addWidget(self.lbl_status); status_layout.addWidget(self.lbl_address); side_layout.addWidget(self.status_box)

        self.cred_box = QFrame(); self.cred_box.setStyleSheet("background-color: #FFF4E6; border-radius: 15px; border: none;")
        cred_layout = QVBoxLayout(self.cred_box); cred_header = QHBoxLayout(); cred_header.addWidget(QLabel("🔑 管理凭证", font=QFont("Microsoft YaHei UI", 10, QFont.Bold)))
        self.btn_get_admin = self.create_mini_btn("🔍 获取", "#FD7E14"); self.btn_get_admin.clicked.connect(self.get_admin_info)
        self.btn_set_admin = self.create_mini_btn("✍️ 修改", "#E67E22"); self.btn_set_admin.clicked.connect(self.set_admin_password)
        cred_header.addStretch(); cred_header.addWidget(self.btn_get_admin); cred_header.addWidget(self.btn_set_admin); cred_layout.addLayout(cred_header)
        self.lbl_admin_user = QLabel("用户: admin"); self.lbl_admin_pwd = QLabel("密码: ********"); cred_layout.addWidget(self.lbl_admin_user); cred_layout.addWidget(self.lbl_admin_pwd); side_layout.addWidget(self.cred_box)

        self.github_box = QFrame(); self.github_box.setStyleSheet("background-color: #E7F5FF; border-radius: 15px; border: none;")
        github_layout = QVBoxLayout(self.github_box); github_header = QHBoxLayout(); github_header.addWidget(QLabel("🐙 开源主页", font=QFont("Microsoft YaHei UI", 9, QFont.Bold)))
        self.btn_view_github = self.create_mini_btn("🌐 访问", "#228BE6"); self.btn_view_github.clicked.connect(lambda: webbrowser.open(GITHUB_URL))
        github_header.addStretch(); github_header.addWidget(self.btn_view_github); github_layout.addLayout(github_header); side_layout.addWidget(self.github_box)

        self.help_box = QFrame(); self.help_box.setStyleSheet("background-color: #F3F0FF; border-radius: 15px; border: none;")
        help_layout = QVBoxLayout(self.help_box); help_header = QHBoxLayout(); help_header.addWidget(QLabel("📚 使用帮助", font=QFont("Microsoft YaHei UI", 9, QFont.Bold)))
        self.btn_view_help = self.create_mini_btn("🔗 查看", "#7950F2"); self.btn_view_help.clicked.connect(lambda: webbrowser.open(HELP_DOC_URL))
        help_header.addStretch(); help_header.addWidget(self.btn_view_help); help_layout.addLayout(help_header); side_layout.addWidget(self.help_box)

        side_layout.addStretch(); self.btn_reset_path = self.create_btn("⚙️ 重新设置路径", "#F1F3F5", "#495057", height=45); self.btn_reset_path.clicked.connect(self.change_path); side_layout.addWidget(self.btn_reset_path)
        content_hbox.addWidget(sidebar)

        right_area = QVBoxLayout(); right_area.setContentsMargins(40, 40, 40, 40); right_area.setSpacing(25)
        ctrl_label = QLabel("服务控制中心"); ctrl_label.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold)); right_area.addWidget(ctrl_label)
        
        btn_grid_container = QHBoxLayout(); btn_grid_container.setSpacing(15)
        self.btn_start = self.create_btn("🚀 开启服务", "#4C6EF5", "#FFFFFF", width=150)
        self.btn_start.clicked.connect(lambda: self.run_command("start"))
        self.btn_restart = self.create_btn("🔄 一键重启", "#748FC3", "#FFFFFF", width=150)
        self.btn_restart.clicked.connect(lambda: self.run_command("restart"))
        self.btn_stop = self.create_btn("🛑 停止服务", "#FA5252", "#FFFFFF", width=150)
        self.btn_stop.clicked.connect(lambda: self.run_command("stop"))
        self.btn_open_web = self.create_btn("🌐 管理后台", "#1098AD", "#FFFFFF", width=150)
        self.btn_open_web.clicked.connect(lambda: webbrowser.open(f"http://127.0.0.1:{DEFAULT_PORT}"))
        btn_grid_container.addWidget(self.btn_start); btn_grid_container.addWidget(self.btn_restart); btn_grid_container.addWidget(self.btn_stop); btn_grid_container.addWidget(self.btn_open_web); btn_grid_container.addStretch()
        right_area.addLayout(btn_grid_container)

        right_area.addWidget(QLabel("数据维护", font=QFont("Microsoft YaHei UI", 12, QFont.Bold)))
        backup_hbox = QHBoxLayout(); backup_hbox.setSpacing(15)
        self.btn_export = self.create_btn("📦 导出全量备份", "#15AABF", "#FFFFFF", height=45, width=220)
        self.btn_export.clicked.connect(self.export_backup)
        self.btn_import = self.create_btn("📥 导入数据恢复", "#AE3EC9", "#FFFFFF", height=45, width=220)
        self.btn_import.clicked.connect(self.import_backup)
        backup_hbox.addWidget(self.btn_export); backup_hbox.addWidget(self.btn_import); backup_hbox.addStretch()
        right_area.addLayout(backup_hbox)

        right_area.addWidget(QLabel("实时运行日志"))
        self.log_box = QTextEdit(readOnly=True); self.log_box.setStyleSheet("background-color: #212529; color: #F8F9FA; border-radius: 15px; padding: 20px; font-family: 'Consolas'; border:none;")
        right_area.addWidget(self.log_box); content_hbox.addLayout(right_area, stretch=1)

    def initTray(self):
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists(ICON_APP): self.tray_icon.setIcon(QIcon(ICON_APP))
        self.tray_menu = QMenu(); show_action = QAction("🏠 显示面板", self); show_action.triggered.connect(self.showNormal); quit_action = QAction("❌ 退出程序", self); quit_action.triggered.connect(self.force_quit)
        self.tray_menu.addAction(show_action); self.tray_menu.addSeparator(); self.tray_menu.addAction(quit_action); self.tray_icon.setContextMenu(self.tray_menu); self.tray_icon.show()

    def update_tray_icon(self, is_running):
        icon_path = ICON_RUNNING if is_running else ICON_STOPPED
        if os.path.exists(icon_path): self.tray_icon.setIcon(QIcon(icon_path))

    def create_btn(self, text, bg, fg, height=50, width=None):
        btn = QPushButton(text); btn.setMinimumHeight(height); btn.setCursor(Qt.PointingHandCursor)
        if width: btn.setFixedWidth(width)
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {bg}; color: {fg}; border-radius: 12px; font-weight: bold; border: none; }}
            QPushButton:hover {{ filter: brightness(1.1); }}
            QPushButton:pressed {{ filter: brightness(0.85); padding-top: 4px; padding-left: 4px; }}
        """)
        return btn

    def create_mini_btn(self, text, bg, width=60):
        btn = QPushButton(text); btn.setFixedSize(width, 24); btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"QPushButton {{ background: {bg}; color: white; border-radius: 8px; border:none; font-size: 10px; font-weight:bold; }} QPushButton:pressed {{ padding-top: 1px; padding-left: 1px; }}")
        return btn

    def refresh_status(self):
        is_running = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1); is_running = (s.connect_ex(('127.0.0.1', DEFAULT_PORT)) == 0)
        except: pass
        self.update_tray_icon(is_running)
        if is_running:
            self.lbl_status.setText("🟢 正在运行"); self.lbl_status.setStyleSheet("color: white; border: none;")
            self.status_box.setStyleSheet("background-color: #40C057; border-radius: 15px; border: none;")
            self.lbl_address.setStyleSheet("color: #EBFBEE; border: none;"); self.btn_start.setEnabled(False)
        else:
            self.lbl_status.setText("🔴 未在运行"); self.lbl_status.setStyleSheet("color: #FA5252; border: none;")
            self.status_box.setStyleSheet("background-color: #F8F9FA; border-radius: 15px; border: none;")
            self.lbl_address.setStyleSheet("color: #868E96; border: none;"); self.btn_start.setEnabled(True)

    def handle_incoming_log(self, msg):
        self.log(msg)
        p_match = re.search(r"initial password is:\s*(\S+)", msg)
        if p_match:
            self.raw_password = p_match.group(1); QApplication.clipboard().setText(self.raw_password)
            self.lbl_admin_pwd.setText(f"密码: {self.raw_password}"); self.tips_bar.show()

    def run_command(self, action):
        if not self.app_path: return
        if action == "stop": self.kill_all(); self.log("🛑 停止服务")
        elif action == "start":
            self.log("🚀 拉起服务..."); self.thread = LogThread([self.app_path, "server", "--force-bin-dir"], os.path.dirname(self.app_path))
            self.thread.new_log.connect(self.handle_incoming_log); self.thread.start()
        elif action == "restart":
            self.log("🔄 重启联动..."); self.kill_all(); QTimer.singleShot(1000, lambda: self.run_command("start"))

    def kill_all(self):
        if not self.app_path: return
        name = os.path.basename(self.app_path)
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'].lower() == name.lower(): proc.kill()
            except: pass

    def set_admin_password(self):
        if not self.app_path: return
        pwd, ok = QInputDialog.getText(self, "修改密码", "输入新管理密码 (确定后将自动重启):", QLineEdit.Password)
        if ok and pwd:
            subprocess.Popen([self.app_path, "admin", "set", pwd], cwd=os.path.dirname(self.app_path), creationflags=0x08000000).wait()
            self.raw_password = pwd; self.lbl_admin_pwd.setText(f"密码: {pwd}"); self.log("✅ 密码已修改"); self.run_command("restart")

    def get_admin_info(self):
        if not self.app_path: return
        self.log("🔍 正在提取凭证..."); self.kill_all(); time.sleep(1.5)
        try:
            cmd = [self.app_path, "admin", "show"]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=os.path.dirname(self.app_path), text=True, creationflags=0x08000000)
            output, _ = process.communicate(); clean_output = re.compile(r'\x1b\[[0-9;]*m').sub('', output)
            p_match = re.search(r"(?:password|password is):\s*(\S+)", clean_output, re.IGNORECASE)
            if p_match: 
                self.raw_password = p_match.group(1); QApplication.clipboard().setText(self.raw_password)
                self.lbl_admin_pwd.setText(f"密码: {self.raw_password}"); self.tips_bar.show()
            self.run_command("start")
        except: self.log("❌ 获取失败"); self.run_command("start")

    def export_backup(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "导出备份", "Alist_Backup.zip", "Zip (*.zip)")
        if save_path:
            shutil.make_archive(save_path.replace('.zip', ''), 'zip', os.path.join(os.path.dirname(self.app_path), "data"))
            self.log("✅ 备份已导出")

    # --- 【重点修复】导入数据恢复底层加固 ---
    def import_backup(self):
        if not self.app_path: return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择恢复文件", "", "Zip (*.zip)")
        if not file_path: return
        
        self.log("📦 准备数据恢复，正在彻底清理环境...")
        self.kill_all() # 1. 尝试停止服务
        time.sleep(2) # 2. 增加等待时间，确保操作系统完全释放文件句柄
        
        try:
            # 再次确认 alist 进程是否已彻底消失
            name = os.path.basename(self.app_path)
            for proc in psutil.process_iter(['name']):
                if proc.info['name'].lower() == name.lower():
                    proc.kill()
            
            with zipfile.ZipFile(file_path, 'r') as z:
                # 3. 执行解压覆盖
                z.extractall(os.path.dirname(self.app_path))
            
            self.log("✅ 恢复成功！系统将自动重启服务...")
            QTimer.singleShot(1000, lambda: self.run_command("start")) # 4. 自动重启
            
        except PermissionError:
            # 捕获权限占用错误，避免闪退
            self.log("❌ 崩溃预防：文件被占用，请右键管理员运行后再试")
            QMessageBox.critical(self, "恢复失败", "某些文件仍被系统占用，请尝试手动关闭所有 alist.exe 进程后再试。")
            self.run_command("start")
        except Exception as e:
            # 捕获通用错误
            self.log(f"❌ 恢复崩溃: {e}")
            QMessageBox.warning(self, "异常提醒", f"恢复过程遇到未知错误: {e}")
            self.run_command("start")

    def log(self, msg, color="#63E6BE"): self.log_box.append(f"<span style='color:{color};'>[{time.strftime('%H:%M:%S')}]</span> {msg}")
    
    def change_path(self):
        p, _ = QFileDialog.getOpenFileName(self, "定位 alist.exe", "", "EXE (*.exe)")
        if p: 
            self.app_path = os.path.normpath(p)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: f.write(p)
            hide_file(CONFIG_FILE)
            self.log("⚙️ 路径更新成功")

    def quick_copy(self, mode):
        content = self.raw_username if mode == "user" else self.raw_password
        QApplication.clipboard().setText(content); self.log(f"📋 已手动复制")
    def force_quit(self): self.save_geometry(); self.tray_icon.hide(); QApplication.quit()
    def closeEvent(self, event): self.save_geometry(); self.hide(); event.ignore()

class LogThread(QThread):
    new_log = pyqtSignal(str)
    def __init__(self, cmd, cwd): super().__init__(); self.cmd, self.cwd = cmd, cwd
    def run(self):
        process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=self.cwd, text=True, bufsize=1, creationflags=0x08000000)
        for line in iter(process.stdout.readline, ''):
            if line: self.new_log.emit(line.strip())
        process.stdout.close()

if __name__ == '__main__':
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    manager = OpenListManager(); manager.show(); sys.exit(app.exec_())
