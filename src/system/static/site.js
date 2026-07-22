(function () {
  const button = document.querySelector('[data-mobile-menu-button]');
  const menu = document.querySelector('[data-mobile-menu]');
  if (button && menu) {
    button.addEventListener('click', function () {
      const isOpen = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', String(!isOpen));
      menu.hidden = isOpen;
      document.body.classList.toggle('menu-open', !isOpen);
    });
  }

  document.querySelectorAll('[data-tab-target]').forEach(function (button) {
    button.addEventListener('click', function () {
      const root = button.closest('[data-tabs]');
      if (!root) return;
      const target = button.getAttribute('data-tab-target');
      root.querySelectorAll('[data-tab-target]').forEach(function (item) {
        item.classList.toggle('is-active', item === button);
        item.setAttribute('aria-selected', item === button ? 'true' : 'false');
      });
      root.querySelectorAll('[data-tab-panel]').forEach(function (panel) {
        panel.hidden = panel.getAttribute('data-tab-panel') !== target;
      });
    });
  });
})();
