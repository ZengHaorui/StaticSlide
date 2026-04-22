import json
import os
import subprocess
import shutil

# --- 配置区 ---
FFMPEG_CMD = "ffmpeg"  # 确保 ffmpeg 在环境变量中
# 编码预设：ultrafast 最快，但在网页上可能体积稍大；veryfast 是很好的平衡
ENCODING_PRESET = "ultrafast" 

BASE_DIR = "static/videos"
LOOP_DIR = os.path.join(BASE_DIR, "loops")
TRANS_DIR = os.path.join(BASE_DIR, "transitions")
THUMB_DIR = os.path.join(BASE_DIR, "thumbnails")

# 清理并重建目录
for d in [LOOP_DIR, TRANS_DIR, THUMB_DIR]:
    os.makedirs(d, exist_ok=True)

def run_ffmpeg_cut(input_file, start, end, output_file):
    """精确剪切视频"""
    duration = end - start
    cmd = [
        FFMPEG_CMD, "-y",
        "-ss", str(start),
        "-i", input_file,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", ENCODING_PRESET,
        "-c:a", "aac",  # 如果不需要音频可以改为 "-an"
        "-strict", "experimental",
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_ffmpeg_reverse(input_file, output_file):
    """生成倒放视频"""
    cmd = [
        FFMPEG_CMD, "-y",
        "-i", input_file,
        "-vf", "reverse", "-af", "areverse",
        "-c:v", "libx264", "-preset", ENCODING_PRESET,
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_thumb(input_file, time, output_file):
    """生成缩略图"""
    cmd = [
        FFMPEG_CMD, "-y",
        "-ss", str(time),
        "-i", input_file,
        "-vframes", "1",
        "-q:v", "2",
        "-vf", "scale=-1:150", # 高度固定150，宽度自适应
        output_file
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def process_video(source_path, config_path, status_callback=None):
    def log(msg):
        print(msg)
        if status_callback: status_callback(msg)

    if not os.path.exists(source_path):
        log("错误：找不到源视频文件")
        return

    log(f"🚀 开始极速处理: {source_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
    
    processed_nodes = []

    for i, node in enumerate(nodes):
        node_id = node['id']
        log(f"--- 处理节点 {node_id} ---")

        # 1. 循环段 (Loop)
        loop_fn = f"loop_{node_id}.mp4"
        loop_rev_fn = f"loop_{node_id}_rev.mp4"
        loop_path = os.path.join(LOOP_DIR, loop_fn)
        loop_rev_path = os.path.join(LOOP_DIR, loop_rev_fn)
        
        loop_start = node['loop_start']
        loop_end = node['loop_end']
        loop_duration = loop_end - loop_start
        
        # 剪切正向 Loop
        run_ffmpeg_cut(source_path, loop_start, loop_end, loop_path)
        # 生成反向 Loop (新增需求：为了倒序快速播放当前段)
        run_ffmpeg_reverse(loop_path, loop_rev_path)
        
        node['loop_src'] = f"loops/{loop_fn}"
        node['loop_rev_src'] = f"loops/{loop_rev_fn}"
        node['loop_duration'] = loop_duration

        # 生成缩略图
        thumb_fn = f"thumb_{node_id}.jpg"
        mid_time = loop_start + loop_duration / 2
        generate_thumb(source_path, mid_time, os.path.join(THUMB_DIR, thumb_fn))
        node['thumb_src'] = f"thumbnails/{thumb_fn}"

        # 2. 过渡段 (Transition)
        if 'next_id' in node:
            next_id = node['next_id']
            next_node = next((n for n in nodes if n['id'] == next_id), None)
            
            if next_node:
                trans_start = node['loop_end']
                trans_end = next_node['loop_start']
                duration = trans_end - trans_start
                
                if duration > 0.1:
                    trans_fn = f"trans_{node_id}_to_{next_id}.mp4"
                    trans_rev_fn = f"trans_{node_id}_to_{next_id}_rev.mp4"
                    trans_path = os.path.join(TRANS_DIR, trans_fn)
                    trans_rev_path = os.path.join(TRANS_DIR, trans_rev_fn)
                    
                    # 剪切 & 倒放
                    run_ffmpeg_cut(source_path, trans_start, trans_end, trans_path)
                    run_ffmpeg_reverse(trans_path, trans_rev_path)
                    
                    node['trans_src'] = f"transitions/{trans_fn}"
                    node['trans_rev_src'] = f"transitions/{trans_rev_fn}"
                    node['trans_duration'] = float(duration)
                else:
                    node['trans_src'] = None
                    node['trans_duration'] = 0

        processed_nodes.append(node)

    # 导出配置
    with open(os.path.join(BASE_DIR, "playlist.json"), 'w', encoding='utf-8') as f:
        json.dump(processed_nodes, f, indent=2)
    
    log("🎉 处理完成！速度起飞！")

if __name__ == "__main__":
    if os.path.exists("source.mp4") and os.path.exists("config.json"):
        process_video("source.mp4", "config.json")