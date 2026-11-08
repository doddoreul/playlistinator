function scanLibrary() {
  fetch('/api/scan', {method:'POST'}).then(r=>r.json()).then(res=>{
    alert(`Scan: ${res.added} ajoutés, ${res.updated} mis à jour, ${res.skipped} ignorés`);
    htmx.trigger('#main-content','load');
    htmx.trigger('#playlists','load');
  });
}
function searchTracks(q) {
  htmx.ajax('GET','/api/tracks',{target:'#main-content', values:{q}});
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
// Drag & drop pour réordonner une playlist
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

function searchCovers(id) {
  fetch(`/api/tracks/${id}/covers`).then(r=>r.json()).then(data=>{
    const res = data.results || [];
    if (!res.length) { alert('Aucune pochette trouvée'); return; }
    const url = res[0].image_url;
    if (confirm('Appliquer cette pochette ?')) {
      const fd = new FormData(); fd.append('image_url', url);
      fetch(`/api/tracks/${id}/cover`,{method:'POST',body:fd}).then(()=>htmx.trigger('#main-content','load'));
    }
  });
}