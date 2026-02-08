# Bugs and Enhancements

## Planned Features (from GEMINI.md)

- [ ] **Admin Switch for Offline Mode:** Add functionality in `admin.py` to "stop" the current survey, effectively putting the site into offline mode (`index_off.html`).
- [ ] **Enhanced Offline Page:** Update `index_off.html` to include the "FlyerFerteiler" text within the Matrix rain effect, while ensuring Impressum and Datenschutz remain accessible.

## Fixes

- [ ] **`app.py` Robustness:** Ensure `app.py` gracefully handles the absence of `data/streets_status.json` by showing the offline page instead of crashing.