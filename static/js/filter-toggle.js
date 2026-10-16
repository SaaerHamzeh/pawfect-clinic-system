/**
 * Pawfect Clinic - Universal Filter Bar Controller
 * Preserves filter bar toggle state per-page strictly based on user action & localStorage.
 */
window.filterController = function (pageKey) {
    const key = pageKey || window.location.pathname;
    const storageKey = 'pawfect_filters_visible_' + key;

    // Read saved preference from localStorage (defaults to true if first visit)
    const storedVal = localStorage.getItem(storageKey);
    const initialOpen = storedVal !== null ? (storedVal === 'true') : true;

    return {
        filtersOpen: initialOpen,

        toggleFilters() {
            this.filtersOpen = !this.filtersOpen;
            try {
                localStorage.setItem(storageKey, String(this.filtersOpen));
            } catch (e) {
                console.warn('localStorage error:', e);
            }
        },

        openFilters() {
            this.filtersOpen = true;
            try {
                localStorage.setItem(storageKey, 'true');
            } catch (e) {}
        },

        closeFilters() {
            this.filtersOpen = false;
            try {
                localStorage.setItem(storageKey, 'false');
            } catch (e) {}
        }
    };
};
