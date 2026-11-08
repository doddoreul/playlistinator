const audio = document.getElementById('audio');
let queue = [];
let queueIndex = 0;
let repeatMode = 0; // 0 none, 1 one, 2 all
let shuffle = false;

function loadState() {
  try {
    const s = JSON.parse(localStorage.getItem('playerState') || '{}');
    queue = s.queue || [];
    queueIndex = s.index || 0;
    if (s.volume != null) audio.volume = s.volume;
    if (s.trackId) {
      setAudioSrc(s.trackId, s.position || 0);
    }
  } catch(e) {}
}
function saveState() {
  const s = { queue, index: queueIndex, trackId: currentTrackId, position: audio.currentTime, volume: audio.volume };
  localStorage.setItem('playerState', JSON.stringify(s));
}
let currentTrackId = null;

function setAudioSrc(trackId, pos) {
  currentTrackId = trackId;
  audio.src = `/stream/${trackId}`;
  audio.addEventListener('loadedmetadata', () => { if (pos) audio.currentTime = pos; }, { once: true });
  updatePlayerMeta(trackId);
}

async function updatePlayerMeta(trackId) {
  // fetch track info from a simple endpoint? We'll store in queue objects.
  const t = findTrack(trackId);
  if (t) {
    document.getElementById('player-title').textContent = t.title || t.path;
    document.getElementById('player-artist').textContent = t.artist || '';
    const cover = document.getElementById('player-cover');
    cover.src = `/cover/${trackId}`;
  }
}

function findTrack(id) {
  return queue.find(t => t.id === id) || null;
}

function playTrack(id) {
  // if not in queue, build queue from current track list? Add single.
  const trackObj = { id };
  // try to enrich from DOM? We'll just play; meta fetched lazily.
  currentTrackId = id;
  setAudioSrc(id, 0);
  audio.play();
  saveState();
}

function playPlaylist(plId) {
  fetch(`/api/playlists/${plId}/tracks.json`).then(r=>r.json()).then(tracks => {
    queue = tracks;
    queueIndex = 0;
    if (tracks.length) {
      currentTrackId = tracks[0].id;
      setAudioSrc(tracks[0].id, 0);
      audio.play();
    }
    saveState();
  });
}

function togglePlay() {
  if (audio.paused) audio.play(); else audio.pause();
}
function nextTrack() {
  if (!queue.length) return;
  if (shuffle) queueIndex = Math.floor(Math.random()*queue.length);
  else queueIndex = (queueIndex + 1) % queue.length;
  const t = queue[queueIndex];
  if (t) { currentTrackId = t.id; setAudioSrc(t.id, 0); audio.play(); saveState(); }
}
function prevTrack() {
  if (!queue.length) return;
  queueIndex = (queueIndex - 1 + queue.length) % queue.length;
  const t = queue[queueIndex];
  if (t) { currentTrackId = t.id; setAudioSrc(t.id, 0); audio.play(); saveState(); }
}
function seek(val) {
  if (audio.duration) audio.currentTime = (val/1000)*audio.duration;
}
function setVolume(v) { audio.volume = parseFloat(v); saveState(); }

audio.addEventListener('timeupdate', () => {
  if (audio.duration) {
    document.getElementById('progress').value = (audio.currentTime/audio.duration)*1000;
  }
  document.getElementById('time').textContent = fmt(audio.currentTime);
  saveState();
});
audio.addEventListener('ended', () => {
  if (repeatMode === 1) { audio.currentTime = 0; audio.play(); }
  else if (repeatMode === 2 || queue.length > 1) { nextTrack(); }
});
function fmt(s) { const m = Math.floor(s/60); const sec = Math.floor(s%60); return m+':'+String(sec).padStart(2,'0'); }

// keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
  else if (e.code === 'ArrowRight') { audio.currentTime = Math.min(audio.duration, audio.currentTime + 5); }
  else if (e.code === 'ArrowLeft') { audio.currentTime = Math.max(0, audio.currentTime - 5); }
  else if (e.key === 'n' || e.key === 'N') { nextTrack(); }
  else if (e.key === 'p' || e.key === 'P') { prevTrack(); }
});

window.addEventListener('beforeunload', saveState);
loadState();