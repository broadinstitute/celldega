const WIDE_CLASS = 'celldega-wide-notebook';
const TOGGLE_CLASS = 'celldega-notebook-nav-toggle';

// Sidebar-toggle icon: a window outline with a left panel. The panel is filled
// while the navigation sidebar is shown and hollow while hidden, and the
// chevron points the way a click will move it.
function sidebarIcon(sidebarShown) {
    const chevron = sidebarShown ? 'M15 9.5 L12.5 12 L15 14.5' : 'M13 9.5 L15.5 12 L13 14.5';
    return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
        stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="4.5" width="18" height="15" rx="2.5"/>
        <path d="M9 4.5 V19.5"/>
        <rect x="3.9" y="5.4" width="4.2" height="13.2" rx="1.6"
            fill="${sidebarShown ? 'currentColor' : 'none'}" stroke="none"
            opacity="0.85"/>
        <path d="${chevron}"/>
    </svg>`;
}

function initializeNotebookLayout() {
    document.querySelectorAll(`.${TOGGLE_CLASS}`).forEach((button) => button.remove());

    // nbconvert wraps rendered notebooks in .jupyter-wrapper. Detecting the
    // generated markup is more reliable than coupling this behavior to URL
    // conventions, and makes every documentation notebook wide by default.
    // Gallery pages (docs/gallery/gallery_*.md) host full-width stand-alone
    // visualizations, so they get the same toggle.
    const isNotebookPage = Boolean(document.querySelector('.jupyter-wrapper'));
    const isGalleryExample = /\/gallery\/gallery_[^/]+\/?$/.test(window.location.pathname);
    if (!isNotebookPage && !isGalleryExample) {
        document.body.classList.remove(WIDE_CLASS);
        return;
    }

    const storageKey = `celldega-wide-notebook:${window.location.pathname}`;
    const savedPreference = window.sessionStorage.getItem(storageKey);
    let wide = savedPreference !== 'false';

    const header = document.querySelector('.md-header__inner');
    if (!header) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = `md-header__button ${TOGGLE_CLASS}`;

    const applyLayout = () => {
        document.body.classList.toggle(WIDE_CLASS, wide);
        const action = wide ? 'Show navigation sidebar' : 'Hide navigation sidebar';
        // `wide` means the sidebar is hidden.
        button.innerHTML = sidebarIcon(!wide);
        button.setAttribute('aria-label', action);
        button.setAttribute('aria-pressed', String(wide));
        button.title = action;
    };

    button.addEventListener('click', () => {
        wide = !wide;
        window.sessionStorage.setItem(storageKey, String(wide));
        applyLayout();
    });

    // The left edge, immediately before the logo, visually associates the
    // control with the navigation drawer it reveals. `title` above supplies
    // the native hover tooltip in addition to the accessible label.
    header.insertBefore(button, header.firstElementChild);
    applyLayout();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNotebookLayout);
} else {
    initializeNotebookLayout();
}

// Reinitialize after Material's optional instant-navigation page swaps.
if (window.document$?.subscribe) {
    window.document$.subscribe(initializeNotebookLayout);
}
