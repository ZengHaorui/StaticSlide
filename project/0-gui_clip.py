import sys
import json
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QMessageBox, QFrame)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QAction

import processor  # 引用你的 processor.py

# --- 自定义可视化时间轴控件 ---
class TimelineWidget(QWidget):
    seek_request = pyqtSignal(int) # 毫秒

    def __init__(self):
        super().__init__()
        self.setFixedHeight(60)
        self.duration = 1  # 避免除以0
        self.position = 0
        self.segments = [] # List of (start_ms, end_ms)
        self.setMouseTracking(True)
        self.is_dragging = False

    def set_duration(self, duration):
        self.duration = duration if duration > 0 else 1
        self.update()

    def set_position(self, position):
        self.position = position
        self.update()

    def set_segments(self, segments):
        """ segments: [(start_sec, end_sec), ...] """
        self.segments = [(s * 1000, e * 1000) for s, e in segments]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # 1. 绘制轨道背景 (深灰)
        painter.fillRect(0, 20, w, h-40, QColor("#333"))
        
        # 2. 绘制循环片段 (绿色)
        painter.setBrush(QBrush(QColor("#4CAF50")))
        painter.setPen(Qt.PenStyle.NoPen)
        
        for start_ms, end_ms in self.segments:
            x = int((start_ms / self.duration) * w)
            seg_w = int(((end_ms - start_ms) / self.duration) * w)
            if seg_w < 2: seg_w = 2 # 最小显示宽度
            painter.drawRect(x, 20, seg_w, h-40)

        # 3. 绘制游标 (红色)
        cursor_x = int((self.position / self.duration) * w)
        painter.setPen(QPen(QColor("#FF5252"), 2))
        painter.drawLine(cursor_x, 5, cursor_x, h-5)
        
        # 游标头
        painter.setBrush(QBrush(QColor("#FF5252")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cursor_x, 15), 6, 6)

        # 4. 显示时间文字
        curr_sec = self.position / 1000
        total_sec = self.duration / 1000
        time_str = f"{curr_sec:.2f} / {total_sec:.2f}s"
        painter.setPen(QColor("#FFF"))
        painter.drawText(w - 100, h - 5, time_str)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self._update_seek(event.pos().x())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self._update_seek(event.pos().x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
            self._update_seek(event.pos().x())

    def _update_seek(self, mouse_x):
        ratio = mouse_x / self.width()
        ratio = max(0, min(1, ratio))
        target_ms = int(ratio * self.duration)
        self.seek_request.emit(target_ms)

# --- 主编辑器 ---
class VideoSlicerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PPT 视频极速切片器 Pro")
        self.resize(1100, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #222; color: #FFF; }
            QWidget { color: #FFF; font-family: 'Segoe UI'; }
            QTableWidget { background-color: #333; gridline-color: #555; alternate-background-color: #3d3d3d; }
            QHeaderView::section { background-color: #444; padding: 4px; border: 1px solid #555; }
            QPushButton { background-color: #444; border: 1px solid #555; padding: 6px; border-radius: 4px; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #222; }
            QPushButton#ActionBtn { background-color: #2196F3; font-weight: bold; border: none; }
            QPushButton#ExportBtn { background-color: #4CAF50; font-weight: bold; font-size: 14px; padding: 10px; }
            QLabel { color: #AAA; }
        """)

        self.video_path = ""
        self.init_ui()

        # 加载默认
        if os.path.exists("source.mp4"):
            self.load_video_file(os.path.abspath("source.mp4"))
            if os.path.exists("config.json"):
                self.load_config("config.json")

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. 视频区域
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black; border: 1px solid #444;")
        layout.addWidget(self.video_widget, stretch=4)

        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_widget)
        
        # 2. 可视化时间轴
        self.timeline = TimelineWidget()
        self.timeline.seek_request.connect(self.player.setPosition)
        layout.addWidget(self.timeline)

        # 3. 控制区
        ctrl_layout = QHBoxLayout()
        
        # 播放控制
        self.btn_play = QPushButton("⏯ 播放/暂停")
        self.btn_play.setFixedWidth(100)
        self.btn_play.clicked.connect(self.toggle_play)
        
        # 定位微调
        self.btn_jump_start = QPushButton("⏮ 跳转到当前段开头")
        self.btn_jump_start.clicked.connect(lambda: self.jump_to_segment('start'))
        
        self.btn_jump_end = QPushButton("⏭ 跳转到当前段结尾")
        self.btn_jump_end.clicked.connect(lambda: self.jump_to_segment('end'))

        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_jump_start)
        ctrl_layout.addWidget(self.btn_jump_end)
        ctrl_layout.addStretch()
        
        # 编辑操作
        self.btn_set_start = QPushButton("🚩 设为起点 (Start)")
        self.btn_set_start.setObjectName("ActionBtn")
        self.btn_set_start.clicked.connect(lambda: self.set_time_val(1))
        
        self.btn_set_end = QPushButton("🏁 设为终点 (End)")
        self.btn_set_end.setObjectName("ActionBtn")
        self.btn_set_end.clicked.connect(lambda: self.set_time_val(2))

        ctrl_layout.addWidget(self.btn_set_start)
        ctrl_layout.addWidget(self.btn_set_end)
        
        layout.addLayout(ctrl_layout)

        # 4. 表格区
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "开始时间 (s)", "结束时间 (s)", "跳转到 ID"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        
        # 表格变动时更新时间轴显示
        self.table.itemChanged.connect(self.sync_timeline_data)
        self.table.itemSelectionChanged.connect(self.on_row_select)
        
        # 表格按钮
        tbl_btn_layout = QHBoxLayout()
        btn_add = QPushButton("➕ 新增")
        btn_add.clicked.connect(self.add_row)
        btn_del = QPushButton("➖ 删除")
        btn_del.clicked.connect(self.del_row)
        
        tbl_btn_layout.addWidget(btn_add)
        tbl_btn_layout.addWidget(btn_del)
        tbl_btn_layout.addStretch()

        layout.addLayout(tbl_btn_layout)
        layout.addWidget(self.table, stretch=2)

        # 5. 底部导出
        self.btn_export = QPushButton("🚀 保存配置并生成极速切片")
        self.btn_export.setObjectName("ExportBtn")
        self.btn_export.clicked.connect(self.export_data)
        layout.addWidget(self.btn_export)

        # 信号绑定
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)

    # --- 逻辑处理 ---

    def load_video_file(self, path):
        self.video_path = path
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        # 自动暂停以显示第一帧
        QTimer.singleShot(500, self.player.pause)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_position_changed(self, pos):
        self.timeline.set_position(pos)

    def on_duration_changed(self, dur):
        self.timeline.set_duration(dur)

    def add_row(self, data=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 默认值
        s, e, nid = "0.00", "0.00", str(row + 1)
        if data:
            s = f"{data.get('loop_start', 0):.2f}"
            e = f"{data.get('loop_end', 0):.2f}"
            nid = str(data.get('next_id', row + 1))

        self.table.setItem(row, 0, QTableWidgetItem(str(row))) # ID (Auto)
        self.table.setItem(row, 1, QTableWidgetItem(s))
        self.table.setItem(row, 2, QTableWidgetItem(e))
        self.table.setItem(row, 3, QTableWidgetItem(nid))
        
        self.sync_timeline_data()

    def del_row(self):
        if self.table.currentRow() >= 0:
            self.table.removeRow(self.table.currentRow())
            self.sync_timeline_data()

    def set_time_val(self, col):
        """将当前播放时间填入表格"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先在表格中点击选中一行")
            return
        
        sec = self.player.position() / 1000.0
        self.table.setItem(row, col, QTableWidgetItem(f"{sec:.2f}"))
        self.sync_timeline_data() # 立即刷新下方绿条

    def jump_to_segment(self, type_):
        """一键定位到当前选中行的开头或结尾"""
        row = self.table.currentRow()
        if row < 0: return
        
        col = 1 if type_ == 'start' else 2
        item = self.table.item(row, col)
        if item:
            try:
                sec = float(item.text())
                self.player.setPosition(int(sec * 1000))
                # 如果是跳转，通常希望暂停看清楚这帧
                self.player.pause() 
            except: pass

    def on_row_select(self):
        """选中行时，不高亮时间轴，单纯为了定位做准备"""
        pass

    def sync_timeline_data(self):
        """从表格读取数据，更新下方时间轴的绿色片段"""
        segs = []
        try:
            for r in range(self.table.rowCount()):
                s_item = self.table.item(r, 1)
                e_item = self.table.item(r, 2)
                if s_item and e_item:
                    s = float(s_item.text())
                    e = float(e_item.text())
                    if e > s:
                        segs.append((s, e))
        except: pass
        self.timeline.set_segments(segs)

    def load_config(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                nodes = json.load(f)
            self.table.setRowCount(0)
            for n in nodes:
                self.add_row(n)
        except Exception as e:
            print(e)

    def export_data(self):
        # 1. 收集数据
        nodes = []
        try:
            for r in range(self.table.rowCount()):
                node = {
                    "id": int(self.table.item(r, 0).text()),
                    "loop_start": float(self.table.item(r, 1).text()),
                    "loop_end": float(self.table.item(r, 2).text()),
                    "next_id": int(self.table.item(r, 3).text())
                }
                if node["loop_start"] >= node["loop_end"]:
                    raise ValueError(f"第 {r+1} 行时间设置错误：开始时间必须小于结束时间")
                nodes.append(node)
        except Exception as e:
            QMessageBox.warning(self, "数据错误", str(e))
            return

        # 2. 保存 JSON
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(nodes, f, indent=2)

        # 3. 调用 Processor
        self.btn_export.setEnabled(False)
        self.btn_export.setText("处理中 (FFmpeg)...")
        QApplication.processEvents() # 刷新UI

        try:
            processor.process_video(self.video_path or "source.mp4", "config.json", print)
            QMessageBox.information(self, "成功", "切片完成！\n请运行 main.py 查看效果。")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))
        finally:
            self.btn_export.setEnabled(True)
            self.btn_export.setText("🚀 保存配置并生成极速切片")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = VideoSlicerApp()
    win.show()
    sys.exit(app.exec())