// Keep keyboard focus inside an open dialog or mobile navigation.
document.addEventListener('alpine:init', () => {
  const focusable = element => [...element.querySelectorAll('a[href], button, input, select, textarea, [tabindex="0"]')]
    .filter(node => !node.disabled && node.getClientRects().length && !node.closest('[inert]'));
  document.querySelectorAll('[role="dialog"], #app-sidebar').forEach(panel => {
    let previousFocus;
    let wasOpen = false;
    const isOpen = () => panel.id === 'app-sidebar'
      ? window.innerWidth < 1024 && !panel.inert
      : getComputedStyle(panel).display !== 'none';
    const observer = new MutationObserver(() => {
      const open = isOpen();
      if (open && !wasOpen) {
        previousFocus = document.activeElement;
        requestAnimationFrame(() => focusable(panel)[0]?.focus());
      } else if (!open && wasOpen) {
        previousFocus?.focus();
      }
      wasOpen = open;
    });
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
