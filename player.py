import os
import json
import subprocess
from tempfile import NamedTemporaryFile

def parse_time(tc):
    if isinstance(tc, (int, float)): return float(tc)
    s = str(tc).strip()
    if ':' in s:
        parts = s.split(':')
        try:
            if len(parts)==3:
                h,m,sec = parts
                return int(h)*3600 + int(m)*60 + float(sec)
            elif len(parts)==2:
                m,sec = parts
                return int(m)*60 + float(sec)
        except: return 0
    try: return float(s)
    except: return 0

class VideoPlayerController:
    def __init__(self):
        self.video_path = None
        self.clips = []
        self.clips_json = None
        self.current_index = 0
        self.duration = 0

    def load_video(self, path):
        self.video_path = path
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.duration = float(result.stdout)
        except:
            self.duration = 0
        self.current_index = 0

    def load_json(self, path):
        with open(path,'r',encoding='utf-8') as f:
            j = json.load(f)
        self.set_json(j)

    def set_json(self, j):
        arr = j.get('clips') if isinstance(j,dict) and 'clips' in j else j
        self.clips = []
        for idx,o in enumerate(arr):
            self.clips.append({
                'number': o.get('number', idx+1),
                'start': parse_time(o.get('start')),
                'end': parse_time(o.get('end')),
                'type': o.get('type','loop'),
                'description': o.get('description',''),
                'animate_curve': o.get('animate_curve','easeInOut'),
                'jump_speed': float(o.get('jump_speed', 6.0))
            })

    def control(self, cmd, param=None):
        if not self.video_path or not self.clips: return {'error':'No video or clips'}
        if cmd == 'next':
            self.current_index = self.find_next_loop(self.current_index)
        elif cmd == 'prev':
            self.current_index = self.find_prev_loop(self.current_index)
        elif cmd == 'loop':
            pass
        elif cmd == 'seek':
            for i,c in enumerate(self.clips):
                if c['start']<=param<c['end']:
                    self.current_index = i
                    break
        elif cmd == 'set_clip':
            self.current_index = int(param)
        return {
            'current_index': self.current_index,
            'clip': self.clips[self.current_index]
        }

    def find_next_loop(self, idx):
        n = len(self.clips)
        for i in range(idx+1, idx+n+1):
            if self.clips[i % n]['type'] == 'loop':
                return i % n
        return idx

    def find_prev_loop(self, idx):
        n = len(self.clips)
        for i in range(idx-1, idx-n-1, -1):
            if self.clips[i % n]['type'] == 'loop':
                return i % n
        return idx

    def render_current_clip(self):
        idx = self.current_index
        c = self.clips[idx]
        # 避免裁切黑帧，前后预留一点
        start = max(0, c['start']-0.04)
        end = c['end']
        temp_dir = 'temp'
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = NamedTemporaryFile(delete=False, suffix='.mp4', dir=temp_dir)
        temp_file.close()
        outpath = temp_file.name
        cmd = [
            'ffmpeg', '-y',
            '-ss', f'{start:.3f}',
            '-to', f'{end:.3f}',
            '-i', self.video_path,
            '-avoid_negative_ts', 'make_zero',
            '-fflags', '+genpts',
            '-c:v', 'libx264', '-c:a', 'aac',
            '-preset', 'ultrafast',
            outpath
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return outpath