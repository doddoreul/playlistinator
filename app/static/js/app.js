function scanLibrary() {
  fetch('/api/scan', {method:'POST'}).then(r=>r.json()).then(res=>{
    alert(`Scan: ${res.added} added, ${res.updated} updated, ${res.skipped} skipped`);
    htmx.trigger('#main-content','load');
    htmx.trigger('#playlists','load');
  });
}
function searchTracks(q) {
  const v = (typeof currentView !== 'undefined') ? currentView : 'musiques';
  htmx.ajax('GET','/api/tracks',{target:'#main-content', values:{q, view:v}});
}
function createPlaylist() {
  const name = prompt('Nom de la playlist ?');
  if (!name) return;
  const fd = new FormData(); fd.append('name', name);
  fetch('/api/playlists',{method:'POST',body:fd}).then(()=>htmx.trigger('#playlists','load'));
}
function renamePlaylist(id) {
  const name = prompt('Nouveau nom ?');
  if (!name) return;
  const fd = new FormData(); fd.append('name', name);
  fetch(`/api/playlists/${id}`,{method:'PUT',body:fd}).then(()=>htmx.trigger('#playlists','load'));
}
function deletePlaylist(id) {
  if (!confirm('Supprimer cette playlist ?')) return;
  fetch(`/api/playlists/${id}`,{method:'DELETE'}).then(()=>htmx.trigger('#playlists','load'));
}
function openPlaylist(id, name) {
  htmx.ajax('GET',`/api/playlists/${id}/tracks`,{target:'#main-content'});
}
function removeFromPlaylist(plId, trackId) {
  fetch(`/api/playlists/${plId}/tracks/${trackId}`,{method:'DELETE'}).then(()=>htmx.ajax('GET',`/api/playlists/${plId}/tracks`,{target:'#main-content'}));
}
function playPlaylist(plId) { playPlaylistFromServer(plId); }
function playPlaylistFromServer(plId) {
  fetch(`/api/playlists/${plId}/tracks.json`).then(r=>r.json()).then(tracks=>{
    queue = tracks; queueIndex = 0;
    if (tracks.length) { currentTrackId = tracks[0].id; setAudioSrc(tracks[0].id,0); audio.play(); }
    saveState();
  });
}
function addToPlaylist(plId, trackIds) {
  const fd = new FormData(); fd.append('track_ids', trackIds.join(','));
  fetch(`/api/playlists/${plId}/tracks`,{method:'POST',body:fd}).then(()=>{});
}
function editTrack(id) {
  const title = prompt('Titre ?');
  const artist = prompt('Artiste ?');
  const album = prompt('Album ?');
  const fd = new FormData();
  if (title !== null) fd.append('title', title);
  if (artist !== null) fd.append('artist', artist);
  if (album !== null) fd.append('album', album);
  fd.append('write_tags_flag','0');
  fetch(`/api/tracks/${id}/edit`,{method:'POST',body:fd}).then(()=>htmx.trigger('#main-content','load'));
}
// Drag & drop to reorder a playlist
document.addEventListener('dragstart', (e) => {
  const li = e.target.closest('li[data-track-id]');
  if (li) e.dataTransfer.setData('text/plain', li.dataset.trackId);
});
document.addEventListener('drop', (e) => {
  const ol = e.target.closest('ol.pl-tracks');
  if (!ol) return;
  e.preventDefault();
  const draggedId = e.dataTransfer.getData('text/plain');
  const targetLi = e.target.closest('li[data-track-id]');
  if (!targetLi || targetLi.dataset.trackId === draggedId) return;
  const items = [...ol.querySelectorAll('li[data-track-id]')];
  const draggedEl = items.find(li => li.dataset.trackId === draggedId);
  if (!draggedEl) return;
  ol.insertBefore(draggedEl, targetLi);
  // envoyer nouvel ordre
  const plId = ol.id.replace('pl-tracks-','');
  const order = [...ol.querySelectorAll('li[data-track-id]')].map(li=>li.dataset.trackId).join(',');
  const fd = new FormData(); fd.append('order', order);
  fetch(`/api/playlists/${plId}/reorder`,{method:'POST',body:fd});
});
document.addEventListener('dragover', (e) => { if (e.target.closest('ol.pl-tracks')) e.preventDefault(); });

function enqueueTrack(id) {
  const row = document.querySelector(`tr[data-track-id="${id}"]`);
  const title = row ? row.dataset.title : '';
  const artist = row ? row.dataset.artist : '';
  if (!queue.find(t => t.id === id)) queue.push({id, title, artist});
  saveState();
}
async function showDetails(id) {
  const panel = document.getElementById('details-panel');
  const content = document.getElementById('details-content');
  if (!panel || !content) return;
  content.innerHTML = '<p class="muted">Chargement…</p>';
  panel.classList.add('open');
  try {
    const r = await fetch(`/api/tracks/${id}`);
    const t = await r.json();
    const dur = t.duration ? (Math.floor(t.duration/60)+':'+String(Math.floor(t.duration%60)).padStart(2,'0')) : '—';
    content.innerHTML = `
      <img src="/cover/${t.id}" alt="">
      <h3>${escapeHtml(t.title || t.path)}</h3>
      <div class="row"><span>Artiste</span><span>${escapeHtml(t.artist || '—')}</span></div>
      <div class="row"><span>Album</span><span>${escapeHtml(t.album || '—')}</span></div>
      <div class="row"><span>Duration</span><span>${dur}</span></div>
      <div class="row"><span>Chemin</span><span>${escapeHtml(t.path)}</span></div>
      <div style="margin-top:12px;display:flex;gap:8px;">
        <button onclick="playTrack(${t.id})">▶ Lire</button>
        <button onclick="enqueueTrack(${t.id})">+ file</button>
      </div>`;
  } catch(e) {
    content.innerHTML = '<p class="muted">Erreur</p>';
  }
}
function closeDetails() {
  const panel = document.getElementById('details-panel');
  if (panel) panel.classList.remove('open');
}
function escapeHtml(s){ return String(s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
// Home page logic
function renderHomeQueue() {
  const ol = document.getElementById('home-queue');
  const empty = document.getElementById('home-queue-empty');
  if (!ol) return;
  if (!queue || !queue.length) { ol.innerHTML=''; if(empty) empty.style.display='block'; return; }
  if(empty) empty.style.display='none';
  ol.innerHTML = queue.map((t) => `<li style="padding:4px 0;border-bottom:1px solid var(--border);cursor:pointer;" onclick="playTrack(${t.id})">${escapeHtml(t.title||t.path)} — ${escapeHtml(t.artist||'')}</li>`).join('');
}
function updateHomeMeta(trackId) {
  const cover = document.getElementById('home-cover');
  if (cover) cover.src = `/cover/${trackId}`;
  const t = findTrack(trackId);
  const title = document.getElementById('home-title');
  if (title) title.textContent = t ? (t.title || t.path) : '—';
  const artist = document.getElementById('home-artist');
  if (artist) artist.textContent = t ? (t.artist || '') : '';
  const album = document.getElementById('home-album');
  if (album) album.textContent = t ? (t.album || '') : '';
}
if (document.getElementById('home-queue')) {
  const _orig = updatePlayerMeta;
  updatePlayerMeta = function(trackId) {
    _orig(trackId);
    updateHomeMeta(trackId);
  };
  setInterval(renderHomeQueue, 1000);
  setTimeout(renderHomeQueue, 200);
  if (currentTrackId) updateHomeMeta(currentTrackId);
}
function searchCovers(id) {
  fetch(`/api/tracks/${id}/covers`).then(r=>r.json()).then(data=>{
    const res = data.results || [];
    if (!res.length) { alert('No cover found'); return; }
    const url = res[0].image_url;
    if (confirm('Appliquer cette pochette ?')) {
      const fd = new FormData(); fd.append('image_url', url);
      fetch(`/api/tracks/${id}/cover`,{method:'POST',body:fd}).then(()=>htmx.trigger('#main-content','load'));
    }
  });
}