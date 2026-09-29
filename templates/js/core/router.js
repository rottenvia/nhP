// View registry + animated navigation. Views are mounted lazily on first visit
// and kept in the DOM afterwards (hidden with opacity/visibility, never display:none,
// so transitions actually run and scroll positions survive).

import { h, icon, $ } from './dom.js';

const views = new Map();
let current = null;
const stack = [];
const railButtons = new Map();

export const router = {
  register(def) { views.set(def.id, { ...def, mounted: false, el: null }); },

  get current() { return current; },

  mountRail() {
    const rail = $('#rail-items');
    for (const v of views.values()) {
      if (!v.rail) continue;
      const btn = h('button.rail-item', { dataset: { nav: v.id }, title: v.title }, icon(v.icon, 21), h('span', v.title));
      btn.addEventListener('click', () => this.go(v.id));
      rail.appendChild(btn);
      railButtons.set(v.id, btn);
    }
    document.querySelectorAll('[data-nav]').forEach(b => { if (!b.classList.contains('rail-item') || !railButtons.has(b.dataset.nav)) b.addEventListener('click', () => this.go(b.dataset.nav)); });
    document.querySelector('.rail-bottom [data-nav="settings"]')?.addEventListener('click', () => this.go('settings'));
  },

  async go(id, params = {}, { replace = false } = {}) {
    const v = views.get(id);
    if (!v) return console.warn('[router] unknown view', id);
    if (current === id && !params.force) { v.instance?.refresh?.(params); return; }
    if (!v.mounted) {
      v.el = h('section.view', { dataset: { view: id } });
      $('#views').appendChild(v.el);
      try { v.instance = await v.mount(v.el, params); } catch (e) { console.error('[router] mount failed', id, e); }
      v.mounted = true;
    }
    const prev = current ? views.get(current) : null;
    if (prev && prev.el) {
      prev.el.classList.remove('is-active');
      prev.el.classList.add('is-leaving');
      setTimeout(() => prev.el.classList.remove('is-leaving'), 250);
      prev.instance?.hide?.();
    }
    if (current && !replace) stack.push(current);
    current = id;
    v.el.classList.add('is-active');
    v.instance?.show?.(params);
    $('#topbar-title').textContent = params.title || v.title;
    for (const [k, b] of railButtons) b.classList.toggle('is-active', k === id);
    document.querySelectorAll('.rail-bottom [data-nav]').forEach(b => b.classList.toggle('is-active', b.dataset.nav === id));
    $('#nav-back').hidden = stack.length === 0;
    document.dispatchEvent(new CustomEvent('view:change', { detail: { id, params } }));
  },

  back() {
    const prev = stack.pop();
    if (prev) { this.go(prev, {}, { replace: true }); stack.pop(); $('#nav-back').hidden = stack.length === 0; }
  },

  refresh(id) { views.get(id)?.instance?.refresh?.(); },
  instance(id) { return views.get(id)?.instance; },
  isMounted(id) { return !!views.get(id)?.mounted; },
};
