// Keep the same data available without relying on color, hover, or canvas.
if (window.Chart) {
  Chart.defaults.font.family = 'system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = '#625d58';
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) Chart.defaults.animation = false;
  Chart.register({
    id: 'accessibleData',
    afterInit(chart) {
      const title = chart.canvas.closest('.deco-card')?.querySelector('h2')?.textContent.trim() || 'Données du graphique';
      chart.canvas.setAttribute('role', 'img');
      chart.canvas.setAttribute('aria-label', title + '. Données disponibles dans le tableau suivant.');
      const details = document.createElement('details');
      details.className = 'chart-data';
      const summary = document.createElement('summary');
      summary.textContent = 'Afficher les données';
      details.append(summary);
      const region = document.createElement('div');
      region.className = 'overflow-x-auto';
      region.tabIndex = 0;
      region.setAttribute('role', 'region');
      region.setAttribute('aria-label', title);
      const table = document.createElement('table');
      const caption = table.createCaption();
      caption.className = 'sr-only';
      caption.textContent = title;
      const header = table.createTHead().insertRow();
      ['Catégorie', ...chart.data.datasets.map(data => data.label || 'Valeur')].forEach(label => {
        const th = document.createElement('th');
        th.scope = 'col';
        th.textContent = label;
        header.append(th);
      });
      const body = table.createTBody();
      chart.data.labels.forEach((label, index) => {
        const row = body.insertRow();
        const th = document.createElement('th');
        th.scope = 'row';
        th.textContent = label;
        row.append(th);
        chart.data.datasets.forEach(data => {
          const value = data.data[index];
          row.insertCell().textContent = typeof value === 'number'
            ? value.toLocaleString('fr-FR', { maximumFractionDigits: 2 }) : value ?? '—';
        });
      });
      region.append(table);
      details.append(region);
      chart.canvas.parentElement.after(details);
    }
  });
}
