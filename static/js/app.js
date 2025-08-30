const DEFAULT_JSON = {
};

function $(id){ return document.getElementById(id) }
const player = $('player');
let allClips = [];
let currentClipIndex = 0;
let currentClipType = 'loop';
let isLoopMode = true;
let playingFastChain = false;
let videoDuration = 0;
let timelineUpdating = false;

// --- 资源列表 ---
function loadResourceList() {
  fetch('/api/resource_list').then(r=>r.json()).then(list => {
    const resDiv = $('resource-list');
    resDiv.innerHTML = '';
    list.forEach(item => {
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.textContent = item.name;
      btn.onclick = () => {
        fetch('/api/load_resource', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({video: item.video, json: item.json})
        }).then(r=>r.json()).then(j=>{
          if(j.success){
            loadJsonAndClips();
            loadVideo();
          }
        });
      };
      resDiv.appendChild(btn);
    });
    if (list.length === 0) {
      resDiv.innerHTML = '<span style="color:var(--muted)">resource文件夹暂无可用资源</span>';
    }
  });
}

// --- 默认资源加载 ---
function loadVideo() {
  player.src = '/api/video?t=' + Date.now();
  player.load();
  player.onloadedmetadata = ()=>{
    videoDuration = player.duration;
    player.currentTime = 0;
    player.playbackRate = 1;
    player.play();
    isLoopMode = (currentClipType === 'loop');
    playingFastChain = false;
  };
}

function loadJsonAndClips() {
  fetch('/api/json').then(r=>r.json()).then(j=>{
    if (!j.clips) j = DEFAULT_JSON;
    $('json-editor').value = JSON.stringify(j, null, 2);
    allClips = j.clips.map((c, i) => ({
      ...c,
      startSec: timeStrToSec(c.start),
      endSec: timeStrToSec(c.end),
      index: i
    }));
    renderTimeline();
    currentClipIndex = 0;
    currentClipType = allClips[0]?.type || 'loop';
  });
}

// --- 时间轴渲染 ---
function renderTimeline() {
  timelineUpdating = true;
  const timeline = $('timeline-bar');
  timeline.innerHTML = '';
  let duration = allClips.length ? allClips[allClips.length - 1].endSec : 0;
  allClips.forEach((clip, i) => {
    let left = (clip.startSec / duration) * 100;
    let width = ((clip.endSec - clip.startSec) / duration) * 100;
    let color = clip.type === 'loop' ? 'var(--accent)' : 'var(--pink)';
    let block = document.createElement('div');
    block.className = 'timeline-block';
    block.style.left = `${left}%`;
    block.style.width = `${width}%`;
    block.style.background = color;
    block.title = `${clip.description || clip.type} (${secToTimeStr(clip.startSec)} ~ ${secToTimeStr(clip.endSec)})`;
    block.onclick = () => {
      jumpToClip(i);
    };
    timeline.appendChild(block);

    // 标记分割线
    let marker = document.createElement('div');
    marker.className = 'timeline-marker';
    marker.style.left = `${left}%`;
    marker.title = `#${clip.number} ${clip.type}`;
    timeline.appendChild(marker);
  });
  timelineUpdating = false;
}

// 跳转到某段
function jumpToClip(index) {
  currentClipIndex = index;
  currentClipType = allClips[index].type;
  seekTo(allClips[index].startSec);
}

// --- 时间工具 ---
function timeStrToSec(str) {
  if (typeof str === 'number') return str;
  let a = str.split(':');
  let s = 0;
  if (a.length === 3) {
    s += parseInt(a[0], 10) * 3600;
    s += parseInt(a[1], 10) * 60;
    s += parseFloat(a[2]);
  } else if (a.length === 2) {
    s += parseInt(a[0], 10) * 60;
    s += parseFloat(a[1]);
  } else if (a.length === 1) {
    s += parseFloat(a[0]);
  }
  return s;
}
function secToTimeStr(sec) {
  sec = Math.max(0, sec);
  let hh = Math.floor(sec / 3600);
  let mm = Math.floor((sec % 3600) / 60);
  let ss = (sec % 60).toFixed(3);
  if (hh > 0) return `${hh.toString().padStart(2,"0")}:${mm.toString().padStart(2,"0")}:${ss.padStart(6,"0")}`;
  return `${mm.toString().padStart(2,"0")}:${ss.padStart(6,"0")}`;
}

// --- 进度动画切换 ---
function seekTo(targetTime) {
  player.currentTime = targetTime;
  player.playbackRate = 1;
  player.play();
}

// 平滑快进到目标片段
function fastForwardToNextLoop() {
  if (playingFastChain) return;
  playingFastChain = true;
  isLoopMode = false;
  let idx = currentClipIndex;
  let chain = [];
  for (let i = idx+1; i < allClips.length; i++) {
    chain.push(i);
    if (allClips[i].type === 'loop') break;
  }
  if (chain.length === 0) return;
  playChainClips(chain, () => {
    currentClipIndex = chain[chain.length-1];
    currentClipType = allClips[currentClipIndex].type;
    isLoopMode = true;
    playingFastChain = false;
    seekTo(allClips[currentClipIndex].startSec);
  });
}

// 平滑快退到目标片段
function fastBackwardToPrevLoop() {
  if (playingFastChain) return;
  playingFastChain = true;
  isLoopMode = false;
  let idx = currentClipIndex;
  let chain = [];
  for (let i = idx-1; i >= 0; i--) {
    chain.push(i);
    if (allClips[i].type === 'loop') break;
  }
  if (chain.length === 0) return;
  playChainClips(chain.reverse(), () => {
    currentClipIndex = chain[chain.length-1];
    currentClipType = allClips[currentClipIndex].type;
    isLoopMode = true;
    playingFastChain = false;
    seekTo(allClips[currentClipIndex].startSec);
  }, true);
}

// 动画快进/快退片段链
function playChainClips(chain, onFinish, isBackward=false) {
  let playNext = (i) => {
    if (i >= chain.length) {
      onFinish && onFinish();
      return;
    }
    let clip = allClips[chain[i]];
    currentClipIndex = chain[i];
    currentClipType = clip.type;
    let speed = Math.max(clip.jump_speed || 6, 2);
    let curve = clip.animate_curve || 'easeInOut';
    let start = clip.startSec;
    let end = clip.endSec;
    seekTo(start);
    smoothSpeedPlay(start, end, speed, curve, isBackward, ()=>{
      playNext(i+1);
    });
  };
  playNext(0);
}

// 动画加速播放当前片段，到片尾自动回调
function smoothSpeedPlay(start, end, maxSpeed, curve, isBackward, cb) {
  player.currentTime = start;
  let duration = Math.abs(end - start);
  let ease = getEaseFunc(curve);
  let startTs = performance.now();
  let finished = false;
  player.playbackRate = maxSpeed;
  let raf = null;
  function animate(now){
    if (finished) return;
    let t = (now-startTs)/1000;
    let progress = Math.min(1, t/(duration/(maxSpeed*1.5)));
    let speed = 1 + (maxSpeed-1)*ease(progress);
    player.playbackRate = speed;
    if (!isBackward && player.currentTime >= end-0.03) {
      player.playbackRate = 1;
      player.currentTime = end;
      finished = true;
      cb && cb();
      return;
    } else if (isBackward && player.currentTime <= start+0.03) {
      player.playbackRate = 1;
      player.currentTime = start;
      finished = true;
      cb && cb();
      return;
    }
    raf = requestAnimationFrame(animate);
  }
  raf = requestAnimationFrame(animate);
}

// 动画缓动函数
function getEaseFunc(type){
  if(type==='easeInOut'){
    return function(t){ return t<0.5 ? 2*t*t : -1+(4-2*t)*t }
  }
  if(type==='easeIn'){ return function(t){ return t*t } }
  if(type==='easeOut'){ return function(t){ return t*(2-t) } }
  return function(t){ return t }
}

// --- 控制按钮和键盘 ---
$('next-clip').onclick = fastForwardToNextLoop;
$('prev-clip').onclick = fastBackwardToPrevLoop;
$('loop-clip').onclick = () => {
  isLoopMode = true;
  seekTo(allClips[currentClipIndex].startSec);
};

window.addEventListener('keydown', e=>{
  if(e.code==='Space'||e.code==='Enter'){ $('next-clip').click(); }
  else if(e.code==='ArrowLeft'){ $('prev-clip').click(); }
});

// loop 自动循环（片尾无闪烁）
player.addEventListener('ended', ()=>{
  if (timelineUpdating) return;
  if (isLoopMode && currentClipType==='loop') {
    player.currentTime = allClips[currentClipIndex].startSec;
    player.play();
  }
});

// json编辑和保存
$('save-json').onclick = () => {
  let txt = $('json-editor').value;
  try{
    let j = JSON.parse(txt);
    fetch('/api/set_json', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(j)
    }).then(r=>r.json()).then(j=>{
      alert('JSON已更新');
      allClips = j.clips.map((c, i) => ({
        ...c,
        startSec: timeStrToSec(c.start),
        endSec: timeStrToSec(c.end),
        index: i
      }));
      renderTimeline();
    });
  }catch(e){ alert('JSON格式错误'); }
};

// 初始化
window.onload = () => {
  loadResourceList();
  loadJsonAndClips();
  loadVideo();
};