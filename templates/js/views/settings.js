import { h, icon, clear, append } from '../core/dom.js';
import { getJSON, postJSON, rpcSafe } from '../core/api.js';
import { store } from '../core/store.js';
import { toast, confirm } from '../core/ui.js';

const PROVIDERS = [
  ['openai', 'OpenAI', 'gpt-4o-mini, gpt-4.1…'],
  ['deepseek', 'DeepSeek', 'deepseek-chat (cheap)'],
  ['openrouter', 'OpenRouter', 'any model, one key'],
  ['groq', 'Groq', 'fast Llama models'],
  ['custom', 'Custom / local', 'LM Studio, Ollama, vLLM'],
];
const SECTIONS = [['ai', 'AI assistant'], ['playback', 'Playback'], ['folders', 'Folders & merger'], ['providers', 'Downloads & sources'], ['hotkeys', 'Hotkeys'], ['about', 'About']];

export const settingsView = {
  id: 'settings', title: 'Settings', icon: 'settings', rail: false,
  async mount(el) {
    let data = store.state.settings || {};
    let keys = { ...(data.keys || {}) };
    let merger = { ...(data.merger || {}) };
    const nav = h('.settings-nav');
    const body = h('div');
    el.append(h('.view-inner', h('.settings-layout', nav, body)));
    let active = 'ai';

    const load = async () => { const r = await getJSON('/api/settings').catch(() => null); if (r?.status === 'success') { data = r; keys = { ...r.keys }; merger = { ...r.merger }; store.state.settings = r; } };
    const save = async (patch) => {
      const r = await postJSON('/api/settings', patch).catch(e => ({ status: 'error', message: e.message }));
      if (r.status !== 'success') return toast('Save failed: ' + r.message, { kind: 'err' });
      data = r; keys = { ...r.keys }; merger = { ...r.merger }; store.state.settings = r;
      toast('Saved', { kind: 'ok' });
      render();
    };

    const field = (label, key, { type = 'text', hint = '', placeholder = '', secret = false } = {}) => {
      const input = h('input.input', { type: secret ? 'password' : type, value: keys[key] ?? '', placeholder, dataset: { key } });
      if (secret) { const wrap = h('.hstack', input, h('button.btn.icon.ghost', { onClick: () => { input.type = input.type === 'password' ? 'text' : 'password'; } }, icon('eye', 16))); return h('.field', h('label', label), wrap, hint ? h('span.hint', hint) : null); }
      return h('.field', h('label', label), input, hint ? h('span.hint', hint) : null);
    };
    const collect = (root) => { const out = {}; root.querySelectorAll('[data-key]').forEach(i => out[i.dataset.key] = i.type === 'checkbox' ? i.checked : i.value); return out; };

    const sections = {
      ai() {
        const a = data.assistant || {};
        const status = h('.status-line', h('span.dot', { class: a.has_key ? 'ok' : '' }), a.has_key ? `Configured: ${a.provider} · ${a.model}` : 'No API key configured yet');
        let provider = keys.AI_PROVIDER || a.provider || 'openai';
        const cards = h('.provider-cards');
        const form = h('.form-grid');
        const renderForm = () => {
          clear(cards);
          for (const [id, name, sub] of PROVIDERS) cards.appendChild(h('button.provider-card', { class: id === provider ? 'is-active' : '', onClick: () => { provider = id; renderForm(); } }, h('b', name), h('small', sub)));
          clear(form);
          append(form, [
            h('input', { type: 'hidden', dataset: { key: 'AI_PROVIDER' }, value: provider }),
            field('API key', 'AI_API_KEY', { secret: true, placeholder: keys.has_AI_API_KEY ? '' : 'sk-…', hint: 'Stored locally in keys.json. Leave blank to use the provider-specific key below.' }),
            field('Model', 'AI_MODEL', { placeholder: { openai: 'gpt-4o-mini', deepseek: 'deepseek-chat', openrouter: 'openai/gpt-4o-mini', groq: 'llama-3.3-70b-versatile', custom: 'local-model' }[provider], hint: 'Must support tool calling.' }),
            provider === 'custom' ? field('Base URL', 'AI_BASE_URL', { placeholder: 'http://127.0.0.1:1234/v1', hint: 'OpenAI-compatible /chat/completions endpoint.' }) : null,
            provider === 'openai' ? field('OpenAI key (fallback)', 'OPENAI_API_KEY', { secret: true }) : null,
            provider === 'deepseek' ? field('DeepSeek key (fallback)', 'DEEPSEEK_API_KEY', { secret: true }) : null,
            field('Tavily key (web search)', 'TAVILY_API_KEY', { secret: true, hint: 'Optional. Lets the assistant search the web for recommendations and release info.' }),
          ]);
        };
        renderForm();
        const testBtn = h('button.btn.ghost', { onClick: async () => { testBtn.disabled = true; const r = await postJSON('/api/assistant/test').catch(e => ({ status: 'error', message: e.message })); testBtn.disabled = false; toast(r.status === 'success' ? `OK · ${r.provider} · ${r.model} replied "${r.reply}"` : 'Failed: ' + r.message, { kind: r.status === 'success' ? 'ok' : 'err', ms: 5000 }); } }, 'Test connection');
        return h('.settings-section', h('h2', 'AI assistant'), h('p', 'The :3 assistant uses any OpenAI-compatible API. It can search your library and the catalog, play episodes, find and add torrents, run the merger and more.'), status, cards, form,
          h('.hstack', { style: { marginTop: '14px' } }, h('button.btn.primary', { onClick: async () => { await save({ keys: collect(form) }); } }, 'Save'), testBtn, h('button.btn.ghost', { onClick: async () => { if (await confirm('Clear chat history', 'Delete the assistant conversation history?')) { await postJSON('/api/assistant/clear'); toast('History cleared'); document.dispatchEvent(new CustomEvent('assistant:reload')); } } }, 'Clear history')));
      },
      playback() {
        const p = store.prefs;
        const num = (label, key, hint) => h('.field', h('label', label), h('input.input', { type: 'number', min: 0, value: p[key], onChange: (e) => store.setPref(key, Number(e.target.value) || 0) }), hint ? h('span.hint', hint) : null);
        const sw = (label, key, hint) => h('.field', h('label.switch', h('input', { type: 'checkbox', checked: !!p[key], onChange: (e) => store.setPref(key, e.target.checked) }), h('span', label)), hint ? h('span.hint', hint) : null);
        return h('.settings-section', h('h2', 'Playback'), h('p', 'Player defaults. Skip markers can also be set per title from the player menu.'), h('.form-grid',
          sw('Auto-play next episode', 'autoNext'), sw('Keep playing in mini player when browsing', 'miniPlayerOnBrowse'),
          num('Default intro length (s)', 'skipIntroDefault', 'The "Skip intro" button appears for the first N seconds.'), num('Outro starts before end (s)', 'outroOffset'),
          num('Seek step for ← → (s)', 'seekStep'), num('Subtitle size (%)', 'subtitleSize'),
          h('.field', h('label', 'Catalog language'), h('select.select', { onChange: (e) => save({ keys: { CATALOG_LANGUAGE: e.target.value } }) }, ...[['en-US', 'English'], ['ru-RU', 'Russian'], ['ja-JP', 'Japanese'], ['uk-UA', 'Ukrainian']].map(([v, l]) => h('option', { value: v, selected: (keys.CATALOG_LANGUAGE || 'en-US') === v }, l))), h('span.hint', 'Titles and synopses for movies/shows (TMDB).')),
        ));
      },
      folders() {
        const f = (label, key, hint) => h('.field', h('label', label), h('input.input', { value: merger[key] ?? '', dataset: { mkey: key } }), hint ? h('span.hint', hint) : null);
        const form = h('.form-grid', f('RAW folder', 'raw_folder', 'Original video files land here.'), f('DUB folder', 'dub_folder', 'Dub audio/video files land here.'), f('Output folder', 'output_folder'), f('Library root', 'library_root', 'Merged episodes are organized here (empty = default Videos folder).'), f('ffmpeg path', 'ffmpeg_path'), f('ffprobe path', 'ffprobe_path'),
          h('.field', h('label', 'Voice isolation (Demucs)'), h('select.select', { dataset: { mkey: 'voice_isolation' } }, h('option', { value: 'off', selected: merger.voice_isolation !== 'demucs' }, 'Off'), h('option', { value: 'demucs', selected: merger.voice_isolation === 'demucs' }, 'Demucs voice overlay'))));
        const app = store.state.app || {};
        return h('.settings-section', h('h2', 'Folders & merger'), h('p', `Workflow folder: ${app.workflow_dir || ''} · Library: ${app.library_dir || ''}`),
          h('.status-line', h('span.dot', { class: app.ffmpeg ? 'ok' : 'err' }), app.ffmpeg ? 'FFmpeg found' : 'FFmpeg not found: playback fixes, TS remux and merging need it (add ffmpeg.exe next to the app or to PATH).'),
          form, h('.hstack', { style: { marginTop: '14px' } }, h('button.btn.primary', { onClick: () => { const out = {}; form.querySelectorAll('[data-mkey]').forEach(i => out[i.dataset.mkey] = i.value); save({ merger: out }); } }, 'Save'), h('button.btn.ghost', { onClick: () => rpcSafe('open_library_folder') }, icon('folder', 16), 'Open library folder'), h('button.btn.ghost', { onClick: () => rpcSafe('open_path', app.workflow_dir) }, icon('folder', 16), 'Open workflow folder')));
      },
      providers() {
        const form = h('.form-grid',
          field('TMDB API key (optional)', 'TMDB_API_KEY', { secret: true, hint: 'A built-in key is used when empty.' }),
          field('DUB source URL', 'DUB_SOURCE_URL', { placeholder: 'https://…', hint: 'Site opened by "Open DUB browser". You log in and download manually; the merger picks files up from Downloads.' }),
          field('DUB provider command', 'DUB_PROVIDER_COMMAND', { placeholder: 'python my_dub_tool.py', hint: 'Optional external tool you own. Called as: <cmd> list-voices --title X | download --title X --season N --episode N --output DIR. Must print JSON.' }),
          field('Preferred dub studios', 'PREFERRED_DUB_ORDER', { placeholder: 'Дубляж, JAM, AniLibria' }),
          field('Prowlarr URL', 'PROWLARR_URL', { placeholder: 'http://127.0.0.1:9696', hint: 'Movie / show RAW search (self-hosted).' }),
          field('Prowlarr API key', 'PROWLARR_API_KEY', { secret: true }),
          field('FlareSolverr URL', 'FLARESOLVERR_URL', { placeholder: 'http://127.0.0.1:8191' }),
          field('FlareSolverr path (autostart)', 'FLARESOLVERR_PATH'),
          field('qBittorrent WebUI URL', 'QBIT_URL', { placeholder: 'http://127.0.0.1:8080', hint: 'Fallback when libtorrent is unavailable.' }),
          field('qBittorrent user', 'QBIT_USERNAME'), field('qBittorrent password', 'QBIT_PASSWORD', { secret: true }),
        );
        const app = store.state.app || {};
        return h('.settings-section', h('h2', 'Downloads & sources'), h('p', 'Anime RAW search uses Nyaa and needs nothing. Movies and shows need Prowlarr.'),
          h('.status-line', h('span.dot', { class: app.libtorrent ? 'ok' : '' }), app.libtorrent ? 'Internal torrent engine (libtorrent) available' : 'libtorrent not installed: torrents are handed to qBittorrent or saved as .torrent files'),
          form, h('.hstack', { style: { marginTop: '14px' } }, h('button.btn.primary', { onClick: () => save({ keys: collect(form) }) }, 'Save')));
      },
      hotkeys() {
        const keys = [['Space / K', 'Play / pause'], ['← / →', 'Seek'], ['J / L', 'Seek 10 s'], ['Shift + ← / →', 'Prev / next'], ['↑ / ↓', 'Volume'], ['M', 'Mute'], ['F', 'Fullscreen'], ['S', 'Skip intro / outro'], ['A', 'Aspect'], ['C', 'Subtitles'], ['B', 'Bookmark'], ['P', 'Playlist'], [', / .', 'Speed'], ['0–9', 'Jump'], ['Esc', 'Mini player'], ['/', 'Search'], ['Ctrl + K', 'Assistant'], ['?', 'Help']];
        return h('.settings-section', h('h2', 'Hotkeys'), h('.hotkeys', ...keys.map(([k, v]) => h('.hotkey', h('span', v), h('kbd', k)))));
      },
      about() {
        const app = store.state.app || {};
        return h('.settings-section', h('h2', 'About'), h('dl.kv', h('dt', 'Version'), h('dd', app.version || ''), h('dt', 'Port'), h('dd', String(app.port || '')), h('dt', 'Desktop window'), h('dd', app.window ? 'yes' : 'no (browser mode)'), h('dt', 'Data folder'), h('dd', app.user_data_dir || ''), h('dt', 'keys.json'), h('dd', data.keys_file || '')));
      },
    };

    const render = () => {
      clear(nav);
      for (const [id, label] of SECTIONS) nav.appendChild(h('button', { class: id === active ? 'is-active' : '', onClick: () => { active = id; render(); } }, label));
      clear(body); body.appendChild(sections[active]());
    };
    await load();
    render();
    return { show: async (p) => { if (p?.section) active = p.section; await load(); render(); }, refresh: render };
  },
};
