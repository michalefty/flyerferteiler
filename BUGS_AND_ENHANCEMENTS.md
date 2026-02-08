# Bugs and Enhancements

## Completed Tasks
- [x] **PDF Map Zoom:** The map now automatically zooms to the bounding box of the selected streets before generating the PDF screenshot. This ensures the relevant area is visible and detailed. (`templates/index.html`)
- [x] **Map Width on Mobile:** Added a CSS media query to reduce map width to 90% and center it on devices with width <= 768px. This improves scrolling experience by preventing the map from trapping all touch events. (`templates/index.html`)
- [x] **Admin Safety Check:** Added `check_active_survey()` to `admin.py`. It warns the administrator if a flyer survey is currently active (based on start date and duration) before they can overwrite it with a new plan.
- [x] **Netcup DNS API:** Implemented automatic DNS A-record updates via Netcup CCP API.
    - Created `admin_modules/netcup.py` with `update_dns_record` function.
    - Integrated into `admin_modules/vm.py` to trigger update after VM start.
    - Requires `NETCUP_API_KEY`, `NETCUP_API_PASSWORD`, `NETCUP_CUSTOMER_NUMBER`, `NETCUP_DOMAIN` in `config.py`.
- [x] **PDF Workflow Evaluation:** Evaluated `leaflet-easyPrint`. Decided to stick with and improve the existing `jsPDF` + `html2canvas` workflow as it provides better customization for the report layout (header, street list, stats).

## Open Tasks
- [ ] nur vorerst eine idee: wie könnte man mehrere flyeraktion laufen lassen?