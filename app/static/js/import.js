document.getElementById('import-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = document.getElementById('import-url').value.trim();
  const status = document.getElementById('import-status');
  status.textContent = 'Starting...';
  const fd = new FormData(); fd.append('url', url);
  const r = await fetch('/api/import/url', {method:'POST', body:fd});
  const data = await r.json();
  if (data.error) { status.textContent = 'Erreur: ' + data.error; return; }
  const jobId = data.job_id;
  const poll = setInterval(async () => {
    const sr = await fetch(`/api/import/status/${jobId}`);
    const j = await sr.json();
    if (j.total) {
      const pct = Math.round((j.progress / j.total) * 100);
      status.textContent = `${j.status} - ${pct}%`;
    } else {
      status.textContent = j.status;
    }
    if (j.done) {
      clearInterval(poll);
      if (j.status === 'done') status.textContent = 'Import done (track #' + j.track_id + ')';
      else if (j.status === 'duplicate') status.textContent = 'Duplicate detected, please check manually in the Duplicates section';
      else status.textContent = 'Erreur: ' + (j.error || '');
    }
  }, 500);
});