# Bugs and Enhancements

## Bugs
- [x] Map Overlay Shift: When zooming to selected streets for PDF export, the colored street overlay is shifted to the left and the map appears distorted. (Fixed by switching to `leaflet-simple-map-screenshoter`)
- [x] Regression: Map only shows Germany (default view), no overlays/streets are rendered. Likely JS error preventing `init()` from running. (Fixed: moved screenshoter script to load after Leaflet)
