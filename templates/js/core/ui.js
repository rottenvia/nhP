// Toasts, modals, context menus, task overlay.
import { h, icon, clear, $ } from './dom.js';

export function toast(message, { kind = '', ms = 2600 } = {}) {
  const root = $('#toast-root');
  const el = h('.toast', { class: kind }, kind === 'ok' ? icon('check', 16) : (kind === 'err' ? icon('x', 16) : null), h('span', message));
  root.appendChild(el);
  while (root.children.length > 4) root.firstChild.remove();
  setTimeout(() => { el.classList.add('leaving'); setTimeout(() => el.remove(), 250); }, ms);
  return el;
}

let modalStack = [];

/**
 * modal({ title, body: Node|string, actions:[{label, kind, value, onClick}], wide, dismissable })
 * resolves with the value of the clicked action (or null when dismissed).
 */
export function modal({ title, body, actions = [{ label: 'Close', value: null }], wide = false, dismissable = true, onOpen } = {}) {
  return new Promise(resolve => {
    const box = h('.modal', { class: wide ? 'wide' : '', role: 'dialog', 'aria-modal': 'true' });
    if (title) box.appendChild(h('h2', title));
    if (body) box.appendChild(typeof body === 'string' ? h('p', body) : h('.m-body', body));
    const bar = h('.m-actions');
    let done = false;
    const close = (value) => { if (done) return; done = true; back.classList.remove('is-open'); setTimeout(() => back.remove(), 220); modalStack = modalStack.filter(m => m !== back); resolve(value); };
    for (const a of actions) {
      bar.appendChild(h('button.btn', { class: a.kind || '', onClick: async () => { if (a.onClick) { const r = await a.onClick(close); if (r === false) return; } close(a.value); } }, a.label));
    }
    if (actions.length) box.appendChild(bar);
    const back = h('.modal-backdrop', box);
    back.addEventListener('click', e => { if (dismissable && e.target === back) close(null); });
    back._close = close; back._dismissable = dismissable;
    $('#modal-root').appendChild(back);
    modalStack.push(back);
    requestAnimationFrame(() => back.classList.add('is-open'));
    onOpen?.(box, close);
  });
}

export function closeTopModal() {
  const top = modalStack[modalStack.length - 1];
  if (top && top._dismissable) { top._close(null); return true; }
  return false;
}

export function confirm(title, text, { okLabel = 'Confirm', danger = false } = {}) {
  return modal({ title, body: text, actions: [{ label: 'Cancel', value: false, kind: 'ghost' }, { label: okLabel, value: true, kind: danger ? 'danger' : 'primary' }] });
}

export function prompt(title, { placeholder = '', value = '', okLabel = 'OK' } = {}) {
  const input = h('input.input', { placeholder, value });
  return modal({
    title, body: input,
    actions: [{ label: 'Cancel', value: null, kind: 'ghost' }, { label: okLabel, kind: 'primary', onClick: (close) => { close(input.value.trim()); return false; } }],
    onOpen: () => setTimeout(() => input.focus(), 50),
  });
}

/** Context menu at (x,y). items: [{label, icon, onClick, danger, sep}] */
export function contextMenu(x, y, items) {
  closeContextMenu();
  const menu = h('.context-menu');
  for (const it of items) {
    if (it.sep) { menu.appendChild(h('.sep')); continue; }
    menu.appendChild(h('button', { class: it.danger ? 'danger' : '', onClick: () => { closeContextMenu(); it.onClick?.(); } }, it.icon ? icon(it.icon, 16) : null, h('span', it.label)));
  }
  const root = $('#context-root');
  root.appendChild(menu);
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, innerWidth - r.width - 8) + 'px';
  menu.style.top = Math.min(y, innerHeight - r.height - 8) + 'px';
  setTimeout(() => {
    document.addEventListener('pointerdown', onDocDown, { capture: true });
    document.addEventListener('keydown', onEsc);
  }, 0);
}
function onDocDown(e) { if (!e.target.closest('.context-menu')) closeContextMenu(); }
function onEsc(e) { if (e.key === 'Escape') closeContextMenu(); }
export function closeContextMenu() {
  clear($('#context-root'));
  document.removeEventListener('pointerdown', onDocDown, { capture: true });
  document.removeEventListener('keydown', onEsc);
}

let taskEl = null;
export function taskOverlay(title, subtitle = '', progress = null) {
  if (!taskEl) {
    taskEl = h('.task-overlay', h('.task-card', h('h3'), h('p'), h('.progress-bar', h('i')), h('button.btn.ghost.sm', { onClick: () => hideTask() }, 'Hide')));
    document.body.appendChild(taskEl);
  }
  taskEl.querySelector('h3').textContent = title;
  taskEl.querySelector('p').textContent = subtitle;
  const bar = taskEl.querySelector('.progress-bar i');
  if (progress == null) { bar.style.width = '35%'; bar.style.animation = 'shimmer 1.2s infinite'; }
  else { bar.style.animation = ''; bar.style.width = Math.max(2, Math.min(100, progress)) + '%'; }
}
export function hideTask() { if (taskEl) { taskEl.remove(); taskEl = null; } }
