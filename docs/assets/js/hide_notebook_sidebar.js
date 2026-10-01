const WIDE_MARKER = '[data-celldega-wide-notebook]';
const WIDE_CLASS = 'celldega-wide-notebook';

function initializeNotebookLayout() {
    // Keep the existing modest width improvement for every notebook/gallery.
    const isNotebookPage =
        window.location.pathname.includes('notebook') ||
        window.location.pathname.includes('gallery_');

    if (isNotebookPage) {
        const primarySidebar = document.querySelector('.md-sidebar--primary');
        const secondarySidebar = document.querySelector('.md-sidebar--secondary');
        const mainGrid = document.querySelector('.md-main__inner');

        if (primarySidebar) primarySidebar.style.width = '8.1rem';
        if (secondarySidebar) secondarySidebar.style.display = 'none';
        if (mainGrid) {
            mainGrid.style.marginLeft = 'unset';
            mainGrid.style.marginRight = 'unset';
            mainGrid.style.maxWidth = 'none';
        }
    }

    const marker = document.querySelector(WIDE_MARKER);
    if (!marker) {
        document.body.classList.remove(WIDE_CLASS);
        return;
    }

    // The marker makes wide mode opt-in and reusable for future notebook pages.
    // Default to expanded, but remember the reader's choice for this page.
    const storageKey = `celldega-wide-notebook:${window.location.pathname}`;
    const savedPreference = window.sessionStorage.getItem(storageKey);
    let expanded = savedPreference !== 'false';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'celldega-wide-notebook-toggle';

    const applyLayout = () => {
        document.body.classList.toggle(WIDE_CLASS, expanded);
        button.textContent = expanded ? 'Show navigation' : 'Expand notebook';
        button.setAttribute('aria-pressed', String(expanded));
        button.title = expanded
            ? 'Restore the documentation navigation sidebar'
            : 'Hide navigation and use the full browser width';
    };

    button.addEventListener('click', () => {
        expanded = !expanded;
        window.sessionStorage.setItem(storageKey, String(expanded));
        applyLayout();
    });

    marker.classList.add('celldega-wide-notebook-controls');
    marker.replaceChildren(button);
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
