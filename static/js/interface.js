// Keep keyboard focus inside an open dialog or mobile navigation.
document.addEventListener('alpine:initialized', () => {
  document.querySelectorAll('#app-sidebar nav a').forEach(link => {
    if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
  });
  const focusable = element => [...element.querySelectorAll('a[href], button, input, select, textarea, [tabindex="0"]')]
    .filter(node => !node.disabled && node.getClientRects().length && !node.closest('[inert]'));
  document.querySelectorAll('[role="dialog"], #app-sidebar').forEach(panel => {
    let previousFocus;
    let wasOpen = false;
    const isOpen = () => panel.id === 'app-sidebar'
      ? window.innerWidth < 1024 && !panel.inert
      : getComputedStyle(panel).display !== 'none';
    const sync = () => {
      const open = isOpen();
      if (open && !wasOpen) {
        previousFocus = document.activeElement;
        requestAnimationFrame(() => { if (isOpen()) focusable(panel)[0]?.focus(); });
      } else if (!open && wasOpen) {
        requestAnimationFrame(() => {
          if (previousFocus?.isConnected && !previousFocus.closest('[inert]')) previousFocus.focus();
          else if (!document.querySelector('[role="dialog"]:not([style*="display: none"])') && window.innerWidth < 1024) {
            document.querySelector('[aria-controls="app-sidebar"]')?.focus();
          }
        });
      }
      wasOpen = open;
      const modalOpen = [...document.querySelectorAll('[role="dialog"]')]
        .some(dialog => getComputedStyle(dialog).display !== 'none');
      const sidebar = document.getElementById('app-sidebar');
      const menuOpen = sidebar && window.innerWidth < 1024 && !sidebar.inert;
      document.body.style.overflow = modalOpen || menuOpen ? 'hidden' : '';
    };
    const observer = new MutationObserver(sync);
    window.addEventListener('resize', sync);
    sync();
    observer.observe(panel, { attributes: true, attributeFilter: ['style', 'class', 'inert'] });
    panel.addEventListener('keydown', event => {
      if (event.key !== 'Tab' || !isOpen()) return;
      const items = focusable(panel);
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });
  });
});
