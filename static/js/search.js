// Header search bar
const searchInput = document.getElementById('search-input');
const searchDropdown = document.getElementById('search-dropdown');

if (searchInput) {
  let timer;

  searchInput.addEventListener('input', () => {
    clearTimeout(timer);
    const q = searchInput.value.trim();
    if (!q) { searchDropdown.classList.add('hidden'); return; }
    timer = setTimeout(() => fetchSearch(q, searchDropdown), 250);
  });

  searchInput.addEventListener('focus', () => {
    if (searchInput.value.trim()) searchDropdown.classList.remove('hidden');
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#search-input') && !e.target.closest('#search-dropdown'))
      searchDropdown.classList.add('hidden');
  });

  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      const first = searchDropdown.querySelector('a');
      if (first) window.location.href = first.href;
    }
  });
}

function fetchSearch(q, dropdown) {
  fetch(`/busca/?q=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(data => {
      if (!data.results.length) {
        dropdown.innerHTML = '<p class="px-4 py-3 text-sm text-mute">Nenhum resultado encontrado.</p>';
      } else {
        dropdown.innerHTML = data.results.map(r => `
          <a href="${r.url}" class="flex flex-col px-4 py-3 rounded-2xl hover:bg-card transition">
            <span class="font-semibold text-sm text-ink">${r.title}</span>
            <span class="text-xs text-mute">${r.major}</span>
          </a>`).join('');
      }
      dropdown.classList.remove('hidden');
    })
    .catch(() => {});
}
